# Low Sample Player Stats Notebook Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `notebooks/player_stats_analysis.ipynb` 追加一个低样本玩家章节，固定展示同一玩家在平滑与非平滑统计下的差异。

**Architecture:** 先新增一个很小的 Python 辅助模块，负责筛选低样本玩家和生成对比 DataFrame，再让 notebook 末尾追加展示单元复用这些函数。这样可以先写单元测试锁定筛选和对比逻辑，再做 notebook 集成，避免直接把复杂逻辑塞进 ipynb JSON。

**Tech Stack:** Python 3.12, pandas, pytest, Jupyter Notebook JSON, SQLite, PlayerStatsRepository

---

### Task 1: 新增低样本玩家分析辅助模块

**Files:**
- Create: `src/bayes_poker/player_metrics/analysis_helpers.py`
- Test: `tests/test_player_metrics_analysis_helpers.py`

**Step 1: Write the failing test**

```python
def test_build_core_stats_comparison_returns_raw_and_smoothed_rows() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: FAIL with missing module or missing function

**Step 3: Write minimal implementation**

```python
def build_core_stats_comparison(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: PASS

### Task 2: 实现低样本玩家筛选与节点差异排序

**Files:**
- Modify: `src/bayes_poker/player_metrics/analysis_helpers.py`
- Test: `tests/test_player_metrics_analysis_helpers.py`

**Step 1: Write the failing test**

```python
def test_select_low_sample_player_prefers_larger_probability_shift() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: FAIL with incorrect selection result

**Step 3: Write minimal implementation**

```python
def select_low_sample_player(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: PASS

### Task 3: 追加 notebook 展示单元

**Files:**
- Modify: `notebooks/player_stats_analysis.ipynb`
- Test: `tests/test_player_metrics_analysis_helpers.py`

**Step 1: Write the failing test**

```python
def test_notebook_contains_low_sample_comparison_section() -> None:
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: FAIL because notebook section does not exist yet

**Step 3: Write minimal implementation**

```python
# 在 notebook 末尾追加 markdown 和 code cells
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: PASS

### Task 4: 运行端到端校验

**Files:**
- Verify: `notebooks/player_stats_analysis.ipynb`
- Verify: `src/bayes_poker/player_metrics/analysis_helpers.py`
- Verify: `tests/test_player_metrics_analysis_helpers.py`

**Step 1: Run focused tests**

Run: `source .venv/bin/activate && pytest tests/test_player_metrics_analysis_helpers.py -q`
Expected: PASS

**Step 2: Validate notebook JSON**

Run: `python3 - <<'PY' ...`
Expected: notebook JSON loads successfully

**Step 3: Smoke test notebook helper logic**

Run: `source .venv/bin/activate && python3 - <<'PY' ...`
Expected: prints chosen player name and non-empty comparison tables
