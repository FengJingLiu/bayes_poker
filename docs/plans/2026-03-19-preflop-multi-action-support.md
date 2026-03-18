# Preflop Multi-Action Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `strategy_engine` 增加 preflop 多次行动支持, 重点补齐 Hero 已经入池后再次决策的场景, 使 `facing_3bet` 真实场景测试转正, 并为后续更深的 `three_bet+` 链路提供统一框架。

**Architecture:** 保持 `ObservedTableState` 作为唯一事实源, 不新增独立的 `PreflopDecisionSlice` 领域对象。把“当前决策点之前的 preflop 前缀”、“某座位此前动作”、“当前仍存活对手的最近一次动作”、“当前决策点历史 token”等推导统一下沉为 `ObservedTableState` 的只读成员函数, 然后让 `context_builder`、`opponent_pipeline`、`hero_resolver` 全部复用这套状态查询接口。

**Tech Stack:** Python 3.12, `uv`, `pytest`, SQLite `PreflopStrategyRepository`, `ObservedTableState`, `player_metrics.PreFlopParams`, 真实场景测试 `tests/real_scenario/`.

---

## Framework

- **单一事实源**
  - `ObservedTableState` 继续持有原始 `action_history`、`players`、`actor_seat`、`hero_seat`。
  - 所有“当前决策点切片”都由成员函数即时推导, 不保存冗余状态。
- **统一查询接口**
  - 新增只读成员函数, 例如:
    - `get_preflop_actions()`
    - `get_preflop_prefix_before_current_turn()`
    - `get_preflop_prior_actions_for_seat(seat)`
    - `get_preflop_previous_action_for_seat(seat)`
    - `get_live_opponent_last_action_indices_before_current_turn()`
    - `get_preflop_history_tokens_before_current_turn(include_size: bool = False)`
    - `get_active_player_count_before_current_turn()`
- **明确语义约定**
  - `previous_action=FOLD` 在 preflop 统计索引里表示“该玩家此前尚未行动”, 不是“真实上一动作是 fold”。
  - Hero facing 3bet 时, `previous_action` 应为 `RAISE`, 不再落到“未行动”桶。
- **保持底层策略数据不变**
  - SQLite `solver_nodes` 和 `node_mapper` 已支持 `raise_time >= 2`。
  - 本次只修运行时切片和上下文构建, 不改表结构。
- **支持边界**
  - 本次计划支持:
    - Hero 首次决策。
    - Hero open 后 facing 3bet 的再次决策。
    - `three_bet+` 链路中, 已行动且当前仍存活对手的最近一次动作 posterior。
  - 本次不扩展:
    - postflop。
    - limp 后再加注。
    - 超出当前 `PreFlopParams.to_index()` 表达能力的新统计维度。

### Task 1: 为 ObservedTableState 增加 Preflop 决策查询成员函数

**Files:**
- Modify: `src/bayes_poker/table/observed_state.py`
- Test: `tests/test_observed_table_state.py`

**Step 1: Write the failing test**

```python
from __future__ import annotations

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.table.observed_state import ObservedTableState


def _build_players() -> list[Player]:
    return [
        Player(0, "btn", 100.0, 0.0, Position.BTN, is_folded=True),
        Player(1, "sb", 99.5, 0.5, Position.SB, is_folded=True),
        Player(2, "bb", 99.0, 1.0, Position.BB, is_folded=True),
        Player(3, "hero", 97.5, 2.5, Position.UTG),
        Player(4, "villain", 92.0, 8.0, Position.MP),
        Player(5, "co", 100.0, 0.0, Position.CO, is_folded=True),
    ]


def test_observed_state_exposes_reentry_preflop_views() -> None:
    state = ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_players(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
            PlayerAction(5, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(0, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(1, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(2, ActionType.FOLD, 0.0, Street.PREFLOP),
        ],
        state_version=1,
    )

    assert tuple(a.player_index for a in state.get_preflop_prefix_before_current_turn()) == (
        3,
        4,
        5,
        0,
        1,
        2,
    )
    assert state.get_preflop_previous_action_for_seat(3) == ActionType.RAISE
    assert state.get_preflop_previous_action_for_seat(4) == ActionType.RAISE
    assert state.get_preflop_history_tokens_before_current_turn() == "R-R-F-F-F-F"
    assert state.get_live_opponent_last_action_indices_before_current_turn() == ((4, 1),)
    assert state.get_active_player_count_before_current_turn() == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_observed_table_state.py`

