# Preflop Engine Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为项目引入统一的 preflop 推理内核, 同时打通节点映射、对手范围更新和 Hero 决策三条主线, 并让 `runtime` 与 `opponent_range` 复用同一套核心逻辑。

**Architecture:** 新增 `strategy/preflop_engine` 共享目录, 以 `PreflopDecisionState -> NodeMapper -> SolverPrior -> PlayerTendencyProfile -> PolicyCalibrator` 为主干, 在此基础上分化出 `RangeEngine` 和 `HeroDecisionEngine`。现有 `runtime/preflop.py` 和 `opponent_range/predictor.py` 退化为 adapter, 新增代码全部使用 Google 风格中文注释与完整类型标注。

**Tech Stack:** Python 3.12, pytest, uv, 现有 `PreflopStrategy` / `PreflopRange` / `PlayerStatsRepository` / `ObservedTableState` 模型。

## 执行结果（2026-03-07）

- `Task 1` 到 `Task 10` 已在分支 `feat/preflop-engine-refactor` 执行完成, 并按 task 粒度经过 spec review 与 code quality review。
- 当前实际落地范围:
  - `preflop_engine` 共享目录及其单元测试已落地。
  - `runtime` 共享 adapter 仅接管 `CALL_VS_OPEN` 相关主链, 其余仍回退 legacy。
  - `opponent_range` 共享 adapter 仅接管 `UTG first-in open` 与非盲位 `cold call vs open`, 其余前缀保持旧逻辑或 fallback。
- Task 9 关键提交:
  - `3853b94` `refactor: route opponent preflop ranges through shared adapter`
  - `1badcd5` `fix: narrow opponent range shared adapter scope`
  - `6b360a2` `fix: tighten opponent range shared adapter guards`
- 既有基线问题:
  - `tests/test_strategy_request_payload.py` 的导入失败为本轮开始前已存在的问题, 未纳入本计划实现范围。
- 最终验证命令与结果见本文件 `Task 10` 的执行记录。

---

### Task 1: 建立共享状态模型

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/__init__.py`
- Create: `src/bayes_poker/strategy/preflop_engine/state.py`
- Test: `tests/test_preflop_engine_state.py`

**Step 1: Write the failing test**

```python
def test_build_preflop_decision_state_for_open_plus_cold_call() -> None:
    state = build_preflop_decision_state(...)
    assert state.action_family == ActionFamily.CALL_VS_OPEN
    assert state.call_count == 1
    assert state.aggressor_position == TablePosition.UTG
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_state.py -q`
Expected: FAIL, 因为 `preflop_engine/state.py` 尚不存在。

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class PreflopDecisionState:
    action_family: ActionFamily
    actor_position: TablePosition
    aggressor_position: TablePosition | None
    call_count: int
    limp_count: int
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_state.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/__init__.py src/bayes_poker/strategy/preflop_engine/state.py tests/test_preflop_engine_state.py
git commit -m "feat: add preflop decision state model"
```

### Task 2: 实现 solver 先验候选读取与节点映射

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/solver_prior.py`
- Create: `src/bayes_poker/strategy/preflop_engine/mapper.py`
- Test: `tests/test_preflop_engine_mapper.py`

**Step 1: Write the failing tests**

```python
def test_mapper_prefers_same_family_and_ip_structure() -> None:
    context = mapper.map_state(state)
    assert context.matched_level == 2
    assert context.matched_history == "R2-C"
```

```python
def test_solver_prior_blends_multiple_candidates_by_distance() -> None:
    policy = solver_prior.build_policy(context)
    assert policy.action_names == ("F", "C", "R9.5")
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: FAIL, 因为映射器和先验读取层尚未实现。

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class MappedSolverContext:
    matched_level: int
    matched_history: str
    distance_score: float
    candidate_histories: tuple[str, ...]
```

```python
def map_state(self, state: PreflopDecisionState) -> MappedSolverContext:
    return self._map_by_distance(state)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/solver_prior.py src/bayes_poker/strategy/preflop_engine/mapper.py tests/test_preflop_engine_mapper.py
git commit -m "feat: add preflop solver mapper and prior loader"
```

### Task 3: 补齐价格修正与模板回退

**Files:**
- Modify: `src/bayes_poker/strategy/preflop_engine/mapper.py`
- Modify: `src/bayes_poker/strategy/preflop_engine/solver_prior.py`
- Test: `tests/test_preflop_engine_mapper.py`

**Step 1: Write the failing tests**

```python
def test_mapper_applies_price_adjustment_for_larger_open_size() -> None:
    context = mapper.map_state(state_with_three_bb_open)
    assert context.price_adjustment_applied is True
```

```python
def test_mapper_falls_back_to_synthetic_template_for_limp_family() -> None:
    context = mapper.map_state(limp_state)
    assert context.matched_level == 3
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -k "price or template" -q`
Expected: FAIL, 因为价格修正和模板回退尚未接入。

**Step 3: Write minimal implementation**

```python
def _apply_price_adjustment(...):
    if actual_size_bb > reference_size_bb:
        return edge_tighten_factor
    return edge_loosen_factor
