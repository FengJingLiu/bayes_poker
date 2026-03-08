# Player Pool Posterior Smoothing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `PlayerStatsRepository.get()` 增加可选的“按玩家池做后验平滑”读取能力, 并基于 `aggregated_sixmax_100` 对每个 `params` 下的 `ActionStats` 按 Beta-Binomial 或 Dirichlet-Multinomial 公式做平滑。

**Architecture:** 保持 Rust 和 SQLite 继续只存 raw counts, 不改二进制格式与建库流程。Python 读取玩家统计时, 如果调用方显式开启平滑, 则额外读取 `aggregated_sixmax_100` 作为玩家池先验, 按动作空间为二元或多元分别计算 pseudo-count posterior, 再返回与现有 `PlayerStats` / `ActionStats` 兼容的平滑结果。

**Tech Stack:** Python 3.12, dataclasses, sqlite3, pytest, 现有 `PlayerStatsRepository` / `PlayerStats` / `ActionStats`。

---

### Task 1: 定义后验平滑数据契约与公式实现

**Files:**
- Create: `src/bayes_poker/player_metrics/posterior.py`
- Modify: `src/bayes_poker/player_metrics/__init__.py`
- Test: `tests/test_player_metrics_posterior.py`

**Step 1: 写失败测试, 固定 Beta 与 Dirichlet 公式行为**

```python
def test_beta_posterior_matches_pool_prior_and_player_samples() -> None:
    posterior = smooth_binary_counts(
        prior_probability=0.40,
        prior_strength=20.0,
        positive_count=3.0,
        total_count=10.0,
    )
    assert posterior.positive == pytest.approx(11.0)
    assert posterior.total == pytest.approx(30.0)


def test_dirichlet_posterior_matches_pool_prior_and_player_samples() -> None:
    posterior = smooth_multinomial_counts(
        prior_probabilities=(0.5, 0.3, 0.2),
        prior_strength=10.0,
        counts=(2.0, 1.0, 7.0),
    )
    assert posterior == pytest.approx((7.0, 4.0, 9.0))
```

**Step 2: 运行测试, 确认缺少后验模块而失败**

Run: `uv run pytest -q tests/test_player_metrics_posterior.py`
Expected: FAIL, 因为 `posterior.py` 尚未存在。

**Step 3: 实现最小后验模块**

```python
@dataclass(frozen=True, slots=True)
class PosteriorSmoothingConfig:
    enabled: bool = False
    pool_prior_strength: float = 20.0


def smooth_binary_counts(...) -> BinaryPosteriorCounts:
    positive = (prior_strength * prior_probability) + positive_count
    total = prior_strength + total_count
    return BinaryPosteriorCounts(positive=positive, total=total)


def smooth_multinomial_counts(...) -> tuple[float, ...]:
    total = prior_strength + sum(counts)
    return tuple((prior_strength * prior) + count for prior, count in zip(...))
```

**Step 4: 增加动作空间判定辅助函数**

```python
def classify_preflop_action_space(params: PreFlopParams) -> ActionSpaceSpec: ...
def classify_postflop_action_space(params: PostFlopParams) -> ActionSpaceSpec: ...
```

要求:
- 翻前 `unopened / first-in` 这类只有 `fold` 与 `raise` 的 spot 走 Beta。
- 翻后 `num_bets == 0` 的 spot 走 `check_call` vs `bet_raise` 二元 Beta。
- 其余保留 `fold / check_call / bet_raise` 三元 Dirichlet。
- 返回的 pseudo-count 必须仍能装回 `ActionStats`。

**Step 5: 运行测试并补边界断言**

Run: `uv run pytest -q tests/test_player_metrics_posterior.py`
Expected: PASS

**Step 6: 提交本任务**

```bash
git add src/bayes_poker/player_metrics/posterior.py src/bayes_poker/player_metrics/__init__.py tests/test_player_metrics_posterior.py
git commit -m "feat: add player metrics posterior smoothing primitives"
```

### Task 2: 在仓库读取层增加可选玩家池后验平滑

**Files:**
- Modify: `src/bayes_poker/storage/player_stats_repository.py`
- Modify: `src/bayes_poker/strategy/opponent_range/stats_source.py`
- Test: `tests/test_player_stats_storage.py`

**Step 1: 写失败测试, 固定 `get(..., smooth_with_pool=True)` 的返回行为**

```python
def test_get_can_return_pool_smoothed_stats(tmp_path: Path) -> None:
    with PlayerStatsRepository(db_path) as repo:
        raw_player = repo.get("Hero", TableType.SIX_MAX)
        smoothed_player = repo.get(
            "Hero",
            TableType.SIX_MAX,
            smooth_with_pool=True,
            pool_prior_strength=20.0,
        )
    assert raw_player is not None
    assert smoothed_player is not None
    assert smoothed_player.preflop_stats[0].raise_samples > raw_player.preflop_stats[0].raise_samples
```

**Step 2: 运行测试, 确认签名不支持新参数而失败**

Run: `uv run pytest -q tests/test_player_stats_storage.py -k smooth`
Expected: FAIL, 因为 `PlayerStatsRepository.get()` 还不接受新参数。