Expected: FAIL, 因为这些成员函数还不存在。

**Step 3: Write minimal implementation**

```python
def get_preflop_actions(self) -> tuple[PlayerAction, ...]:
    return tuple(
        action for action in self.action_history if action.street == Street.PREFLOP
    )


def get_preflop_prefix_before_current_turn(self) -> tuple[PlayerAction, ...]:
    return self.get_preflop_actions()


def get_preflop_prior_actions_for_seat(
    self,
    seat: int,
) -> tuple[PlayerAction, ...]:
    return tuple(
        action
        for action in self.get_preflop_prefix_before_current_turn()
        if action.player_index == seat
    )


def get_preflop_previous_action_for_seat(self, seat: int) -> ActionType | None:
    prior_actions = self.get_preflop_prior_actions_for_seat(seat)
    if not prior_actions:
        return None
    return prior_actions[-1].action_type
```

并补充:
- 历史 token 构造。
- 当前仍存活对手最近一次动作索引收集。
- 当前决策点有效玩家数计算。

要求:
- 所有新增方法都加中文 Google 风格 docstring。
- 这些方法必须是纯只读查询, 不修改状态。
- 不把 `NodeContext` 或 `PreFlopParams` 放进 `ObservedTableState`。

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_observed_table_state.py`

Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/table/observed_state.py tests/test_observed_table_state.py
git commit -m "feat: add preflop decision view methods to observed state"
```