```

```python
def _build_synthetic_template(...):
    return SyntheticTemplatePolicy(...)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/mapper.py src/bayes_poker/strategy/preflop_engine/solver_prior.py tests/test_preflop_engine_mapper.py
git commit -m "feat: add price adjustment and synthetic fallback"
```

### Task 4: 实现玩家画像与平滑层

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/tendency.py`
- Test: `tests/test_preflop_engine_tendency.py`

**Step 1: Write the failing tests**

```python
def test_build_profile_blends_population_and_player_stats() -> None:
    profile = profile_builder.build(...)
    assert profile.open_freq > 0.0
    assert 0.0 < profile.confidence < 1.0
```

```python
def test_build_profile_tracks_size_signal_only_when_samples_are_enough() -> None:
    profile = profile_builder.build(...)
    assert profile.size_signal_enabled is False
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_tendency.py -q`
Expected: FAIL, 因为画像和平滑模块尚未存在。

**Step 3: Write minimal implementation**

```python
def smooth_frequency(n_act: int, total: int, mu: float, k: float) -> float:
    return (n_act + k * mu) / (total + k)
```

```python
@dataclass(frozen=True, slots=True)
class PlayerTendencyProfile:
    open_freq: float
    call_freq: float
    confidence: float
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_tendency.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/tendency.py tests/test_preflop_engine_tendency.py
git commit -m "feat: add preflop tendency profile builder"
```

### Task 5: 实现策略校准器

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/policy_calibrator.py`
- Test: `tests/test_preflop_engine_calibrator.py`

**Step 1: Write the failing tests**

```python
def test_binary_calibrator_matches_target_open_frequency() -> None:
    calibrated = calibrate_binary_policy(base_policy, target_frequency=0.10)
    assert calibrated.total_frequency("OPEN") == pytest.approx(0.10, abs=1e-3)
```

```python
def test_multinomial_calibrator_preserves_relative_hand_order() -> None:
    calibrated = calibrate_multinomial_policy(base_policy, target_mix)
    assert calibrated.rank_for("CALL")[0] == "AJs"
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_calibrator.py -q`
Expected: FAIL, 因为校准器尚未实现。

**Step 3: Write minimal implementation**

```python
def calibrate_binary_policy(...):
    return _solve_logit_shift(...)
```

```python
def calibrate_multinomial_policy(...):
    return _solve_softmax_bias(...)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_calibrator.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/policy_calibrator.py tests/test_preflop_engine_calibrator.py
git commit -m "feat: add preflop policy calibrator"
```

### Task 6: 实现贝叶斯范围引擎

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/range_engine.py`
- Test: `tests/test_preflop_engine_range_engine.py`

**Step 1: Write the failing tests**

```python
def test_range_engine_builds_tight_utg_open_posterior() -> None:
    posterior = range_engine.observe_action(...)
    assert posterior.total_frequency() > 0.0
    assert posterior["KQo"] < posterior["AQo"]
```

```python
def test_range_engine_builds_condensed_mp_cold_call_range() -> None:
    posterior = range_engine.observe_action(...)
    assert posterior["AJs"] > posterior["AKs"]
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_range_engine.py -q`
Expected: FAIL, 因为范围引擎尚未存在。

**Step 3: Write minimal implementation**

```python
def update_posterior(prior: PreflopRange, calibrated_policy: ActionPolicy, action_name: str) -> PreflopRange:
    return normalize(prior * calibrated_policy.for_action(action_name))
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_range_engine.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/range_engine.py tests/test_preflop_engine_range_engine.py
git commit -m "feat: add preflop range engine"
```

### Task 7: 实现 Hero 决策引擎与解释输出

**Files:**
- Create: `src/bayes_poker/strategy/preflop_engine/hero_engine.py`
- Create: `src/bayes_poker/strategy/preflop_engine/explain.py`
- Test: `tests/test_preflop_engine_hero_engine.py`

**Step 1: Write the failing tests**

```python
def test_hero_engine_widens_btn_steal_against_under_defending_blinds() -> None:
    result = hero_engine.decide(...)
    assert result.recommended_action == "OPEN"
```

```python
def test_hero_engine_explains_iso_adjustment_against_limp_fold_player() -> None:
    result = hero_engine.decide(...)
    assert "limp-fold" in result.explanation.summary
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_hero_engine.py -q`
Expected: FAIL, 因为 Hero 决策引擎和解释层尚未存在。

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class HeroDecision:
    recommended_action: str
    recommended_size_bb: float | None
    action_distribution: dict[str, float]
    explanation: DecisionExplanation
```

```python
def decide(self, hero_state: PreflopDecisionState, villain_ranges: dict[str, PreflopRange]) -> HeroDecision:
    return self._build_decision(...)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_hero_engine.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/hero_engine.py src/bayes_poker/strategy/preflop_engine/explain.py tests/test_preflop_engine_hero_engine.py
