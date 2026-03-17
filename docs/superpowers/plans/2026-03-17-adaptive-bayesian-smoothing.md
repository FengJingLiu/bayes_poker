# 自适应贝叶斯平滑 + 全局 PFR 补偿 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 stats adapter 的过度平滑问题, 使不同 PFR 的玩家 (bcsilva PFR=16.8% vs Ivan_87 PFR=54.6%) 在同一节点上产生不同的 posterior_freq.

**Architecture:** 两层修改: (1) stats_adapter 中引入自适应 pool_prior_strength 基于玩家总手数动态调整; (2) 在 PlayerNodeStats 中附加全局 PFR/VPIP, 在 opponent_pipeline 中对 aggressive action 用 confidence 混合节点级+全局信号.

**Tech Stack:** Python 3.12+, pytest, pokerkit, SQLite

**Spec:** `docs/superpowers/specs/2026-03-17-adaptive-bayesian-smoothing-design.md`

---

## File Structure

### 修改文件

| 文件 | 职责变更 |
|------|---------|
| `src/bayes_poker/strategy/strategy_engine/stats_adapter.py` | 新增 `_compute_adaptive_prior_strength()`; 扩展 `PlayerNodeStats` 增加 `global_pfr`/`global_vpip`/`total_hands`; 扩展 `PlayerNodeStatsAdapterConfig`; 重写 `load()` 四步流程 |
| `src/bayes_poker/storage/player_stats_repository.py` | 新增 `get_with_raw()` 方法 |
| `src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py` | `_adjust_belief_with_stats_and_ev()` 中对 aggressive action 增加全局 PFR 混合 |

### 测试文件

| 文件 | 职责 |
|------|------|
| `tests/test_strategy_engine_v2_stats_adapter.py` | 扩展: adaptive_k 单元测试, 新字段测试, confidence 基于 raw 测试, feature flag 回归测试 |
| `tests/test_strategy_engine_v2_opponent_pipeline.py` | 扩展: 全局 PFR 混合逻辑测试 |
| `tests/real_scenario/test_3bet_all_positions.py` | 已有集成测试验证 bcsilva vs Ivan_87 产生不同 posterior |

---

## TODOs

### Task 1: 扩展 PlayerNodeStats 数据模型与 Config

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:18-39`
- Test: `tests/test_strategy_engine_v2_stats_adapter.py`

- [ ] **Step 1: 给 PlayerNodeStats 添加 3 个新字段**

在 `PlayerNodeStats` dataclass 中, 在 `source_kind` 之前添加三个新字段:

```python
@dataclass(frozen=True, slots=True)
class PlayerNodeStats:
    """当前节点的玩家动作概率视图。"""

    raise_probability: float
    call_probability: float
    fold_probability: float
    bet_0_40_probability: float
    bet_40_80_probability: float
    bet_80_120_probability: float
    bet_over_120_probability: float
    confidence: float
    global_pfr: float       # 新增: 玩家全局 PFR (0.0~1.0)
    global_vpip: float      # 新增: 玩家全局 VPIP (0.0~1.0)
    total_hands: int        # 新增: 总手牌数
    source_kind: str
```

- [ ] **Step 2: 扩展 PlayerNodeStatsAdapterConfig**

```python
@dataclass(frozen=True, slots=True)
class PlayerNodeStatsAdapterConfig:
    """玩家节点概率适配器配置。"""

    pool_prior_strength: float = 20.0
    confidence_k: float = 20.0
    adaptive_reference_hands: float = 200.0
    adaptive_min_strength: float = 2.0
    enable_global_raise_blending: bool = True
```

- [ ] **Step 3: 修复所有现有测试中 PlayerNodeStats 的构造**

现有测试和代码中所有 `PlayerNodeStats(...)` 的构造都需要添加 `global_pfr=0.0, global_vpip=0.0, total_hands=0` 参数. 搜索所有现有引用并更新.

注意: `load()` 方法的返回值构造也需要临时添加默认值, 待 Task 2 完成后会正式填充.

- [ ] **Step 4: 运行测试确认不破坏现有逻辑**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v`
Expected: ALL PASS (现有测试全过, 新字段有默认值)

