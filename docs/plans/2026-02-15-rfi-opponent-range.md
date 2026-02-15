# RFI Opponent Range Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `OpponentRangePredictor` 中实现 `RFI_NO_LIMPER` 与 `RFI_HAVE_LIMPER` 的 prefix 频率驱动 EV 裁剪范围逻辑。

**Architecture:** 新增 RFI 专用私有构建链路。以 `current_prefix` 构建统计参数并读取 RFI 频率, 以 `decision_prefix` 查询 preflop strategy 节点并聚合 raise EV, 最终按目标频率裁剪 169 范围。分支构建失败时回退现有 action-scale。

**Tech Stack:** Python 3.12, pytest, 现有 `PreflopStrategy` / `PlayerStats` / `PreflopRange` 模型。

---

### Task 1: 新增失败测试（RFI_NO_LIMPER）

**Files:**
- Modify: `tests/test_opponent_range.py`

**Step 1: Write the failing test**

```python
def test_rfi_no_limper_uses_prefix_frequency_and_ev_rank() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -k rfi_no_limper -q`
Expected: FAIL, 原因是当前逻辑未使用 prefix 统计 + EV 裁剪。

**Step 3: Write minimal implementation**

```python
# predictor.py
# 先占位新增 RFI builder 接口并在分支接入
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -k rfi_no_limper -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add tests/test_opponent_range.py src/bayes_poker/strategy/opponent_range/predictor.py
git commit -m "feat: support rfi-no-limper prefix-ev range rebuild"
```

### Task 2: 新增失败测试（RFI_HAVE_LIMPER）

**Files:**
- Modify: `tests/test_opponent_range.py`

**Step 1: Write the failing test**

```python
def test_rfi_have_limper_uses_prefix_frequency_and_ev_rank() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -k rfi_have_limper -q`
Expected: FAIL, 原因同上。

**Step 3: Write minimal implementation**

```python
# predictor.py
# 完整实现 RFI_HAVE_LIMPER 分支走 RFI 专用 builder
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -k rfi_have_limper -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add tests/test_opponent_range.py src/bayes_poker/strategy/opponent_range/predictor.py
git commit -m "feat: support rfi-have-limper prefix-ev range rebuild"
```

### Task 3: 重构与回归验证

**Files:**
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/opponent_range/predictor_flow.md`
- Modify: `tests/test_opponent_range.py`

**Step 1: Refactor helpers**

```python
# 提炼: stats 读取, 决策节点查询, EV 聚合, 频率裁剪
```

**Step 2: Run focused tests**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -k "rfi or limp_preflop" -q`
Expected: PASS。

**Step 3: Run full file tests**

Run: `timeout 60s uv run pytest tests/test_opponent_range.py -q`
Expected: PASS。

**Step 4: Run related context tests**

Run: `timeout 60s uv run pytest tests/test_opponent_range_preflop_context.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/opponent_range/predictor.py src/bayes_poker/strategy/opponent_range/predictor_flow.md tests/test_opponent_range.py
git commit -m "feat: implement rfi range rebuild with prefix stats and ev ranking"
```