git commit -m "feat: add preflop hero decision engine"
```

### Task 8: 接入 runtime adapter

**Files:**
- Modify: `src/bayes_poker/strategy/runtime/preflop.py`
- Modify: `src/bayes_poker/strategy/preflop_parse/models.py`
- Test: `tests/test_preflop_runtime_strategy.py`
- Test: `tests/test_preflop_runtime_framework.py`

**Step 1: Write the failing integration tests**

```python
def test_preflop_runtime_uses_shared_preflop_engine_for_non_standard_size() -> None:
    result = runtime.decide(payload)
    assert result["recommended_action"] in {"F", "C", "R9.5"}
    assert "mapped_level" in result["explanation"]
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_runtime_strategy.py tests/test_preflop_runtime_framework.py -q`
Expected: FAIL, 因为 runtime 仍走旧逻辑。

**Step 3: Write minimal implementation**

```python
class PreflopRuntime:
    def __post_init__(self) -> None:
        self.engine = PreflopHeroEngine(...)
```

```python
def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
    return self.engine.decide_from_payload(payload)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_preflop_runtime_strategy.py tests/test_preflop_runtime_framework.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/runtime/preflop.py src/bayes_poker/strategy/preflop_parse/models.py tests/test_preflop_runtime_strategy.py tests/test_preflop_runtime_framework.py
git commit -m "refactor: route preflop runtime through shared engine"
```

### Task 9: 接入 opponent range adapter 并做回归

**Files:**
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/opponent_range/predictor_flow.md`
- Test: `tests/test_opponent_range.py`
- Test: `tests/test_opponent_range_preflop_context.py`

**Step 1: Write the failing integration tests**

```python
def test_predictor_uses_shared_engine_for_tight_utg_open() -> None:
    predictor.update_range_on_action(...)
    assert predictor.get_preflop_range(utg_seat) is not None
```

```python
def test_predictor_uses_shared_engine_for_cold_call_condensed_range() -> None:
    predictor.update_range_on_action(...)
    assert predictor.get_preflop_range(mp_seat).total_frequency() > 0.0
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py tests/test_opponent_range_preflop_context.py -q`
Expected: FAIL, 因为 predictor 仍使用旧分支逻辑。

**Step 3: Write minimal implementation**

```python
class OpponentRangePredictor:
    def __post_init__(self) -> None:
        self._shared_range_engine = RangeEngine(...)
```

```python
def _update_preflop_range(...):
    self._preflop_ranges[seat] = self.range_engine.observe_action(...)
```

**Step 4: Run tests to verify they pass**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py tests/test_opponent_range_preflop_context.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/opponent_range/predictor.py src/bayes_poker/strategy/opponent_range/predictor_flow.md tests/test_opponent_range.py tests/test_opponent_range_preflop_context.py
git commit -m "refactor: route opponent range predictor through shared engine"
```

### Task 10: 完成文档与全链路验证

**Files:**
- Modify: `docs/plans/2026-03-07-preflop-engine-refactor-design.md`
- Modify: `docs/plans/2026-03-07-preflop-engine-refactor.md`
- Modify: `src/bayes_poker/strategy/preflop_engine/__init__.py`
- Test: `tests/test_preflop_engine_state.py`
- Test: `tests/test_preflop_engine_mapper.py`
- Test: `tests/test_preflop_engine_tendency.py`
- Test: `tests/test_preflop_engine_calibrator.py`
- Test: `tests/test_preflop_engine_range_engine.py`
- Test: `tests/test_preflop_engine_hero_engine.py`
- Test: `tests/test_preflop_runtime_strategy.py`
- Test: `tests/test_opponent_range.py`

**Step 1: Update docs and exports**

```python
__all__ = [
    "PreflopDecisionState",
    "PreflopNodeMapper",
    "RangeEngine",
    "PreflopHeroEngine",
]
```

**Step 2: Run focused suite**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_state.py tests/test_preflop_engine_mapper.py tests/test_preflop_engine_tendency.py tests/test_preflop_engine_calibrator.py tests/test_preflop_engine_range_engine.py tests/test_preflop_engine_hero_engine.py -q`
Expected: PASS。
Result: PASS, `48 passed`。

**Step 3: Run integration suite**

Run: `timeout 60s uv run pytest tests/test_preflop_runtime_strategy.py tests/test_preflop_runtime_framework.py tests/test_opponent_range.py tests/test_opponent_range_preflop_context.py -q`
Expected: PASS。
Result: PASS, `23 passed, 15 skipped`。

**Step 4: Run compile check**

Run: `timeout 60s uv run python -m compileall src`
Expected: PASS, 无语法错误。
Result: PASS。

**Step 5: Commit**

```bash
git add docs/plans/2026-03-07-preflop-engine-refactor-design.md docs/plans/2026-03-07-preflop-engine-refactor.md src/bayes_poker/strategy/preflop_engine/__init__.py
git commit -m "docs: finalize preflop engine refactor plan"
```