**Step 3: 修改仓库接口并实现平滑装配**

```python
def get(
    self,
    player_name: str,
    table_type: TableType,
    *,
    smooth_with_pool: bool = False,
    pool_prior_strength: float = 20.0,
) -> PlayerStats | None:
    raw_stats = self._get_raw(...)
    if not smooth_with_pool:
        return raw_stats
    pool_stats = self._get_raw("aggregated_sixmax_100", table_type)
    return smooth_player_stats_with_pool(...)
```

实现要求:
- 新增私有 `_get_raw()` 避免在读取池先验时递归调用自身。
- 对 `aggregated_sixmax_100` 自身始终返回 raw stats, 不再对池均值做二次平滑。
- 当玩家不存在时返回 `None`。
- 当池先验不存在时回退到 raw player stats。
- `stats_source.get_aggregated_player_stats()` 保持显式走 raw 路径。

**Step 4: 运行存储层测试**

Run: `uv run pytest -q tests/test_player_stats_storage.py`
Expected: PASS

**Step 5: 提交本任务**

```bash
git add src/bayes_poker/storage/player_stats_repository.py src/bayes_poker/strategy/opponent_range/stats_source.py tests/test_player_stats_storage.py
git commit -m "feat: add optional pool-smoothed player stats reads"
```

### Task 3: 接入主要消费路径, 只在玩家个体查询时启用平滑

**Files:**
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/runtime/preflop.py`
- Test: `tests/test_opponent_range.py`

**Step 1: 写失败测试, 固定 predictor 读取玩家个体统计时启用平滑**

```python
def test_shared_predictor_uses_pool_smoothed_player_stats(...) -> None:
    predictor = create_opponent_range_predictor(...)
    predictor.update_range_on_action(...)
    assert stub_repo.calls == [
        ("villain", TableType.SIX_MAX, True, 20.0),
        ("aggregated_sixmax_100", TableType.SIX_MAX, False, 20.0),
    ]
```

**Step 2: 运行目标测试, 确认调用参数不匹配而失败**

Run: `uv run pytest -q tests/test_opponent_range.py -k smoothed`
Expected: FAIL, 因为当前调用仍然只走 `repo.get(player_id, table_type)`。

**Step 3: 修改调用点**

规则:
- 玩家个体读取改为 `smooth_with_pool=True`。
- 聚合玩家读取保持 `smooth_with_pool=False`。
- 默认先验强度先固定为 `20.0`, 集中定义为模块级常量, 不散落 magic number。

优先修改这些调用点:
- `OpponentRangePredictor._build_shared_tendency_profile()`
- `OpponentRangePredictor._get_initial_preflop_range()`
- `OpponentRangePredictor._get_preflop_action_scale()`
- `runtime/preflop._player_cluster_beliefs()`

**Step 4: 运行相关测试**

Run: `uv run pytest -q tests/test_opponent_range.py tests/test_preflop_runtime_strategy.py`
Expected: PASS

**Step 5: 提交本任务**

```bash
git add src/bayes_poker/strategy/opponent_range/predictor.py src/bayes_poker/strategy/runtime/preflop.py tests/test_opponent_range.py
git commit -m "feat: use pool-smoothed player stats in predictors"
```

### Task 4: 回归验证与文档收尾

**Files:**
- Modify: `src/bayes_poker/storage/player_stats_repository.py`
- Modify: `src/bayes_poker/player_metrics/posterior.py`
- Modify: `tests/test_player_metrics_posterior.py`
- Modify: `tests/test_player_stats_storage.py`
- Modify: `tests/test_opponent_range.py`

**Step 1: 补充风险用例**

```python
def test_get_smoothed_stats_returns_raw_when_pool_missing() -> None: ...
def test_get_smoothed_stats_does_not_smooth_aggregated_player_row() -> None: ...
def test_dirichlet_posterior_preserves_probability_simplex() -> None: ...
```

**Step 2: 运行精确回归命令**

Run: `uv run pytest -q tests/test_player_metrics_posterior.py tests/test_player_stats_storage.py tests/test_opponent_range.py tests/test_preflop_runtime_strategy.py`
Expected: PASS

**Step 3: 运行更大范围的安全回归**

Run: `uv run pytest -q tests/test_preflop_engine_tendency.py tests/test_preflop_engine_calibrator.py tests/test_player_metrics.py`
Expected: PASS

**Step 4: 检查未覆盖风险并收尾**

需要人工确认:
- `aggregated_sixmax_100` 的实际数据口径按需求视为“玩家等权平均”, 代码不再额外验证。
- 第一版不接入 GTO / archetype 混合先验, 但 `posterior.py` 内部保留多 prior source 扩展位。
- 第一版不改 Rust schema, 因此 pseudo-count 只存在于读取返回值, 不回写数据库。

**Step 5: 提交本任务**

```bash
git add src/bayes_poker/storage/player_stats_repository.py src/bayes_poker/player_metrics/posterior.py tests/test_player_metrics_posterior.py tests/test_player_stats_storage.py tests/test_opponent_range.py
git commit -m "test: cover pool posterior smoothing behavior"
```
