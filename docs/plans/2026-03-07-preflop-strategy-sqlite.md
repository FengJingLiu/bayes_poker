# Preflop 策略 SQLite 化与 Mapper 主链重构 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `strategy/preflop_parse` 重构为面向 sqlite 的结构化策略库, 并让 `mapper` 与 `solver_prior` 完全切换到 `state -> mapper -> solver_prior` 主链, 不再依赖 `history` 查询和 `nodes_by_stack`。

**Architecture:** 解析阶段将策略目录 JSON 转换为 `solver_nodes + solver_actions` 结构化记录并落到 sqlite。运行时通过 `PreflopStrategyRepository` 按 `action_family` 等匹配字段读取候选节点, `mapper` 继续负责距离排序和价格修正, `solver_prior` 按候选 `node_id` 批量聚合动作。

**Tech Stack:** Python 3.12, sqlite3, pytest, uv, 现有 `PreflopRange`、`PreflopDecisionState`、`PreflopNodeMapper`、`SolverPriorBuilder`。

---

### Task 1: 建立范围向量序列化层

**Files:**
- Create: `src/bayes_poker/strategy/preflop_parse/serialization.py`
- Test: `tests/test_preflop_parse_serialization.py`

**Step 1: Write the failing test**

```python
def test_encode_and_decode_preflop_range_round_trip() -> None:
    preflop_range = PreflopRange(
        strategy=[0.25] * RANGE_169_LENGTH,
        evs=[1.5] * RANGE_169_LENGTH,
    )

    encoded = encode_preflop_range(preflop_range)
    decoded = decode_preflop_range(*encoded)

    assert decoded.strategy[0] == pytest.approx(0.25, abs=1e-6)
    assert decoded.evs[-1] == pytest.approx(1.5, abs=1e-6)
```

```python
def test_decode_preflop_range_rejects_invalid_blob_length() -> None:
    with pytest.raises(ValueError):
        decode_preflop_range(b"bad", b"bad")
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_serialization.py -q`
Expected: FAIL, 因为 `serialization.py` 尚不存在。

**Step 3: Write minimal implementation**

```python
def encode_preflop_range(preflop_range: PreflopRange) -> tuple[bytes, bytes]:
    ...

def decode_preflop_range(strategy_blob: bytes, ev_blob: bytes) -> PreflopRange:
    ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_serialization.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_parse/serialization.py tests/test_preflop_parse_serialization.py
git commit -m "feat: add preflop range sqlite serialization"
```

### Task 2: 定义 sqlite 导入记录模型

**Files:**
- Create: `src/bayes_poker/strategy/preflop_parse/records.py`
- Modify: `src/bayes_poker/strategy/preflop_parse/parser.py`
- Test: `tests/test_preflop_parse_records.py`

**Step 1: Write the failing test**

```python
def test_parse_strategy_node_records_extracts_mapper_fields() -> None:
    node_record, action_records = parse_strategy_node_records(
        data=sample_data,
        history_full="R2-C",
        source_file="test.json",
    )

    assert node_record.history_full == "R2-C"
    assert node_record.action_family == "CALL_VS_OPEN"
    assert node_record.call_count == 1
    assert node_record.raise_size_bb == pytest.approx(2.0)
    assert len(action_records) == 2
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_records.py -q`
Expected: FAIL, 因为记录模型和新解析入口尚未存在。

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class ParsedStrategyNodeRecord:
    stack_bb: int
    history_full: str
    action_family: str
    actor_position: str
```

```python
def parse_strategy_node_records(...) -> tuple[ParsedStrategyNodeRecord, tuple[ParsedStrategyActionRecord, ...]]:
    ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_records.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_parse/records.py src/bayes_poker/strategy/preflop_parse/parser.py tests/test_preflop_parse_records.py
git commit -m "feat: add parsed preflop strategy records"
```

### Task 3: 实现 sqlite 仓库 schema 与基础读写

**Files:**
- Create: `src/bayes_poker/storage/preflop_strategy_repository.py`
- Test: `tests/test_preflop_strategy_repository.py`

**Step 1: Write the failing test**

```python
def test_repository_initializes_schema_and_inserts_source() -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()

    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )

    assert source_id > 0
    assert repo.list_sources()[0].strategy_name == "Cash6m50zGeneral"
```

```python
def test_repository_reads_candidates_and_actions_by_node_id() -> None:
    ...
    assert len(repo.list_candidates(...)) == 1
    assert len(repo.get_actions_for_nodes((node_id,))) == 2
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_strategy_repository.py -q`
Expected: FAIL, 因为 repository 尚未实现。

**Step 3: Write minimal implementation**

```python
class PreflopStrategyRepository:
    def connect(self) -> None:
        ...

    def upsert_source(...) -> int:
        ...

    def insert_nodes(...) -> dict[str, int]:
        ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_strategy_repository.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/storage/preflop_strategy_repository.py tests/test_preflop_strategy_repository.py