### Task 2: 让 Context Builder 基于 ObservedTableState 成员函数构建 reentry 上下文

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/context_builder.py`
- Test: `tests/test_strategy_engine_v2_context_builder.py`
- Reference: `src/bayes_poker/player_metrics/params.py`
- Reference: `src/bayes_poker/player_metrics/builder.py`

**Step 1: Write the failing test**

```python
def test_context_builder_supports_hero_open_facing_3bet_reentry() -> None:
    observed_state = ObservedTableState(
        table_id="t_reentry",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h_reentry",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_sixmax_players(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
            PlayerAction(5, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(0, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(1, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(2, ActionType.FOLD, 0.0, Street.PREFLOP),
        ],
        state_version=1,
    )

    context = build_player_node_context(observed_state)

    assert context.node_context.actor_position == Position.UTG
    assert context.node_context.aggressor_position == Position.MP
    assert context.node_context.raise_time == 2
    assert context.node_context.call_count == 0
    assert context.params.previous_action == MetricsActionType.RAISE
    assert context.params.num_raises == 2
    assert context.params.num_active_players == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_strategy_engine_v2_context_builder.py -k reentry`

Expected: FAIL, 当前实现会报 `UnsupportedContextError("当前最小实现只支持 actor 的首次翻前行动")`。

**Step 3: Write minimal implementation**

```python
prefix_actions = list(observed_state.get_preflop_prefix_before_current_turn())
previous_action = observed_state.get_preflop_previous_action_for_seat(actor_seat)
active_player_count = observed_state.get_active_player_count_before_current_turn()

params = PreFlopParams(
    table_type=table_type,
    position=metrics_position,
    num_callers=min(num_callers, 1),
    num_raises=min(num_raises, 2),
    num_active_players=max(2, active_player_count),
    previous_action=(
        MetricsActionType.FOLD
        if previous_action is None
        else MetricsActionType(previous_action.value)
    ),
    in_position_on_flop=_is_in_position_on_flop(...),
)
```

要求:
- 删除 `_build_first_action_prefix()` 对 actor 首次行动的硬拒绝。
- 保留 `previous_action=FOLD` 作为“此前尚未行动”的约定值。
- `num_active_players` 不能再硬编码为整桌人数, 必须基于当前决策点存活人数。
- 保留 `limp 后加注` 的拒绝逻辑, 不在本任务顺手扩展。

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_strategy_engine_v2_context_builder.py`

Expected: PASS, 旧用例和新增 reentry 用例都通过。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/context_builder.py tests/test_strategy_engine_v2_context_builder.py
git commit -m "feat: support reentry context from observed state"
```

### Task 3: 让 Opponent Pipeline 基于“当前仍存活对手的最近一次动作”建模

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py`
- Test: `tests/test_strategy_engine_v2_opponent_pipeline.py`
- Reference: `src/bayes_poker/table/observed_state.py`

**Step 1: Write the failing test**

```python
def test_opponent_pipeline_uses_latest_live_opponent_action_for_reentry_node(
    tmp_path: Path,
) -> None:
    observed_state = _build_hero_open_facing_3bet_state()

    context = pipeline.process_hero_snapshot(
        session_id="reentry",
        observed_state=observed_state,
    )

    assert context.player_summaries[4]["status"] == "posterior"
    assert 4 in context.player_ranges
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_strategy_engine_v2_opponent_pipeline.py -k reentry`

Expected: FAIL, 当前 pipeline 只按“首次动作”构造 prefix。

**Step 3: Write minimal implementation**

```python
latest_indices = observed_state.get_live_opponent_last_action_indices_before_current_turn()

for seat, action_index in latest_indices:
    player = _find_player_by_seat(observed_state.players, seat)
    prefix = list(observed_state.get_preflop_prefix_before_action_index(action_index))
    action = observed_state.action_history[action_index]
    prior_policy = self._build_initial_prior_range(
        player=player,
        observed_state=observed_state,
        decision_prefix=prefix,
    )
```

要求:
- 不再把“对手第一次动作”当成唯一事实来源。
- 只对当前决策点之前仍存活的对手保留 posterior。
- 顺序必须按最近动作索引排序, 保证调试输出稳定。

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_strategy_engine_v2_opponent_pipeline.py`

Expected: PASS, 现有缓存/校准/范围重分配测试不能回归。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py tests/test_strategy_engine_v2_opponent_pipeline.py
git commit -m "feat: use latest live opponent actions in pipeline"
```

### Task 4: 升级 Hero Resolver 以支持 reentry 历史与对手校验

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/hero_resolver.py`
- Test: `tests/test_strategy_engine_v2_hero_resolver.py`
- Reference: `src/bayes_poker/table/observed_state.py`

**Step 1: Write the failing test**

```python
def test_hero_resolver_supports_facing_3bet_reentry(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo_with_facing_3bet_node(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
    observed_state = _build_hero_open_facing_3bet_state()
    session_context = _build_session_context_with_posterior_seats(posterior_seats=(4,))

    decision = resolver.resolve(
        observed_state=observed_state,
        session_context=session_context,
    )

    assert isinstance(decision, RecommendationDecision)
    assert "matched_history=R2.5-R8-F-F-F-F" in decision.notes
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_strategy_engine_v2_hero_resolver.py -k facing_3bet_reentry`

Expected: FAIL, 当前 resolver 在 Hero 第一次动作处就停止收集历史。

**Step 3: Write minimal implementation**

```python
def _build_acted_history_actions(observed_state: ObservedTableState) -> str:
    return observed_state.get_preflop_history_tokens_before_current_turn()


def _collect_acted_live_opponent_seats(
    observed_state: ObservedTableState,
) -> tuple[int, ...]:
    last_actions = observed_state.get_live_opponent_last_action_indices_before_current_turn()
    return tuple(seat for seat, _ in last_actions)
```

要求:
- `hero_resolver` 不再在遇到 Hero 第一条历史动作时提前 `break`。
- `matched_history` 必须反映当前决策点之前的完整 preflop 前缀。
- 已行动对手校验必须和 `opponent_pipeline` 使用同一套 seat 集合。

**Step 4: Run test to verify it passes**

Run: `uv run pytest -q tests/test_strategy_engine_v2_hero_resolver.py`

Expected: PASS, 新增 reentry 用例通过, 旧的 unsupported/no-match 用例仍保持原有语义。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/strategy_engine/hero_resolver.py tests/test_strategy_engine_v2_hero_resolver.py
git commit -m "feat: support hero reentry in resolver"
```

### Task 5: 打通 Facing 3-Bet 真实场景并更新文档

**Files:**
- Modify: `src/bayes_poker/strategy/AGENTS.md`
- Modify: `docs/hero_decision_pipeline.md`
- Verify: `tests/real_scenario/test_facing_3bet_all_positions.py`
- Verify: `tests/real_scenario/test_3bet_all_positions.py`
- Verify: `tests/real_scenario/test_4bet_all_positions.py`

**Step 1: Write the failing test**

直接使用现有 `tests/real_scenario/test_facing_3bet_all_positions.py` 作为验收, 不新增真实场景文件。

**Step 2: Run test to verify it fails**

Run: `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q -x tests/real_scenario/test_facing_3bet_all_positions.py`

Expected: 当前主分支 FAIL, 原因是 `UnsupportedScenarioDecision("当前最小实现只支持 actor 的首次翻前行动")`。

**Step 3: Write minimal implementation**

```markdown
- 更新 `src/bayes_poker/strategy/AGENTS.md`:
  - 删除“仅支持首次行动”的表述。
  - 改为“支持首次行动 + actor reentry 的 preflop 决策, 仍不支持 limp-after-raise / postflop / HU”。
- 更新 `docs/hero_decision_pipeline.md`:
  - 新增基于 `ObservedTableState` 成员函数的“current turn views”说明。
  - 说明 opponent pipeline 现在基于当前决策点前、仍存活对手的最近动作做 posterior。
```

**Step 4: Run test to verify it passes**

Run: `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q tests/real_scenario/test_facing_3bet_all_positions.py`

Expected: PASS。

然后跑回归:

Run: `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q tests/real_scenario/test_3bet_all_positions.py tests/real_scenario/test_4bet_all_positions.py`

Expected: PASS, `3bet` 和 `4bet` 不能回归。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/AGENTS.md docs/hero_decision_pipeline.md
git commit -m "docs: update preflop reentry support matrix"
```

### Task 6: 全量验证并整理交付说明

**Files:**
- Verify: `tests/test_observed_table_state.py`
- Verify: `tests/test_strategy_engine_v2_context_builder.py`
- Verify: `tests/test_strategy_engine_v2_opponent_pipeline.py`
- Verify: `tests/test_strategy_engine_v2_hero_resolver.py`
- Verify: `tests/test_strategy_engine_v2_mapper.py`
- Verify: `tests/real_scenario/test_facing_3bet_all_positions.py`

**Step 1: Write the failing test**

本任务不新增测试, 直接把前面各任务的验收命令汇总成最终验证清单。

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest -q \
  tests/test_observed_table_state.py \
  tests/test_strategy_engine_v2_context_builder.py \
  tests/test_strategy_engine_v2_opponent_pipeline.py \
  tests/test_strategy_engine_v2_hero_resolver.py \
  tests/test_strategy_engine_v2_mapper.py
```

Expected: 任一模块有遗漏时 FAIL, 阻止误收尾。

**Step 3: Write minimal implementation**

```markdown
- 修复剩余命名、注释、夹具问题。
- 确保新增成员函数、helper、测试都带中文 Google 风格 docstring 和类型标注。
- 交付说明必须明确:
  - `ObservedTableState` 新增了哪些 preflop 查询接口。
  - `previous_action=FOLD` 的约定语义。
  - 仍未支持的边界。
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest -q \
  tests/test_observed_table_state.py \
  tests/test_strategy_engine_v2_context_builder.py \
  tests/test_strategy_engine_v2_opponent_pipeline.py \
  tests/test_strategy_engine_v2_hero_resolver.py \
  tests/test_strategy_engine_v2_mapper.py

BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q \
  tests/real_scenario/test_facing_3bet_all_positions.py \
  tests/real_scenario/test_3bet_all_positions.py \
  tests/real_scenario/test_4bet_all_positions.py
```

Expected: 全部 PASS。

**Step 5: Commit**

```bash
git add src tests docs
git commit -m "feat: add preflop multi-action support"
```
