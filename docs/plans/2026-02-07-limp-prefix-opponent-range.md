# Limp Prefix Opponent Range Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `OpponentRangePredictor` 在 `limp` 场景使用“当前 action + 行动前缀”更新范围, 基于 `table_type` 平均玩家统计与策略节点构造梯形信念的 Calling Range.

**Architecture:** 以 `action_prefix` 贯穿 `engine/server -> predictor` 调用链. 在 `opponent_range` 下新增独立的“前缀上下文解析”和“频率填充算法”模块, predictor 只做编排与回退. 复用并抽取 preflop 场景分类逻辑, 保持非 limp 现有行为不变.

**Tech Stack:** Python 3.12, dataclasses, typing, pytest, 现有 `PreflopStrategy` / `PlayerStatsRepository` / `PreFlopParams` / `ActionStats`.

### Task 1: 固化需求与边界的失败测试

**Files:**
- Modify: `tests/test_opponent_range_action_queue.py`
- Modify: `tests/test_opponent_range.py`
- Create: `tests/test_opponent_range_limp_fill.py`

**Step 1: 写失败测试（行动前缀透传）**

```python
def test_dispatcher_passes_action_prefix_to_predictor() -> None:
    ...
    # 断言每次调用都带有当前动作之前的 prefix
```

**Step 2: 运行单测确认失败**

Run: `uv run pytest -q tests/test_opponent_range_action_queue.py::test_dispatcher_passes_action_prefix_to_predictor`
Expected: FAIL, 因为当前 predictor 接口没有 `action_prefix`.

**Step 3: 写失败测试（limp A/B 规则入口）**

```python
def test_limp_uses_table_type_average_stats_and_raise_ev() -> None:
    ...
    # 断言:
    # 1) 平均统计按 table_type 全量聚合
    # 2) EV 取 raise 动作, 多 raise 取最小尺度
```

**Step 4: 运行单测确认失败**

Run: `uv run pytest -q tests/test_opponent_range_limp_fill.py::test_limp_uses_table_type_average_stats_and_raise_ev`
Expected: FAIL, 因为 limp 专用路径尚未实现.

### Task 2: 抽取并复用 preflop 场景分类能力

**Files:**
- Create: `src/bayes_poker/strategy/runtime/preflop_history.py`
- Modify: `src/bayes_poker/strategy/runtime/preflop.py`
- Create: `tests/test_preflop_history_utils.py`

**Step 1: 从 `preflop.py` 抽取可复用函数**

```python
class PreflopScenario(str, Enum):
    RFI_NO_LIMPER = "rfi_no_limper"
    RFI_FACE_LIMPER = "rfi_face_limper"
    THREE_BET = "three_bet"
    FOUR_BET = "four_bet"
    UNKNOWN = "unknown"
```

**Step 2: 在 `preflop.py` 切换为复用新模块**

```python
from bayes_poker.strategy.runtime.preflop_history import infer_preflop_layer
```

**Step 3: 写/补测试覆盖兼容性**

```python
def test_infer_preflop_layer_compatibility() -> None:
    assert infer_preflop_layer("C") == PreflopLayer.RFI
```

**Step 4: 运行测试**

Run: `uv run pytest -q tests/test_preflop_runtime_framework.py tests/test_preflop_history_utils.py`
Expected: PASS.

### Task 3: 实现“前缀 -> PreFlopParams”上下文解析模块

**Files:**
- Create: `src/bayes_poker/strategy/opponent_range/preflop_context.py`
- Create: `tests/test_opponent_range_preflop_context.py`

**Step 1: 新增上下文数据结构**

```python
@dataclass(slots=True)
class OpponentPreflopContext:
    scenario: PreflopScenario
    query_history: str
    params: PreFlopParams | None
```

**Step 2: 实现核心函数**

```python
def build_opponent_preflop_context(
    *,
    player: Player,
    action_prefix: Sequence[PlayerAction],
    table_state: ObservedTableState,
    table_type: TableType,
) -> OpponentPreflopContext:
    ...
```

**Step 3: 处理枚举与位置映射差异**

```python
# domain.ActionType -> player_metrics.ActionType
# BTN/SB/BB/UTG/MP/CO -> player_metrics.Position
```

**Step 4: 运行测试**

Run: `uv run pytest -q tests/test_opponent_range_preflop_context.py`
Expected: PASS.

### Task 4: 实现聚合玩家数据读取

**Files:**
- Create: `src/bayes_poker/strategy/opponent_range/stats_source.py`
- Modify: `tests/test_opponent_range_limp_fill.py`