- [ ] **Step 5: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/stats_adapter.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: 扩展 PlayerNodeStats 添加 global_pfr/vpip/total_hands 字段"
```

### Task 2: 实现 repository get_with_raw() 方法

**Files:**
- Modify: `src/bayes_poker/storage/player_stats_repository.py:253-302`
- Test: `tests/test_strategy_engine_v2_stats_adapter.py`

- [ ] **Step 1: 编写 get_with_raw() 的测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 中新增测试:

```python
def test_get_with_raw_returns_both_raw_and_smoothed(tmp_path: Path) -> None:
    """get_with_raw() 应一次返回 raw 和 smoothed 两份统计."""
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo, _make_player_stats(player_name="villain", params=context.params)
        )
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100", params=context.params
            ),
        )
        raw, smoothed = repo.get_with_raw(
            "villain", TableType.SIX_MAX, pool_prior_strength=20.0
        )
    assert raw is not None
    assert smoothed is not None
    # raw 的节点级概率不应被平滑
    raw_action = raw.get_preflop_stats(context.params)
    assert raw_action.raise_samples == 5
    assert raw_action.fold_samples == 2
    # smoothed 的概率会被 pool 影响
    smoothed_action = smoothed.get_preflop_stats(context.params)
    assert smoothed_action.raise_samples != raw_action.raise_samples  # 平滑后不同


def test_get_with_raw_missing_player_returns_none_pair(tmp_path: Path) -> None:
    """玩家不存在时 get_with_raw() 返回 (None, None)."""
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100",
                params=_make_node_context().params,
            ),
        )
        raw, smoothed = repo.get_with_raw(
            "nobody", TableType.SIX_MAX, pool_prior_strength=20.0
        )
    assert raw is None
    assert smoothed is None
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py::test_get_with_raw_returns_both_raw_and_smoothed -v`
Expected: FAIL (方法不存在)

- [ ] **Step 3: 在 player_stats_repository.py 实现 get_with_raw()**

在 `PlayerStatsRepository` 类的 `get()` 方法之后 (约 line 303) 添加:

```python
def get_with_raw(
    self,
    player_name: str,
    table_type: TableType,
    *,
    pool_prior_strength: float = 20.0,
) -> tuple[PlayerStats | None, PlayerStats | None]:
    """一次读取, 同时返回 (raw_stats, smoothed_stats).

    避免 stats_adapter 需要两次调用 get() 的性能问题.
    内部复用 _get_raw() 和 _smooth_player_stats_with_pool().

    Args:
        player_name: 玩家名称.
        table_type: 桌型.
        pool_prior_strength: 平滑时使用的先验强度.

    Returns:
        元组 (raw_stats, smoothed_stats).
        若玩家不存在则返回 (None, None).

    Raises:
        ValueError: 当先验强度不为正时抛出.
    """
    raw_stats = self._get_raw(player_name, table_type)
    if raw_stats is None:
        return None, None

    if pool_prior_strength <= 0.0:
        raise ValueError("pool_prior_strength 必须大于 0.")

    pool_player_name = _POOL_PRIOR_PLAYER_NAMES.get(table_type)
    if not pool_player_name or player_name == pool_player_name:
        return raw_stats, raw_stats

    pool_stats = self._get_raw(pool_player_name, table_type)
    if pool_stats is None:
        return raw_stats, raw_stats

    smoothed = self._smooth_player_stats_with_pool(
        raw_stats=raw_stats,
        pool_stats=pool_stats,
        pool_prior_strength=pool_prior_strength,
    )
    return raw_stats, smoothed
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v -k "get_with_raw"`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/bayes_poker/storage/player_stats_repository.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: 新增 PlayerStatsRepository.get_with_raw() 一次返回 raw+smoothed"
```

