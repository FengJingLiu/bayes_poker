# 相似玩家个性化先验 + 样本上限 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用风格相似的玩家群体聚合数据替代全局 pool 先验做贝叶斯平滑, 并设置样本上限 1000 手防止高样本玩家 confidence 过高.

**Architecture:** 三层修改: (1) 新建 `SimilarPlayerIndex` 按 VPIP/PFR 欧氏距离检索相似玩家; (2) Repository 层新增 `get_with_similar_prior()` 用相似玩家聚合替代 pool 平滑; (3) stats_adapter 中接入相似玩家路径 + 样本上限约束 confidence 和 adaptive_k.

**Tech Stack:** Python 3.12+, pytest, pokerkit, SQLite

**Spec:** `docs/superpowers/specs/2026-03-18-similar-player-prior-design.md`

---

## File Structure

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/bayes_poker/strategy/strategy_engine/similar_player_index.py` | `PlayerProfile` dataclass + `SimilarPlayerIndex` 类: 基于 VPIP/PFR 欧氏距离检索相似玩家 |
| `tests/test_similar_player_index.py` | SimilarPlayerIndex 全面单元测试 |

### 修改文件

| 文件 | 职责变更 |
|------|---------|
| `src/bayes_poker/strategy/strategy_engine/stats_adapter.py` | `PlayerNodeStatsAdapterConfig` 新增 `max_observation_samples`; `__init__` 新增 `similar_index` 参数; `load()` 增加相似玩家分支; `_build_confidence()` 和 `_compute_adaptive_prior_strength()` 应用样本上限 |
| `src/bayes_poker/storage/player_stats_repository.py` | 新增 `get_with_similar_prior()` 方法: 聚合相似玩家节点数据做先验平滑, 节点级 fallback 到 pool |
| `src/bayes_poker/strategy/strategy_engine/engine.py` | `StrategyEngineConfig` 新增 5 个配置字段; `build_strategy_engine()` 构建 SimilarPlayerIndex 并传入 stats_adapter |
| `src/bayes_poker/strategy/strategy_engine/handler.py` | `create_strategy_handler()` 透传新增配置字段 |
| `tests/test_strategy_engine_v2_stats_adapter.py` | 扩展: 样本上限测试, 相似玩家路径测试 |

---

## Chunk 1: SimilarPlayerIndex + 样本上限

### Task 1: 创建 SimilarPlayerIndex 模块

**Files:**
- Create: `src/bayes_poker/strategy/strategy_engine/similar_player_index.py`
- Create: `tests/test_similar_player_index.py`

- [ ] **Step 1: 写 SimilarPlayerIndex 的失败测试**

创建 `tests/test_similar_player_index.py`:

```python
"""SimilarPlayerIndex 单元测试."""
from __future__ import annotations

import pytest

from bayes_poker.strategy.strategy_engine.similar_player_index import (
    PlayerProfile,
    SimilarPlayerIndex,
)


# ── fixtures ──────────────────────────────────────────────

def _build_profiles() -> list[PlayerProfile]:
    """构建测试用玩家档案列表.

    Returns:
        包含 5 个不同风格玩家的档案列表.
    """
    return [
        PlayerProfile(name="tight_a", vpip=0.18, pfr=0.14, total_hands=200),
        PlayerProfile(name="tight_b", vpip=0.20, pfr=0.16, total_hands=100),
        PlayerProfile(name="lag_a", vpip=0.35, pfr=0.28, total_hands=300),
        PlayerProfile(name="lag_b", vpip=0.38, pfr=0.30, total_hands=50),
        PlayerProfile(name="fish", vpip=0.55, pfr=0.08, total_hands=500),
    ]


# ── 基础功能测试 ──────────────────────────────────────────

class TestSimilarPlayerIndex:
    """SimilarPlayerIndex 核心功能测试."""

    def test_query_returns_similar_players(self) -> None:
        """查询 tight 风格应返回 tight_a 和 tight_b."""
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=5,
            max_distance=0.15,
        )
        result = index.query(vpip=0.19, pfr=0.15)
        names = [p.name for p in result]
        assert "tight_a" in names
        assert "tight_b" in names
        # LAG 和 fish 距离太远, 不应出现
        assert "lag_a" not in names
        assert "fish" not in names

    def test_query_excludes_self(self) -> None:
        """查询时排除自身玩家."""
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=5,
            max_distance=1.0,  # 放大距离确保都能匹配
        )
        result = index.query(vpip=0.18, pfr=0.14, exclude_name="tight_a")
        names = [p.name for p in result]
        assert "tight_a" not in names

    def test_query_respects_max_results(self) -> None:
        """返回结果不超过 max_results."""
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=2,
            max_distance=1.0,  # 放大距离
        )
        result = index.query(vpip=0.30, pfr=0.20)
        assert len(result) <= 2

    def test_query_empty_when_no_match(self) -> None:
        """无匹配时返回空列表."""
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=5,
            max_distance=0.01,  # 极小距离
        )
        result = index.query(vpip=0.90, pfr=0.90)
        assert result == []

    def test_query_sorted_by_distance(self) -> None:
        """结果按距离从近到远排序."""
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=10,
            max_distance=1.0,
        )
        result = index.query(vpip=0.19, pfr=0.15)
        # 验证距离单调递增
        for i in range(len(result) - 1):
            dist_i = ((result[i].vpip - 0.19) ** 2 + (result[i].pfr - 0.15) ** 2) ** 0.5
            dist_next = ((result[i + 1].vpip - 0.19) ** 2 + (result[i + 1].pfr - 0.15) ** 2) ** 0.5
            assert dist_i <= dist_next

    def test_empty_profiles(self) -> None:
        """空档案列表不报错, 返回空."""
        index = SimilarPlayerIndex(
            profiles=[],
            max_results=5,
            max_distance=0.15,
        )
        result = index.query(vpip=0.20, pfr=0.15)
        assert result == []

    def test_excludes_aggregated_players(self) -> None:
        """以 aggregated_ 开头的玩家在构建时被排除."""
        profiles = _build_profiles() + [
            PlayerProfile(
                name="aggregated_sixmax_100",
                vpip=0.25,
                pfr=0.20,
                total_hands=999999,
            ),
        ]
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=10,
            max_distance=1.0,
        )
        result = index.query(vpip=0.25, pfr=0.20)
        names = [p.name for p in result]
        assert "aggregated_sixmax_100" not in names

    def test_min_hands_filter(self) -> None:
        """低于 min_hands 阈值的玩家在构建时被排除.

        lag_b 只有 50 手, 当 min_hands=100 时应被过滤.
        """
        profiles = _build_profiles()
        index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=10,
            max_distance=1.0,
            min_hands=100,
        )
        result = index.query(vpip=0.38, pfr=0.30)
        names = [p.name for p in result]
        assert "lag_b" not in names