**Step 1: 实现固定聚合玩家名读取函数**

```python
def get_aggregated_player_stats(
    repo: PlayerStatsRepository,
    table_type: TableType,
) -> PlayerStats | None:
    ...
```

**Step 2: 数据读取规则**

```python
# sixmax 固定读取 player_name="aggregated_sixmax_100"
# 其它 table_type 当前返回 None（保持 YAGNI）
```

**Step 3: 运行测试**

Run: `uv run pytest -q tests/test_opponent_range_limp_fill.py::test_get_aggregated_player_stats_uses_fixed_sixmax_name`
Expected: PASS.

### Task 5: 把频率填充算法提取为独立模块

**Files:**
- Create: `src/bayes_poker/strategy/opponent_range/frequency_fill.py`
- Modify: `src/bayes_poker/strategy/opponent_range/__init__.py`
- Modify: `tests/test_opponent_range_limp_fill.py`

**Step 1: 定义算法入口**

```python
def build_limp_calling_range(
    *,
    node: StrategyNode,
    raise_frequency: float,
    call_frequency: float,
) -> PreflopRange:
    ...
```

**Step 2: 固化 EV 选择规则（你已确认）**

```python
# 仅使用 raise 动作 EV
# 多个 raise 时选 bet_size_bb 最小的动作
```

**Step 3: 实现梯形信念填充**

```python
# 1) 按 raise EV 降序
# 2) 剔除顶端 A%
# 3) 后续先 100% 填到接近 B%
# 4) 对 call 段尾部做线性降权
# 5) 同时从 raise 段尾部引入线性升权
```

**Step 4: 运行测试**

Run: `uv run pytest -q tests/test_opponent_range_limp_fill.py`
Expected: PASS.

### Task 6: predictor 接入 limp 专用路径与回退

**Files:**
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/opponent_range/__init__.py`
- Modify: `tests/test_opponent_range.py`

**Step 1: 扩展接口参数**

```python
def update_range_on_action(..., action_prefix: Sequence[PlayerAction] | None = None) -> None:
    ...
```

**Step 2: `_update_postflop_range` 接入新链路**

```python
# 识别 limp 场景 -> query strategy node -> average stats -> PreFlopParams -> A/B
# 调用 build_limp_calling_range 构造 preflop range
```

**Step 3: 保留非 limp 与数据缺失回退**

```python
# 任一环节失败则走原有 _get_initial_preflop_range 逻辑
```

**Step 4: 运行测试**

Run: `uv run pytest -q tests/test_opponent_range.py`
Expected: PASS.

### Task 7: engine/server 透传行动前缀

**Files:**
- Modify: `src/bayes_poker/strategy/engine.py`
- Modify: `src/bayes_poker/comm/server.py`
- Modify: `tests/test_opponent_range_action_queue.py`

**Step 1: 构造 prefix 并透传**

```python
absolute_idx = processed_offset + rel_idx
action_prefix = observed_state.action_history[:absolute_idx]
predictor.update_range_on_action(player, action, observed_state, action_prefix=action_prefix)
```

**Step 2: 更新测试替身签名**

```python
def update_range_on_action(..., action_prefix=None) -> None:
    ...
```

**Step 3: 断言 prefix 顺序与内容**

```python
assert calls[2].prefix_tokens == ["C", "C"]
```

**Step 4: 运行测试**

Run: `uv run pytest -q tests/test_opponent_range_action_queue.py tests/test_strategy_dispatcher.py`
Expected: PASS.

### Task 8: 全链路回归与文档同步

**Files:**
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`（补充中文 Google 风格注释）
- Modify: `src/bayes_poker/strategy/opponent_range/frequency_fill.py`（补充中文 Google 风格注释）
- Modify: `src/bayes_poker/strategy/opponent_range/preflop_context.py`（补充中文 Google 风格注释）

**Step 1: 执行目标测试集**

Run: `uv run pytest -q tests/test_opponent_range.py tests/test_opponent_range_action_queue.py tests/test_opponent_range_limp_fill.py tests/test_preflop_runtime_framework.py`
Expected: PASS.

**Step 2: 执行语法检查**

Run: `uv run python -m compileall src`
Expected: PASS.

**Step 3: 人工检查回退行为**

```python
# 无 preflop_strategy / 无 stats_repo / 参数缺失都不会抛异常
```

**Step 4: 准备进入实现**

```text
将 tasks.md 对应项逐项勾选为完成, 不执行 git 提交.
```