### Task 3: 实现自适应 pool_prior_strength 与 load() 重写

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py:60-135`
- Test: `tests/test_strategy_engine_v2_stats_adapter.py`

依赖: Task 1 (PlayerNodeStats 新字段), Task 2 (get_with_raw)

- [ ] **Step 1: 编写 _compute_adaptive_prior_strength 的测试**

在 `tests/test_strategy_engine_v2_stats_adapter.py` 中新增:

```python
def test_compute_adaptive_prior_strength_zero_hands() -> None:
    """0 手牌时返回 base_strength (20.0)."""
    adapter = PlayerNodeStatsAdapter.__new__(PlayerNodeStatsAdapter)
    adapter._config = PlayerNodeStatsAdapterConfig()
    stats = PlayerStats(player_name="test", table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=0, total=0)
    result = adapter._compute_adaptive_prior_strength(stats)
    assert result == 20.0


def test_compute_adaptive_prior_strength_200_hands() -> None:
    """200 手牌时 k 减半至 10.0."""
    adapter = PlayerNodeStatsAdapter.__new__(PlayerNodeStatsAdapter)
    adapter._config = PlayerNodeStatsAdapterConfig()
    stats = PlayerStats(player_name="test", table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=50, total=200)
    result = adapter._compute_adaptive_prior_strength(stats)
    assert abs(result - 10.0) < 0.01


def test_compute_adaptive_prior_strength_min_clamp() -> None:
    """超大手牌数时 clamp 到 min_strength."""
    adapter = PlayerNodeStatsAdapter.__new__(PlayerNodeStatsAdapter)
    adapter._config = PlayerNodeStatsAdapterConfig(
        adaptive_min_strength=2.0, adaptive_reference_hands=200.0
    )
    stats = PlayerStats(player_name="test", table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=500, total=5000)
    result = adapter._compute_adaptive_prior_strength(stats)
    assert result == 2.0  # 20/(1+5000/200)=20/26≈0.77 → clamp to 2.0
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v -k "adaptive_prior"`
Expected: FAIL (方法不存在)

- [ ] **Step 3: 实现 _compute_adaptive_prior_strength()**

在 `PlayerNodeStatsAdapter` 类中 `_build_confidence()` 之前添加:

```python
def _compute_adaptive_prior_strength(
    self,
    player_stats: PlayerStats,
) -> float:
    """根据玩家全局手牌量自适应调整 pool_prior_strength.

    全局手牌多 → 信任玩家数据 → 降低 prior_strength.
    全局手牌少 → 不确定性高 → 保持较高 prior_strength.

    Args:
        player_stats: 玩家原始统计数据.

    Returns:
        自适应调整后的 pool_prior_strength.
    """
    total_hands = player_stats.vpip.total
    base = self._config.pool_prior_strength
    ref = self._config.adaptive_reference_hands
    adaptive_k = base / (1.0 + total_hands / ref)
    return max(self._config.adaptive_min_strength, adaptive_k)
```

- [ ] **Step 4: 运行 adaptive_prior 测试确认 PASS**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v -k "adaptive_prior"`
Expected: ALL PASS

- [ ] **Step 5: 编写 load() 重写后的测试**

新增测试验证 load() 现在使用 adaptive_k 且填充全局字段:

