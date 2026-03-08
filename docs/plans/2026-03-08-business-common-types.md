# 业务公共类型迁移 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将业务公共类型从 `table` 层收拢到 `domain` 层, 统一 `Position`、`PlayerAction`、`Player` 等业务对象的定义与导出。

**Architecture:** 新增 `domain/table.py` 作为业务桌面模型归属层, 将 `Position`、座位顺序工具、`PlayerAction`、`Player` 迁入该模块。`table` 层只保留解析与状态聚合职责, 各调用方改为依赖 `domain` 公共类型。

**Tech Stack:** Python 3.12, dataclasses, pytest, uv

---

### Task 1: 新建公共业务类型模块

**Files:**
- Create: `src/bayes_poker/domain/table.py`
- Modify: `src/bayes_poker/domain/__init__.py`
- Test: `tests/test_table_parser.py`

**Step 1: Write the failing test**

在 `tests/test_table_parser.py` 增加断言, 验证 `domain.table.Position` 与 `domain.table.get_position_by_seat()` 可直接导入并返回预期位置。

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_table_parser.py -q`
Expected: FAIL, 因为 `domain.table` 尚不存在。

**Step 3: Write minimal implementation**

创建 `src/bayes_poker/domain/table.py`, 搬迁:
- `Position`
- `SEAT_ORDER_6MAX`
- `SEAT_ORDER_9MAX`
- `get_position_by_seat`

并在 `domain/__init__.py` 统一导出。

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_table_parser.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/bayes_poker/domain/table.py src/bayes_poker/domain/__init__.py tests/test_table_parser.py
git commit -m "feat: add shared domain table types"
```

### Task 2: 迁移 PlayerAction 与 Player

**Files:**
- Modify: `src/bayes_poker/domain/table.py`
- Modify: `src/bayes_poker/table/observed_state.py`
- Modify: `src/bayes_poker/comm/strategy_history.py`
- Test: `tests/test_strategy_history.py`
- Test: `tests/test_preflop_runtime_framework.py`

**Step 1: Write the failing test**

补测试, 验证 `PlayerAction`、`Player` 可从 `domain.table` 导入并完成序列化/反序列化。

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_strategy_history.py tests/test_preflop_runtime_framework.py -q`
Expected: FAIL, 因为 `domain.table` 还未提供这些数据类。

**Step 3: Write minimal implementation**

将 `PlayerAction`、`Player` 迁入 `domain.table`, 并让 `observed_state.py` 改为复用公共数据类。内部把 `Player.position` 收紧为 `Position | None`, 只在 `from_dict()` 接受字符串输入。

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_strategy_history.py tests/test_preflop_runtime_framework.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/bayes_poker/domain/table.py src/bayes_poker/table/observed_state.py src/bayes_poker/comm/strategy_history.py tests/test_strategy_history.py tests/test_preflop_runtime_framework.py
git commit -m "refactor: move shared player models into domain"
```

### Task 3: 切换业务模块引用到 domain

**Files:**
- Modify: `src/bayes_poker/strategy/runtime/preflop.py`
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/opponent_range/preflop_context.py`
- Modify: `src/bayes_poker/strategy/preflop_engine/state.py`
- Modify: `src/bayes_poker/strategy/preflop_engine/mapper.py`
- Modify: `src/bayes_poker/strategy/preflop_engine/hero_engine.py`
- Modify: `src/bayes_poker/strategy/preflop_parse/parser.py`
- Modify: `src/bayes_poker/strategy/preflop_parse/records.py`
- Modify: `src/bayes_poker/storage/preflop_strategy_repository.py`
- Test: `tests/test_preflop_engine_state.py`
- Test: `tests/test_preflop_engine_mapper.py`
- Test: `tests/test_preflop_runtime_strategy.py`
- Test: `tests/test_opponent_range_preflop_context.py`

**Step 1: Write the failing test**

先改测试导入来源, 让关键策略测试显式依赖 `domain.table.Position`。

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_state.py tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py -q`
Expected: FAIL, 因为实现仍引用旧模块。

**Step 3: Write minimal implementation**

将业务模块里的 `Position/get_position_by_seat/Player/PlayerAction` 导入统一切到 `domain.table`。删除重复的 `TablePosition` 命名别名, 用统一业务命名。

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_state.py tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy src/bayes_poker/storage tests/test_preflop_engine_state.py tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py
git commit -m "refactor: use domain table types across strategy"
```

### Task 4: 收口导出与遗留依赖

**Files:**
- Modify: `src/bayes_poker/table/__init__.py`
- Modify: `src/bayes_poker/table/layout/__init__.py`
- Modify: `src/bayes_poker/table/layout/base.py`
- Modify: `src/bayes_poker/table/parser.py`
- Test: `tests/test_table_parser.py`

**Step 1: Write the failing test**

增加测试, 验证 `table` 层不再拥有 `Position` 定义, 但解析功能保持稳定。

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_table_parser.py -q`
Expected: FAIL

**Step 3: Write minimal implementation**

`table/layout/base.py` 只保留布局对象; `table/__init__.py` 和 `table/layout/__init__.py` 改为最薄导出或不再导出业务类型。`table/parser.py` 改为依赖 `domain` 公共类型。

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_table_parser.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/bayes_poker/table tests/test_table_parser.py
git commit -m "refactor: separate table parsing from shared domain types"
```

### Task 5: 回归验证

**Files:**
- Test: `tests/test_strategy_history.py`
- Test: `tests/test_preflop_runtime_framework.py`
- Test: `tests/test_preflop_engine_state.py`
- Test: `tests/test_preflop_engine_mapper.py`
- Test: `tests/test_preflop_runtime_strategy.py`
- Test: `tests/test_opponent_range_preflop_context.py`
- Test: `tests/test_opponent_range.py`

**Step 1: Run focused regression**

Run: `timeout 60s uv run pytest tests/test_table_parser.py tests/test_strategy_history.py tests/test_preflop_runtime_framework.py tests/test_preflop_engine_state.py tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py tests/test_opponent_range.py -q`
Expected: PASS

**Step 2: Run compile check**

Run: `timeout 60s uv run python -m compileall src`
Expected: PASS

**Step 3: Commit**

```bash
git add -A
git commit -m "test: verify shared domain type migration"
```