git commit -m "feat: add preflop strategy sqlite repository"
```

### Task 4: 打通目录到 sqlite 的导入链路

**Files:**
- Create: `src/bayes_poker/strategy/preflop_parse/importer.py`
- Create: `src/bayes_poker/strategy/preflop_parse/loader.py`
- Modify: `src/bayes_poker/strategy/preflop_parse/__init__.py`
- Test: `tests/test_preflop_parse_importer.py`

**Step 1: Write the failing test**

```python
def test_import_strategy_directory_builds_sqlite_database(tmp_path: Path) -> None:
    db_path = tmp_path / "strategy.db"

    import_strategy_directory_to_sqlite(
        strategy_dir=FIXTURES_DIR / "Cash6m50zGeneral",
        db_path=db_path,
    )

    repo = PreflopStrategyRepository(db_path)
    repo.connect()
    assert repo.list_sources()
    assert repo.count_nodes() > 0
    assert repo.count_actions() > 0
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_importer.py -q`
Expected: FAIL, 因为 importer 和 loader 尚未实现。

**Step 3: Write minimal implementation**

```python
def import_strategy_directory_to_sqlite(strategy_dir: Path, db_path: Path) -> None:
    ...

def build_preflop_strategy_db(strategy_dir: Path, db_path: Path) -> Path:
    ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_importer.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_parse/importer.py src/bayes_poker/strategy/preflop_parse/loader.py src/bayes_poker/strategy/preflop_parse/__init__.py tests/test_preflop_parse_importer.py
git commit -m "feat: add preflop strategy sqlite importer"
```

### Task 5: 将 mapper 切到 sqlite 候选查询

**Files:**
- Modify: `src/bayes_poker/strategy/preflop_engine/mapper.py`
- Modify: `tests/test_preflop_engine_mapper.py`
- Test: `tests/test_preflop_engine_mapper.py`

**Step 1: Write the failing test**

```python
def test_mapper_reads_candidates_from_repository() -> None:
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(state)

    assert context.matched_node_id is not None
    assert context.candidate_node_ids == (expected_node_id,)
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: FAIL, 因为 `mapper` 仍依赖 `PreflopStrategy` 和 `nodes_by_stack`。

**Step 3: Write minimal implementation**

```python
class PreflopNodeMapper:
    def __init__(self, *, repository: PreflopStrategyRepository, source_id: int, stack_bb: int, max_candidates: int = 2) -> None:
        ...

    def map_state(self, state: PreflopDecisionState) -> MappedSolverContext:
        ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/mapper.py tests/test_preflop_engine_mapper.py
git commit -m "refactor: load preflop mapper candidates from sqlite"
```

### Task 6: 将 solver_prior 切到 node_id 批量取动作

**Files:**
- Modify: `src/bayes_poker/strategy/preflop_engine/solver_prior.py`
- Modify: `tests/test_preflop_engine_mapper.py`
- Test: `tests/test_preflop_engine_mapper.py`

**Step 1: Write the failing test**

```python
def test_solver_prior_batches_actions_by_candidate_node_ids() -> None:
    policy = SolverPriorBuilder(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    ).build_policy(context)

    assert policy.action_names == ("F", "C", "R9.5")
    assert policy.actions[1].blended_frequency > 0.0
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: FAIL, 因为 `solver_prior` 仍按 `history -> get_node()` 读取动作。

**Step 3: Write minimal implementation**

```python
class SolverPriorBuilder:
    def __init__(self, *, repository: PreflopStrategyRepository, source_id: int, stack_bb: int, distance_tau: float = 1.0) -> None:
        ...
```

```python
actions_by_node_id = repository.get_actions_for_nodes(context.candidate_node_ids)
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_engine_mapper.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_engine/solver_prior.py tests/test_preflop_engine_mapper.py
git commit -m "refactor: batch solver prior reads from sqlite"
```

### Task 7: 清理 preflop_parse 对外接口并退役 query.py

**Files:**
- Modify: `src/bayes_poker/strategy/preflop_parse/__init__.py`
- Modify: `src/bayes_poker/strategy/__init__.py`
- Delete: `src/bayes_poker/strategy/preflop_parse/query.py`
- Delete: `tests/test_query.py`
- Modify: `tests/test_preflop_strategy.py`

**Step 1: Write the failing test**

```python
def test_preflop_parse_exports_sqlite_loader_only() -> None:
    from bayes_poker.strategy.preflop_parse import build_preflop_strategy_db

    assert build_preflop_strategy_db is not None
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_strategy.py -q`
Expected: FAIL, 因为导出面仍围绕旧的 query 和内存树设计。

**Step 3: Write minimal implementation**

```python
__all__ = [
    "build_preflop_strategy_db",
    "import_strategy_directory_to_sqlite",
    "ParsedStrategyNodeRecord",
    "ParsedStrategyActionRecord",
]
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_strategy.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/preflop_parse/__init__.py src/bayes_poker/strategy/__init__.py tests/test_preflop_strategy.py
git rm src/bayes_poker/strategy/preflop_parse/query.py tests/test_query.py
git commit -m "refactor: retire history-based preflop query path"
```

### Task 8: 调整运行时入口到 sqlite 主链

**Files:**
- Modify: `src/bayes_poker/strategy/runtime/preflop.py`
- Modify: `src/bayes_poker/strategy/opponent_range/predictor.py`
- Modify: `src/bayes_poker/strategy/runtime/__init__.py`
- Test: `tests/test_preflop_runtime_strategy.py`
- Test: `tests/test_opponent_range_preflop_context.py`

**Step 1: Write the failing tests**

```python
def test_runtime_preflop_strategy_uses_sqlite_backed_mapper() -> None:
    strategy = create_preflop_strategy_from_sqlite(...)
    response = strategy(payload)
    assert response["strategy_source"] == "preflop_engine"