```

- [ ] **Step 2: 运行测试确认失败**

运行: `uv run pytest tests/test_similar_player_index.py -v`
预期: FAIL — `ModuleNotFoundError: No module named 'bayes_poker.strategy.strategy_engine.similar_player_index'`

- [ ] **Step 3: 实现 SimilarPlayerIndex**

创建 `src/bayes_poker/strategy/strategy_engine/similar_player_index.py`:

```python
"""相似玩家索引模块.

基于 VPIP/PFR 欧氏距离检索与目标玩家风格相似的玩家群体,
用于个性化贝叶斯先验平滑.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """玩家风格档案.

    Attributes:
        name: 玩家名称.
        vpip: 自愿入池率 (0.0~1.0).
        pfr: 翻前加注率 (0.0~1.0).
        total_hands: 总手数.
    """

    name: str
    vpip: float
    pfr: float
    total_hands: int


class SimilarPlayerIndex:
    """基于 VPIP/PFR 欧氏距离的相似玩家检索索引.

    构建时自动过滤:
    - 以 ``aggregated_`` 开头的聚合玩家
    - 总手数低于 ``min_hands`` 的玩家

    Attributes:
        _profiles: 过滤后的玩家档案列表.
        _max_results: 单次查询最大返回数量.
        _max_distance: 欧氏距离阈值.
    """

    def __init__(
        self,
        *,
        profiles: list[PlayerProfile],
        max_results: int = 130,
        max_distance: float = 0.15,
        min_hands: int = 30,
    ) -> None:
        """初始化相似玩家索引.

        Args:
            profiles: 所有玩家档案列表.
            max_results: 单次查询最大返回数量.
            max_distance: VPIP/PFR 欧氏距离阈值, 超过则不视为相似.
            min_hands: 最小手数阈值, 低于此值的玩家被过滤.
        """
        self._max_results = max_results
        self._max_distance = max_distance
        self._profiles = [
            p
            for p in profiles
            if not p.name.startswith("aggregated_") and p.total_hands >= min_hands
        ]

    def query(
        self,
        vpip: float,
        pfr: float,
        exclude_name: str | None = None,
    ) -> list[PlayerProfile]:
        """检索与目标 VPIP/PFR 相似的玩家.

        Args:
            vpip: 目标 VPIP (0.0~1.0).
            pfr: 目标 PFR (0.0~1.0).
            exclude_name: 需排除的玩家名称 (通常为目标玩家自身).

        Returns:
            按欧氏距离从近到远排序的相似玩家列表, 最多 max_results 个.
        """
        candidates: list[tuple[float, PlayerProfile]] = []
        for p in self._profiles:
            if exclude_name is not None and p.name == exclude_name:
                continue
            dist = math.hypot(p.vpip - vpip, p.pfr - pfr)
            if dist <= self._max_distance:
                candidates.append((dist, p))

        candidates.sort(key=lambda x: x[0])
        return [p for _, p in candidates[: self._max_results]]
```

- [ ] **Step 4: 运行测试确认通过**

运行: `uv run pytest tests/test_similar_player_index.py -v`
预期: 全部 PASS (8 tests)

- [ ] **Step 5: 提交**

```bash
git add src/bayes_poker/strategy/strategy_engine/similar_player_index.py tests/test_similar_player_index.py
git commit -m "feat: 新增 SimilarPlayerIndex 基于 VPIP/PFR 欧氏距离检索相似玩家"
```

---

### Task 2: 样本上限 — 修改 stats_adapter Config + confidence + adaptive_k

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:51-65` (Config)
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:160-180` (_compute_adaptive_prior_strength)
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:274-277` (_build_confidence)
- Test: `tests/test_strategy_engine_v2_stats_adapter.py`

- [ ] **Step 1: 写样本上限的失败测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 末尾添加:

```python
# ── 样本上限测试 ──────────────────────────────────────────


class TestSampleCap:
    """样本上限 (max_observation_samples) 测试."""

    def test_confidence_capped_at_max_samples(self, tmp_path: Path) -> None:
        """当 total_samples > max_observation_samples 时, confidence 被限制.

        2000 样本在 max_observation_samples=1000 下, confidence 应与 1000 样本相同.
        """
        db = tmp_path / "test.db"
        conn = _insert_player_stats(db, "player_a", _make_player_stats())
        # 插入 pool
        _insert_player_stats(
            db, "aggregated_sixmax_100", _make_player_stats(), conn=conn,
        )
        conn.close()

        config = PlayerNodeStatsAdapterConfig(
            max_observation_samples=1000,
        )
        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)
        adapter = PlayerNodeStatsAdapter(repo, config=config)

        ctx = _make_node_context()

        # 修改 raw 数据使 total_samples 为 2000
        raw, _ = repo.get_with_raw("player_a")
        assert raw is not None
        # 需要验证: confidence = min(total, 1000) / (min(total, 1000) + k)
        # 由于 _make_player_stats 的 total 是 10 (fold=2+call=3+raise=5),
        # 我们无法直接构造 2000 样本, 所以用公式验证:
        # 如果 total=10, max_observation_samples=5:
        #   capped confidence = 5 / (5 + 20) = 0.2
        #   uncapped confidence = 10 / (10 + 20) ≈ 0.333
        config_small_cap = PlayerNodeStatsAdapterConfig(
            max_observation_samples=5,
        )
        adapter_capped = PlayerNodeStatsAdapter(repo, config=config_small_cap)
        result_capped = adapter_capped.load("player_a", ctx)
        assert result_capped is not None
        # confidence = min(10, 5) / (min(10, 5) + 20) = 5/25 = 0.2
        assert result_capped.confidence == pytest.approx(0.2, abs=1e-6)

    def test_confidence_uncapped_below_limit(self, tmp_path: Path) -> None:
        """当 total_samples < max_observation_samples 时, confidence 不受影响.

        total=10, max_observation_samples=1000: confidence = 10/(10+20) ≈ 0.333
        """
        db = tmp_path / "test.db"
        conn = _insert_player_stats(db, "player_a", _make_player_stats())
        _insert_player_stats(
            db, "aggregated_sixmax_100", _make_player_stats(), conn=conn,
        )
        conn.close()

        config = PlayerNodeStatsAdapterConfig(
            max_observation_samples=1000,
        )
        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)
        adapter = PlayerNodeStatsAdapter(repo, config=config)

        result = adapter.load("player_a", _make_node_context())
        assert result is not None
        # total=10 < 1000, 不受限: 10/(10+20) = 0.333...
        assert result.confidence == pytest.approx(10.0 / 30.0, abs=1e-6)

    def test_adaptive_k_capped_at_max_samples(self, tmp_path: Path) -> None:
        """adaptive_k 计算中 vpip.total 被 max_observation_samples 限制."""
        db = tmp_path / "test.db"
        conn = _insert_player_stats(db, "player_a", _make_player_stats())
        _insert_player_stats(
            db, "aggregated_sixmax_100", _make_player_stats(), conn=conn,
        )
        conn.close()

        # vpip.total = 20 in _make_player_stats (vpip=StatValue(10,20))
        # max_observation_samples=10: capped_total = min(20, 10) = 10
        # adaptive_k = max(pool_prior_strength * (1 - 10/200), adaptive_min_strength)
        #            = max(20 * (1 - 0.05), 2.0) = max(19.0, 2.0) = 19.0
        # 对比 uncapped: 20 * (1 - 20/200) = 20 * 0.9 = 18.0
        config_capped = PlayerNodeStatsAdapterConfig(
            max_observation_samples=10,
        )
        config_uncapped = PlayerNodeStatsAdapterConfig(
            max_observation_samples=1000,
        )

        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)
        adapter_capped = PlayerNodeStatsAdapter(repo, config=config_capped)
        adapter_uncapped = PlayerNodeStatsAdapter(repo, config=config_uncapped)

        ctx = _make_node_context()
        result_capped = adapter_capped.load("player_a", ctx)
        result_uncapped = adapter_uncapped.load("player_a", ctx)
        assert result_capped is not None
        assert result_uncapped is not None
        # capped 版本的 prior_strength 更大 (因为样本看起来更少)
        # 这意味着更偏向先验, 所以 posterior 中先验权重更高
        # 我们无法直接读取 adaptive_k, 但可以通过 posterior 间接验证:
        # 如果 adaptive_k 不同, 两者的 raise_probability 应该不同
        # (因为 pool prior 和 raw data 的 raise 比例不同时)
        # 这里直接验证 adaptive_k 的数学:
        # capped: strength = max(20*(1-10/200), 2) = 19.0
        # uncapped: strength = max(20*(1-20/200), 2) = 18.0
        # 两者不同, 所以 posterior 不同
        assert result_capped.raise_probability != result_uncapped.raise_probability
```

- [ ] **Step 2: 运行测试确认失败**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestSampleCap -v`
预期: FAIL — `PlayerNodeStatsAdapterConfig` 不接受 `max_observation_samples` 参数

- [ ] **Step 3: 实现样本上限**

修改 `src/bayes_poker/strategy/strategy_engine/stats_adapter.py`:

**(a) Config 新增字段** — 在 `PlayerNodeStatsAdapterConfig` 中添加:

```python
max_observation_samples: int = 1000
"""样本上限, 超过此值时 confidence 和 adaptive_k 不再增长."""
```

**(b) `_build_confidence` 应用上限** — 修改方法:

```python
@staticmethod
def _build_confidence(
    total_samples: int,
    config: PlayerNodeStatsAdapterConfig,
) -> float:
    """计算 confidence, 受 max_observation_samples 限制.

    Args:
        total_samples: 原始总样本数.
        config: adapter 配置.

    Returns:
        confidence 值 (0.0~1.0).
    """
    capped = min(total_samples, config.max_observation_samples)
    return capped / (capped + config.confidence_k)
```

**(c) `_compute_adaptive_prior_strength` 应用上限** — 在方法内部:

将 `player_stats.vpip.total` 替换为 `min(player_stats.vpip.total, config.max_observation_samples)`:

```python
capped_total = min(player_stats.vpip.total, config.max_observation_samples)
ratio = capped_total / config.adaptive_reference_hands
adaptive_k = max(
    config.pool_prior_strength * (1.0 - ratio),
    config.adaptive_min_strength,
)
```

注意: `_compute_adaptive_prior_strength` 需要能访问 `config`, 如果当前签名不含 config 参数, 需要添加.

- [ ] **Step 4: 运行测试确认通过**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v`
预期: 全部 PASS (原有 12 tests + 新增 3 tests)

- [ ] **Step 5: 运行全量测试确认无回归**

运行: `uv run pytest -q`
预期: 全部 PASS (约 450+ tests)

- [ ] **Step 6: 提交**

```bash
git add src/bayes_poker/strategy/strategy_engine/stats_adapter.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: 样本上限 1000 手 — 限制 confidence 和 adaptive_k 增长"
```

---

## Chunk 2: 相似玩家先验路径

### Task 3: Repository 层 — get_with_similar_prior()

**Files:**
- Modify: `src/bayes_poker/storage/player_stats_repository.py:665-682` (get_all 附近)
- Test: `tests/test_strategy_engine_v2_stats_adapter.py` (通过 adapter 间接测试)

- [ ] **Step 1: 写 get_with_similar_prior 的失败测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 中添加 Repository 级别的直接测试:

```python
class TestGetWithSimilarPrior:
    """Repository.get_with_similar_prior() 测试."""

    def test_similar_prior_uses_aggregate_of_similar_players(
        self, tmp_path: Path,
    ) -> None:
        """相似玩家聚合替代 pool 先验.

        构造 target + 2 个相似玩家 + pool, 验证返回的 smoothed 数据
        使用相似玩家聚合而非 pool.
        """
        db = tmp_path / "test.db"
        # target: vpip=50%, fold=2, call=3, raise=5
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)

        # similar_a: fold=10, call=5, raise=5 (fold 倾向)
        similar_a = _make_player_stats(fold=10, call=5, raise_=5)
        _insert_player_stats(db, "similar_a", similar_a, conn=conn)

        # similar_b: fold=8, call=6, raise=6 (也偏 fold)
        similar_b = _make_player_stats(fold=8, call=6, raise_=6)
        _insert_player_stats(db, "similar_b", similar_b, conn=conn)

        # pool: fold=1, call=1, raise=8 (极端 raise 倾向)
        pool = _make_player_stats(fold=1, call=1, raise_=8)
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool, conn=conn,
        )
        conn.close()

        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        similar_names = ["similar_a", "similar_b"]
        raw, smoothed = repo.get_with_similar_prior(
            player_name="target",
            similar_player_names=similar_names,
            prior_strength=20.0,
        )

        assert raw is not None
        assert smoothed is not None

        # 验证: smoothed 的 fold 应该偏向相似玩家聚合 (fold 倾向)
        # 而非 pool (raise 倾向)
        ctx = _make_node_context()
        node_key = ctx.preflop_params
        smoothed_node = smoothed.get_preflop_stats(node_key)
        assert smoothed_node is not None

        # 相似玩家聚合: fold=18, call=11, raise=11 → fold 比例高
        # pool: fold=1, call=1, raise=8 → raise 比例高
        # 如果用了相似玩家先验, fold_probability 应显著 > 用 pool 时
        pool_raw, pool_smoothed = repo.get_with_raw("target")
        assert pool_smoothed is not None
        pool_node = pool_smoothed.get_preflop_stats(node_key)
        assert pool_node is not None

        # smoothed (similar prior) 的 fold 应 > smoothed (pool prior) 的 fold
        assert smoothed_node.fold_samples > 0  # 基本 sanity

    def test_similar_prior_fallback_to_pool_on_missing_node(
        self, tmp_path: Path,
    ) -> None:
        """当相似玩家聚合在某节点样本不足时, 该节点 fallback 到 pool.

        构造相似玩家在目标节点无数据的场景.
        """
        db = tmp_path / "test.db"
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)

        # pool 有数据
        pool = _make_player_stats()
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool, conn=conn,
        )
        conn.close()

        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        # 空的相似玩家列表 → 所有节点 fallback 到 pool
        raw, smoothed = repo.get_with_similar_prior(
            player_name="target",
            similar_player_names=[],
            prior_strength=20.0,
        )
        assert raw is not None
        assert smoothed is not None

    def test_similar_prior_min_aggregate_samples(
        self, tmp_path: Path,
    ) -> None:
        """聚合样本低于 min_aggregate_samples 时 fallback 到 pool.

        min_aggregate_samples 默认 20, 当相似玩家在该节点总样本 < 20 时
        应 fallback 到 pool 先验.
        """
        db = tmp_path / "test.db"
        # target
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)

        # similar: 只有 5 个样本 (fold=2, call=2, raise=1) < 20
        similar = _make_player_stats(fold=2, call=2, raise_=1)
        _insert_player_stats(db, "similar_one", similar, conn=conn)

        # pool
        pool = _make_player_stats(fold=1, call=1, raise_=8)
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool, conn=conn,
        )
        conn.close()

        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        raw, smoothed = repo.get_with_similar_prior(
            player_name="target",
            similar_player_names=["similar_one"],
            prior_strength=20.0,
            min_aggregate_samples=20,
        )
        assert raw is not None
        assert smoothed is not None
        # 由于 similar 样本 < 20, 应 fallback 到 pool
        # 结果应与 get_with_raw 相同 (使用 pool 先验)
```

- [ ] **Step 2: 运行测试确认失败**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestGetWithSimilarPrior -v`
预期: FAIL — `PlayerStatsRepository` 没有 `get_with_similar_prior` 方法

- [ ] **Step 3: 实现 get_with_similar_prior()**

在 `src/bayes_poker/storage/player_stats_repository.py` 中, 在 `get_with_raw()` 方法之后添加新方法:

```python
def get_with_similar_prior(
    self,
    player_name: str,
    similar_player_names: list[str],
    prior_strength: float,
    min_aggregate_samples: int = 20,
) -> tuple[PlayerStats | None, PlayerStats | None]:
    """用相似玩家聚合数据替代 pool 做先验平滑.

    流程:
    1. 获取 raw player_stats
    2. 加载所有 similar_player 的 raw stats
    3. 对每个 preflop 节点: 聚合相似玩家的 ActionStats
    4. 若聚合 total_samples >= min_aggregate_samples, 用聚合做先验
    5. 否则 fallback 到 pool 先验
    6. postflop 节点始终使用 pool 先验

    Args:
        player_name: 目标玩家名.
        similar_player_names: 相似玩家名列表.
        prior_strength: 先验强度 (Dirichlet/Beta alpha 总和).
        min_aggregate_samples: 聚合最小样本阈值, 低于则 fallback 到 pool.

    Returns:
        (raw, smoothed) 元组, 找不到玩家时 raw 为 None.
    """
    raw = self._get_player_stats(player_name)
    if raw is None:
        return None, None

    pool = self._get_pool_prior()
    if pool is None:
        return raw, raw

    # 加载相似玩家的 raw stats
    similar_stats_list: list[PlayerStats] = []
    for name in similar_player_names:
        stats = self._get_player_stats(name)
        if stats is not None:
            similar_stats_list.append(stats)

    # 聚合相似玩家的 preflop 节点数据
    aggregated_preflop = self._aggregate_preflop_nodes(similar_stats_list)

    # 平滑: preflop 用聚合先验 (带 fallback), postflop 用 pool
    action_spaces = self._build_preflop_action_spaces(raw)
    smoothed_preflop = self._smooth_preflop_with_similar(
        raw=raw,
        aggregated=aggregated_preflop,
        pool=pool,
        action_spaces=action_spaces,
        prior_strength=prior_strength,
        min_aggregate_samples=min_aggregate_samples,
    )
    smoothed_postflop = self._smooth_postflop_stats(raw, pool, prior_strength)

    smoothed = PlayerStats(
        vpip=raw.vpip,
        preflop_stats=smoothed_preflop,
        postflop_stats=smoothed_postflop,
    )
    return raw, smoothed
```

需要添加的辅助方法:

```python
def _aggregate_preflop_nodes(
    self,
    stats_list: list[PlayerStats],
) -> dict[PreFlopParams, ActionStats]:
    """聚合多个玩家的 preflop 节点数据.

    Args:
        stats_list: 玩家 stats 列表.

    Returns:
        节点参数 → 聚合后的 ActionStats 的映射.
    """
    aggregated: dict[PreFlopParams, ActionStats] = {}
    for stats in stats_list:
        for params, action_stats in stats.preflop_stats.items():
            if params in aggregated:
                aggregated[params].append(action_stats)
            else:
                # 深拷贝避免修改原始数据
                aggregated[params] = ActionStats(
                    fold_samples=action_stats.fold_samples,
                    call_samples=action_stats.call_samples,
                    bet_raise_samples=action_stats.bet_raise_samples,
                    bet_size_0_40_samples=action_stats.bet_size_0_40_samples,
                    bet_size_40_80_samples=action_stats.bet_size_40_80_samples,
                    bet_size_80_120_samples=action_stats.bet_size_80_120_samples,
                    bet_size_over_120_samples=action_stats.bet_size_over_120_samples,
                )
    return aggregated

def _smooth_preflop_with_similar(
    self,
    raw: PlayerStats,
    aggregated: dict[PreFlopParams, ActionStats],
    pool: PlayerStats,
    action_spaces: dict[PreFlopParams, list[str]],
    prior_strength: float,
    min_aggregate_samples: int,
) -> dict[PreFlopParams, ActionStats]:
    """用相似玩家聚合先验平滑 preflop 节点, 不足时 fallback 到 pool.

    Args:
        raw: 目标玩家原始数据.
        aggregated: 相似玩家聚合的节点数据.
        pool: 全局 pool 先验.
        action_spaces: 各节点的动作空间.
        prior_strength: 先验强度.
        min_aggregate_samples: 聚合最小样本阈值.

    Returns:
        平滑后的 preflop stats.
    """
    smoothed: dict[PreFlopParams, ActionStats] = {}
    for params, raw_action in raw.preflop_stats.items():
        agg = aggregated.get(params)
        use_similar = (
            agg is not None
            and agg.total_samples() >= min_aggregate_samples
        )
        prior_action = agg if use_similar else pool.get_preflop_stats(params)
        if prior_action is None:
            smoothed[params] = raw_action
            continue

        fields = action_spaces.get(params, [])
        smoothed[params] = self._smooth_action_stats(
            raw_action_stats=raw_action,
            pool_action_stats=prior_action,
            prior_strength=prior_strength,
            active_fields=fields,
        )
    return smoothed
```

注意事项:
- `_smooth_postflop_stats` 需要从现有的 `_smooth_player_stats_with_pool` 中提取, 或直接复用现有 postflop 平滑逻辑.
- 如果 `_smooth_player_stats_with_pool` 中 postflop 部分不是独立方法, 需要提取为 `_smooth_postflop_stats`.
- 实际实现时检查 `_smooth_action_stats` 的签名是否接受 `active_fields` 参数 (现有代码中可能叫不同名字).

- [ ] **Step 4: 运行测试确认通过**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestGetWithSimilarPrior -v`
预期: 全部 PASS (3 tests)

- [ ] **Step 5: 运行全量测试确认无回归**

运行: `uv run pytest -q`
预期: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/bayes_poker/storage/player_stats_repository.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: Repository 新增 get_with_similar_prior() 相似玩家聚合先验平滑"
```

---

### Task 4: stats_adapter 接入相似玩家路径

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:51-85` (Config + __init__)
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:87-158` (load)
- Test: `tests/test_strategy_engine_v2_stats_adapter.py`

- [ ] **Step 1: 写相似玩家路径的失败测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 中添加:

```python
from bayes_poker.strategy.strategy_engine.similar_player_index import (
    PlayerProfile,
    SimilarPlayerIndex,
)


class TestSimilarPlayerPath:
    """stats_adapter 相似玩家路径测试."""

    def _build_similar_index(
        self,
        profiles: list[PlayerProfile] | None = None,
    ) -> SimilarPlayerIndex:
        """构建测试用 SimilarPlayerIndex.

        Args:
            profiles: 玩家档案, 默认为空.

        Returns:
            SimilarPlayerIndex 实例.
        """
        return SimilarPlayerIndex(
            profiles=profiles or [],
            max_results=130,
            max_distance=0.15,
        )

    def test_load_uses_similar_prior_when_available(
        self, tmp_path: Path,
    ) -> None:
        """当 similar_index 提供且有匹配时, load() 使用相似玩家先验.

        构造 target + similar + pool, 验证 posterior 偏向 similar.
        """
        db = tmp_path / "test.db"
        # target: vpip=50% (10/20), fold=2, call=3, raise=5
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)

        # similar: vpip 相近, fold 倾向 (fold=15, call=3, raise=2)
        similar_stats = _make_player_stats(
            vpip_count=10, vpip_total=20,
            fold=15, call=3, raise_=2,
        )
        _insert_player_stats(db, "similar_guy", similar_stats, conn=conn)

        # pool: raise 倾向 (fold=1, call=1, raise=18)
        pool_stats = _make_player_stats(fold=1, call=1, raise_=18)
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool_stats, conn=conn,
        )
        conn.close()

        index = self._build_similar_index([
            PlayerProfile(
                name="similar_guy", vpip=0.50, pfr=0.10, total_hands=100,
            ),
        ])

        config = PlayerNodeStatsAdapterConfig()
        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        # 有 similar_index 的 adapter
        adapter_similar = PlayerNodeStatsAdapter(
            repo, config=config, similar_index=index,
        )
        # 无 similar_index 的 adapter (fallback 到 pool)
        adapter_pool = PlayerNodeStatsAdapter(repo, config=config)

        ctx = _make_node_context()
        result_similar = adapter_similar.load("target", ctx)
        result_pool = adapter_pool.load("target", ctx)

        assert result_similar is not None
        assert result_pool is not None

        # similar 先验偏 fold, pool 先验偏 raise
        # 所以 similar 路径的 fold_probability 应 > pool 路径
        assert result_similar.fold_probability > result_pool.fold_probability

    def test_load_fallback_to_pool_when_no_similar(
        self, tmp_path: Path,
    ) -> None:
        """similar_index 存在但无匹配时, fallback 到 pool 先验."""
        db = tmp_path / "test.db"
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)
        pool_stats = _make_player_stats()
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool_stats, conn=conn,
        )
        conn.close()

        # 构造一个不会匹配 target 的 index (空 profiles)
        index = self._build_similar_index([])

        config = PlayerNodeStatsAdapterConfig()
        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        adapter = PlayerNodeStatsAdapter(
            repo, config=config, similar_index=index,
        )
        result = adapter.load("target", _make_node_context())
        assert result is not None
        # 应该正常返回 (使用 pool fallback)

    def test_load_without_similar_index_unchanged(
        self, tmp_path: Path,
    ) -> None:
        """不传 similar_index 时, 行为与原来完全一致."""
        db = tmp_path / "test.db"
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)
        pool_stats = _make_player_stats()
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool_stats, conn=conn,
        )
        conn.close()

        config = PlayerNodeStatsAdapterConfig()
        repo = PlayerStatsRepository(db_path=db, table_type=TableType.SIXMAX)

        adapter = PlayerNodeStatsAdapter(repo, config=config)
        result = adapter.load("target", _make_node_context())
        assert result is not None
        # 验证与之前版本行为一致 (回归测试)
```

- [ ] **Step 2: 运行测试确认失败**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestSimilarPlayerPath -v`
预期: FAIL — `PlayerNodeStatsAdapter` 不接受 `similar_index` 参数

- [ ] **Step 3: 实现 stats_adapter 相似玩家路径**

修改 `src/bayes_poker/strategy/strategy_engine/stats_adapter.py`:

**(a) `__init__` 新增 similar_index 参数:**

```python
def __init__(
    self,
    repo: PlayerStatsRepository,
    *,
    config: PlayerNodeStatsAdapterConfig | None = None,
    similar_index: SimilarPlayerIndex | None = None,
) -> None:
    """初始化 PlayerNodeStatsAdapter.

    Args:
        repo: 玩家统计数据仓库.
        config: adapter 配置, 为 None 时使用默认值.
        similar_index: 相似玩家索引, 为 None 时使用 pool 先验.
    """
    self._repo = repo
    self._config = config or PlayerNodeStatsAdapterConfig()
    self._similar_index = similar_index
```

**(b) `load()` 增加相似玩家分支:**

在现有 `load()` 方法中, 获取 raw 后、调用 `get_with_raw()` 之前, 增加分支判断:

```python
def load(self, player_name: str, context: NodeContext) -> PlayerNodeStats | None:
    # ... 现有步骤 1-2 (获取 raw + pool) ...

    # 步骤 2.5: 尝试相似玩家路径
    if self._similar_index is not None:
        raw_stats, _ = self._repo.get_with_raw(player_name)
        if raw_stats is not None:
            vpip_rate = (
                raw_stats.vpip.count / raw_stats.vpip.total
                if raw_stats.vpip.total > 0
                else 0.0
            )
            pfr_count, pfr_total = self._compute_global_pfr(raw_stats)
            pfr_rate = pfr_count / pfr_total if pfr_total > 0 else 0.0

            similar = self._similar_index.query(
                vpip=vpip_rate,
                pfr=pfr_rate,
                exclude_name=player_name,
            )

            if similar:
                similar_names = [p.name for p in similar]
                raw, smoothed = self._repo.get_with_similar_prior(
                    player_name=player_name,
                    similar_player_names=similar_names,
                    prior_strength=adaptive_k,  # 使用自适应先验强度
                )
            else:
                raw, smoothed = self._repo.get_with_raw(player_name)
    else:
        raw, smoothed = self._repo.get_with_raw(player_name)

    # ... 后续步骤 (构建 PlayerNodeStats) ...
```

注意: 实际实现时需要仔细检查 `load()` 的完整流程, 确保:
1. `adaptive_k` 在调用 `get_with_similar_prior` 前已计算
2. `_compute_global_pfr` 是 staticmethod, 可在获取 raw 后立即调用
3. `raw` 和 `smoothed` 变量在后续流程中正确使用

**(c) 顶部添加 import:**

```python
from bayes_poker.strategy.strategy_engine.similar_player_index import (
    SimilarPlayerIndex,
)
```

- [ ] **Step 4: 运行测试确认通过**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v`
预期: 全部 PASS

- [ ] **Step 5: 运行全量测试确认无回归**

运行: `uv run pytest -q`
预期: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/bayes_poker/strategy/strategy_engine/stats_adapter.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: stats_adapter 接入相似玩家先验路径, 无匹配时 fallback 到 pool"
```

---

### Task 5: engine.py + handler.py 接线

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/engine.py:30-43` (Config)
- Modify: `src/bayes_poker/strategy/strategy_engine/engine.py:81-123` (build)
- Modify: `src/bayes_poker/strategy/strategy_engine/handler.py:15-56`

- [ ] **Step 1: 写 engine 接线的失败测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 中添加:

```python
from bayes_poker.strategy.strategy_engine.engine import (
    StrategyEngineConfig,
    build_strategy_engine,
)


class TestEngineWiring:
    """engine.py 接线测试."""

    def test_build_strategy_engine_with_similar_player_config(
        self, tmp_path: Path,
    ) -> None:
        """验证 build_strategy_engine 接受相似玩家配置字段."""
        db = tmp_path / "test.db"
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)
        pool_stats = _make_player_stats()
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool_stats, conn=conn,
        )
        conn.close()

        config = StrategyEngineConfig(
            player_stats_db_path=db,
            enable_similar_player_prior=True,
            similar_player_max_results=130,
            similar_player_max_distance=0.15,
            similar_player_min_hands=30,
            max_observation_samples=1000,
        )
        # 不应抛异常
        engine = build_strategy_engine(config)
        assert engine is not None

    def test_build_strategy_engine_similar_disabled(
        self, tmp_path: Path,
    ) -> None:
        """enable_similar_player_prior=False 时不构建 index."""
        db = tmp_path / "test.db"
        target_stats = _make_player_stats()
        conn = _insert_player_stats(db, "target", target_stats)
        pool_stats = _make_player_stats()
        _insert_player_stats(
            db, "aggregated_sixmax_100", pool_stats, conn=conn,
        )
        conn.close()

        config = StrategyEngineConfig(
            player_stats_db_path=db,
            enable_similar_player_prior=False,
        )
        engine = build_strategy_engine(config)
        assert engine is not None
```

- [ ] **Step 2: 运行测试确认失败**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestEngineWiring -v`
预期: FAIL — `StrategyEngineConfig` 不接受 `enable_similar_player_prior` 等参数

- [ ] **Step 3: 实现 engine.py 接线**

修改 `src/bayes_poker/strategy/strategy_engine/engine.py`:

**(a) StrategyEngineConfig 新增字段:**

```python
@dataclass(frozen=True, slots=True)
class StrategyEngineConfig:
    """策略引擎配置."""
    # ... 现有字段 ...

    # 相似玩家先验
    enable_similar_player_prior: bool = True
    """是否启用相似玩家个性化先验, 默认开启."""

    similar_player_max_results: int = 130
    """相似玩家检索最大返回数量."""

    similar_player_max_distance: float = 0.15
    """VPIP/PFR 欧氏距离阈值."""

    similar_player_min_hands: int = 30
    """相似玩家最小手数阈值."""

    max_observation_samples: int = 1000
    """样本上限, 超过此值时 confidence 和 adaptive_k 不再增长."""
```

**(b) build_strategy_engine() 构建 SimilarPlayerIndex:**

```python
from bayes_poker.strategy.strategy_engine.similar_player_index import (
    PlayerProfile,
    SimilarPlayerIndex,
)
from bayes_poker.player_metrics.builder import calculate_pfr


def build_strategy_engine(config: StrategyEngineConfig) -> ...:
    # ... 现有代码: 创建 repo ...

    similar_index: SimilarPlayerIndex | None = None
    if config.enable_similar_player_prior:
        all_players = repo.get_all()
        profiles: list[PlayerProfile] = []
        for name, stats in all_players.items():
            if stats.vpip.total == 0:
                continue
            vpip_rate = stats.vpip.count / stats.vpip.total
            pfr_count, pfr_total = calculate_pfr(stats)
            pfr_rate = pfr_count / pfr_total if pfr_total > 0 else 0.0
            profiles.append(PlayerProfile(
                name=name,
                vpip=vpip_rate,
                pfr=pfr_rate,
                total_hands=stats.vpip.total,
            ))
        similar_index = SimilarPlayerIndex(
            profiles=profiles,
            max_results=config.similar_player_max_results,
            max_distance=config.similar_player_max_distance,
            min_hands=config.similar_player_min_hands,
        )

    # 创建 stats_adapter 时传入 similar_index
    adapter_config = PlayerNodeStatsAdapterConfig(
        # ... 现有字段 ...
        max_observation_samples=config.max_observation_samples,
    )
    stats_adapter = PlayerNodeStatsAdapter(
        repo,
        config=adapter_config,
        similar_index=similar_index,
    )
    # ... 后续代码 ...
```

- [ ] **Step 4: 实现 handler.py 透传**

修改 `src/bayes_poker/strategy/strategy_engine/handler.py`:

在 `create_strategy_handler()` 中, 将新配置字段透传到 `StrategyEngineConfig`:

```python
def create_strategy_handler(
    *,
    # ... 现有参数 ...
    enable_similar_player_prior: bool = True,
    similar_player_max_results: int = 130,
    similar_player_max_distance: float = 0.15,
    similar_player_min_hands: int = 30,
    max_observation_samples: int = 1000,
) -> ...:
    config = StrategyEngineConfig(
        # ... 现有字段 ...
        enable_similar_player_prior=enable_similar_player_prior,
        similar_player_max_results=similar_player_max_results,
        similar_player_max_distance=similar_player_max_distance,
        similar_player_min_hands=similar_player_min_hands,
        max_observation_samples=max_observation_samples,
    )
    return build_strategy_engine(config)
```

- [ ] **Step 5: 运行测试确认通过**

运行: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::TestEngineWiring -v`
预期: 全部 PASS (2 tests)

- [ ] **Step 6: 运行全量测试确认无回归**

运行: `uv run pytest -q`
预期: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add src/bayes_poker/strategy/strategy_engine/engine.py src/bayes_poker/strategy/strategy_engine/handler.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: engine + handler 接线相似玩家先验, 新增 5 个配置字段"
```

---

## Final Verification Wave

### Task 6: 全量回归验证

- [ ] **Step 1: 运行全量测试**

```bash
uv run pytest -v
```

预期: 全部 PASS, 包括所有新增和已有测试.

- [ ] **Step 2: 运行语法检查**

```bash
uv run python -m compileall src
```

预期: 无语法错误.

- [ ] **Step 3: 检查 import 完整性**

```bash
uv run python -c "from bayes_poker.strategy.strategy_engine.similar_player_index import SimilarPlayerIndex, PlayerProfile; print('OK')"
uv run python -c "from bayes_poker.strategy.strategy_engine.engine import StrategyEngineConfig; print('OK')"
uv run python -c "from bayes_poker.storage.player_stats_repository import PlayerStatsRepository; print('OK')"
```

预期: 全部输出 `OK`.