```python
def test_load_fills_global_fields(tmp_path: Path) -> None:
    """load() 应正确填充 global_pfr, global_vpip, total_hands."""
    context = _make_node_context()
    # 创建一个有明确统计的玩家: vpip=10/20, 节点: raise=5, call=3, fold=2
    stats = _make_player_stats(player_name="villain", params=context.params)
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(repo, stats)
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100", params=context.params
            ),
        )
        adapter = PlayerNodeStatsAdapter(repo)
        result = adapter.load(
            player_name="villain",
            table_type=TableType.SIX_MAX,
            node_context=context,
        )
    assert result.total_hands == 20
    assert result.global_vpip > 0.0
    # global_pfr 基于 raw stats 计算
    assert result.global_pfr >= 0.0
    assert result.source_kind == "player"


def test_load_population_fallback_global_fields(tmp_path: Path) -> None:
    """population fallback 时 global 字段为 0."""
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100", params=context.params
            ),
        )
        adapter = PlayerNodeStatsAdapter(repo)
        result = adapter.load(
            player_name="missing",
            table_type=TableType.SIX_MAX,
            node_context=context,
        )
    assert result.source_kind == "population"
    assert result.global_pfr == 0.0
    assert result.global_vpip == 0.0
    assert result.total_hands == 0


def test_confidence_uses_raw_not_smoothed_samples(tmp_path: Path) -> None:
    """confidence 必须基于 raw node samples 而非 smoothed pseudo-counts."""
    context = _make_node_context()
    stats = _make_player_stats(player_name="villain", params=context.params)
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(repo, stats)
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100", params=context.params
            ),
        )
        adapter = PlayerNodeStatsAdapter(
            repo, config=PlayerNodeStatsAdapterConfig(confidence_k=20.0)
        )
        result = adapter.load(
            player_name="villain",
            table_type=TableType.SIX_MAX,
            node_context=context,
        )
    # raw node total = 2+3+5=10, confidence = 10/(10+20)=1/3
    raw_total = 10
    expected_confidence = raw_total / (raw_total + 20.0)
    assert abs(result.confidence - expected_confidence) < 0.01
```

- [ ] **Step 6: 重写 load() 方法**

替换现有 `load()` 方法 (lines 60-98) 为四步流程:

```python
def load(
    self,
    *,
    player_name: str | None,
    table_type: TableType,
    node_context: PlayerNodeContext,
) -> PlayerNodeStats:
    """读取指定玩家在当前节点的动作概率。

    四步流程:
    1. 获取 raw_stats 计算 adaptive_k.
    2. 基于 adaptive_k 调用 get_with_raw() 获取 (raw, smoothed).
    3. 从 raw 提取 confidence + 全局信号.
    4. 从 smoothed 提取节点概率, 组装返回.

    Args:
        player_name: 玩家名, 为空时直接走 population fallback.
        table_type: 桌型.
        node_context: 当前节点上下文.

    Returns:
        当前节点的玩家动作概率.
    """
    source_kind = "player"

    # Step 1: 尝试获取 raw stats 以计算 adaptive_k
    raw_stats = self._load_raw_player_stats(player_name, table_type)
    if raw_stats is None or (player_name and raw_stats.player_name != player_name):
        # population fallback
        return self._load_population_node_stats(table_type, node_context)

    # Step 2: 计算 adaptive_k 并获取 raw + smoothed
    adaptive_k = self._compute_adaptive_prior_strength(raw_stats)
    raw_from_pair, smoothed = self._repo.get_with_raw(
        player_name,  # type: ignore[arg-type]
        table_type,
        pool_prior_strength=adaptive_k,
    )
    if smoothed is None:
        return self._load_population_node_stats(table_type, node_context)

    # Step 3: 从 raw 提取 confidence + 全局信号
    raw_action = raw_from_pair.get_preflop_stats(node_context.params) if raw_from_pair else None
    raw_total = raw_action.total_samples() if raw_action else 0
    raw_confidence = self._build_confidence(raw_total)

    global_pfr = self._compute_global_pfr(raw_from_pair) if raw_from_pair else 0.0
    global_vpip = raw_from_pair.vpip.to_float() if raw_from_pair else 0.0
    total_hands = raw_from_pair.vpip.total if raw_from_pair else 0

    # Step 4: 从 smoothed 提取节点概率
    smoothed_action = smoothed.get_preflop_stats(node_context.params)
    return PlayerNodeStats(
        raise_probability=smoothed_action.bet_raise_probability(),
        call_probability=smoothed_action.check_call_probability(),
        fold_probability=smoothed_action.fold_probability(),
        bet_0_40_probability=smoothed_action.bet_0_40_probability(),
        bet_40_80_probability=smoothed_action.bet_40_80_probability(),
        bet_80_120_probability=smoothed_action.bet_80_120_probability(),
        bet_over_120_probability=smoothed_action.bet_over_120_probability(),
        confidence=raw_confidence,
        global_pfr=global_pfr,
        global_vpip=global_vpip,
        total_hands=total_hands,
        source_kind=source_kind,
    )
```