```

```python
def test_opponent_range_predictor_uses_repository_backed_solver_prior() -> None:
    predictor = create_predictor(...)
    assert predictor.preflop_strategy_repository is not None
```

**Step 2: Run tests to verify they fail**

Run: `timeout 60s uv run pytest tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py -q`
Expected: FAIL, 因为运行时入口仍依赖旧的 `PreflopStrategy` 主链。

**Step 3: Write minimal implementation**

```python
def load_preflop_strategy_repository(db_path: Path) -> PreflopStrategyRepository:
    ...
```

```python
mapper = PreflopNodeMapper(repository=repo, source_id=source_id, stack_bb=stack_bb)
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add src/bayes_poker/strategy/runtime/preflop.py src/bayes_poker/strategy/opponent_range/predictor.py src/bayes_poker/strategy/runtime/__init__.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py
git commit -m "refactor: route preflop runtime through sqlite mapper chain"
```

### Task 9: 跑端到端导入与主链回归测试

**Files:**
- Modify: `tests/test_preflop_engine_mapper.py`
- Modify: `tests/test_preflop_runtime_strategy.py`
- Create: `tests/test_preflop_sqlite_integration.py`

**Step 1: Write the failing test**

```python
def test_fixture_strategy_directory_round_trips_through_sqlite_mapper_and_solver_prior(tmp_path: Path) -> None:
    db_path = build_preflop_strategy_db(FIXTURES_DIR / "Cash6m50zGeneral", tmp_path / "strategy.db")
    repo = open_preflop_strategy_repository(db_path)
    context = mapper.map_state(state)
    policy = solver_prior.build_policy(context)

    assert context.candidate_node_ids
    assert policy.actions
```

**Step 2: Run test to verify it fails**

Run: `timeout 60s uv run pytest tests/test_preflop_sqlite_integration.py -q`
Expected: FAIL, 因为 sqlite 主链尚未完全接通。

**Step 3: Write minimal implementation**

```python
def test_fixture_strategy_directory_round_trips_through_sqlite_mapper_and_solver_prior(...) -> None:
    ...
```

**Step 4: Run test to verify it passes**

Run: `timeout 60s uv run pytest tests/test_preflop_sqlite_integration.py -q`
Expected: PASS。

**Step 5: Commit**

```bash
git add tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_preflop_sqlite_integration.py
git commit -m "test: add sqlite-backed preflop integration coverage"
```

### Task 10: 完成全量验证与文档收口

**Files:**
- Modify: `docs/plans/2026-03-07-preflop-strategy-sqlite-design.md`
- Modify: `docs/plans/2026-03-07-preflop-strategy-sqlite.md`

**Step 1: Run focused verification**

Run: `timeout 60s uv run pytest tests/test_preflop_parse_serialization.py tests/test_preflop_parse_records.py tests/test_preflop_strategy_repository.py tests/test_preflop_parse_importer.py tests/test_preflop_engine_mapper.py tests/test_preflop_runtime_strategy.py tests/test_opponent_range_preflop_context.py tests/test_preflop_sqlite_integration.py -q`
Expected: PASS。

**Step 2: Run syntax verification**

Run: `timeout 60s uv run python -m compileall src`
Expected: PASS。

**Step 3: Update docs to reflect final implementation details**

```markdown
- 记录实际 schema、入口函数和已删除的旧接口。
- 确认 `query.py` 已退役, 运行时只剩 sqlite 主链。
```

**Step 4: Commit**

```bash
git add docs/plans/2026-03-07-preflop-strategy-sqlite-design.md docs/plans/2026-03-07-preflop-strategy-sqlite.md
git commit -m "docs: finalize preflop strategy sqlite refactor plan"
```