同时添加辅助方法:

```python
def _load_raw_player_stats(
    self,
    player_name: str | None,
    table_type: TableType,
) -> PlayerStats | None:
    """获取玩家原始未平滑统计 (仅用于读取 vpip.total 等全局指标)."""
    if not player_name:
        return None
    try:
        return self._repo.get(
            player_name, table_type, smooth_with_pool=False
        )
    except sqlite3.OperationalError:
        return None

def _load_population_node_stats(
    self,
    table_type: TableType,
    node_context: PlayerNodeContext,
) -> PlayerNodeStats:
    """构建 population fallback 的 PlayerNodeStats."""
    stats = self._load_population_stats(table_type)
    action_stats = stats.get_preflop_stats(node_context.params)
    total_samples = action_stats.total_samples()
    return PlayerNodeStats(
        raise_probability=action_stats.bet_raise_probability(),
        call_probability=action_stats.check_call_probability(),
        fold_probability=action_stats.fold_probability(),
        bet_0_40_probability=action_stats.bet_0_40_probability(),
        bet_40_80_probability=action_stats.bet_40_80_probability(),
        bet_80_120_probability=action_stats.bet_80_120_probability(),
        bet_over_120_probability=action_stats.bet_over_120_probability(),
        confidence=self._build_confidence(total_samples),
        global_pfr=0.0,
        global_vpip=0.0,
        total_hands=0,
        source_kind="population",
    )

@staticmethod
def _compute_global_pfr(player_stats: PlayerStats) -> float:
    """从原始统计安全计算全局 PFR."""
    from bayes_poker.player_metrics.builder import calculate_pfr
    positive, total = calculate_pfr(player_stats)
    return positive / total if total > 0 else 0.0
```

- [ ] **Step 7: 运行全部 stats_adapter 测试**

Run: `uv run pytest tests/test_strategy_engine_v2_stats_adapter.py -v`
Expected: ALL PASS

注意: 现有测试 `test_player_stats_hit` 中的 `confidence` 断言值可能需要更新.
旧逻辑: confidence 基于 smoothed total (包含 pool pseudo-counts, 约 30/50=0.6).
新逻辑: confidence 基于 raw total (10/(10+20)=1/3≈0.333).
如果测试断言 `stats.confidence == 30/50`, 需要改为 `stats.confidence == 10/30`.

- [ ] **Step 8: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/stats_adapter.py tests/test_strategy_engine_v2_stats_adapter.py
git commit -m "feat: 实现自适应 pool_prior_strength 和 load() 四步流程"
```

### Task 4: opponent_pipeline 全局 PFR 混合逻辑

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py:406-479`
- Test: `tests/test_strategy_engine_v2_opponent_pipeline.py`

依赖: Task 1 (PlayerNodeStats 新字段)

- [ ] **Step 1: 编写全局 PFR 混合的测试**

在 `tests/test_strategy_engine_v2_opponent_pipeline.py` 中新增测试.
需要先了解该测试文件的结构, 然后添加:

```python
def test_adjust_belief_blends_global_pfr_for_raise() -> None:
    """aggressive action 应混合节点级 stats 和全局 PFR."""
    # 构造 PlayerNodeStats: confidence=0.3, global_pfr=0.5, raise_prob=0.2
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )
    # 对 RAISE action: target = 0.3*0.2 + 0.7*0.5 = 0.41
    # 而不是原来的 0.2
    # 具体断言需要根据 _adjust_belief_with_stats_and_ev 的完整逻辑验证


def test_adjust_belief_no_blend_for_fold() -> None:
    """fold action 不应混合全局信号, 继续用节点级."""
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )
    # fold: target_frequency = stats_frequency (0.5), 不做混合


def test_feature_flag_disabled_no_blend(tmp_path: Path) -> None:
    """enable_global_raise_blending=False 时行为与旧逻辑完全一致."""
    # 使用 enable_global_raise_blending=False 的 config
    # 验证 target_frequency == stats_frequency (不混合)
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `uv run pytest tests/test_strategy_engine_v2_opponent_pipeline.py -v -k "blend"`
Expected: FAIL

- [ ] **Step 3: 修改 _adjust_belief_with_stats_and_ev()**

修改 `opponent_pipeline.py:406-479` 中的 `_adjust_belief_with_stats_and_ev()`:

1. 函数签名新增 `enable_global_raise_blending: bool = True` 参数
2. 在计算 `target_frequency` 时:

```python
stats_frequency = _stats_frequency_for_action_type(
    observed_action_type=observed_action_type,
    node_stats=node_stats,
)

# 全局 PFR 混合 (仅对 aggressive action)
if (
    enable_global_raise_blending
    and observed_action_type in {ActionType.RAISE, ActionType.BET, ActionType.ALL_IN}
    and node_stats.total_hands > 0
):
    node_confidence = node_stats.confidence
    global_signal = node_stats.global_pfr
    target_frequency = (
        node_confidence * stats_frequency
        + (1.0 - node_confidence) * global_signal
    )
else:
    target_frequency = stats_frequency

target_frequency = min(max(target_frequency, 0.0), 1.0)
```

3. 在 `_build_posterior_range()` 调用处, 传入 `enable_global_raise_blending` 参数 (从 config 获取)

- [ ] **Step 4: 更新 _build_posterior_range() 调用链**

在 `OpponentPipeline._build_posterior_range()` (line 200) 中, 需要将 `enable_global_raise_blending` 从 config 传递到 `_adjust_belief_with_stats_and_ev()`. 

需要在 `OpponentPipeline.__init__()` 中存储 stats_adapter 的 config, 或直接从 stats_adapter 获取. 最简做法: 
- 在 `OpponentPipelineConfig` 中添加 `enable_global_raise_blending: bool = True`
- 传递到 `_adjust_belief_with_stats_and_ev()`

如果 `OpponentPipelineConfig` 不存在, 则在调用处硬编码 `enable_global_raise_blending=True` (后续重构).

- [ ] **Step 5: 运行测试确认 PASS**

Run: `uv run pytest tests/test_strategy_engine_v2_opponent_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py tests/test_strategy_engine_v2_opponent_pipeline.py
git commit -m "feat: opponent_pipeline 对 aggressive action 混合全局 PFR 信号"
```

### Task 5: 全量回归测试

**Files:**
- Test: ALL test files

依赖: Task 1-4 全部完成

- [ ] **Step 1: 运行全部单元测试**

Run: `uv run pytest -q --tb=short`
Expected: ALL PASS (0 failures)

- [ ] **Step 2: 运行 real_scenario 集成测试 (如果数据可用)**

Run: `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q -s tests/real_scenario/ --tb=short`
Expected: ALL PASS, 且 bcsilva 和 Ivan_87 现在产生**不同**的 posterior range

如果数据不可用 (环境变量未设置或数据库不存在), 跳过此步.

- [ ] **Step 3: 验证语法检查**

Run: `uv run python -m compileall src`
Expected: 无错误

- [ ] **Step 4: Commit (如有修复)**

仅在步骤 1-3 发现并修复了问题时才 commit:

```bash
git add -A
git commit -m "fix: 全量回归测试修复"
```

## Final Verification Wave

- [ ] F1: Oracle 代码审查 — 所有修改文件的逻辑正确性
- [ ] F2: 全量测试通过 — `uv run pytest -q` 零失败
- [ ] F3: 编译检查 — `uv run python -m compileall src` 无错误
- [ ] F4: 集成验证 — bcsilva 和 Ivan_87 在 3bet 节点上产生不同 posterior (如数据可用)
