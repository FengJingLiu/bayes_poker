from __future__ import annotations

import json
from pathlib import Path

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.preflop_engine.state import ActionFamily as LegacyActionFamily
from bayes_poker.strategy.preflop_parse.loader import (
    build_preflop_strategy_db,
    open_preflop_strategy_repository,
)
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.core_types import NodeContext
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository


REAL_PREFLOP_STRATEGY_SOURCE_NAMES: tuple[str, ...] = (
    "Cash6m50zGeneral",
    "Cash6m50zGeneral25Open3betV2",
    "Cash6m50zGeneral3betV2",
    "Cash6m50zSimple25Open_SimpleIP",
    "Cash6m50zSimple_SimpleIP",
)


def _make_node_record(
    *,
    history_full: str = "R2-C",
    stack_bb: int = 100,
) -> ParsedStrategyNodeRecord:
    return ParsedStrategyNodeRecord(
        stack_bb=stack_bb,
        history_full=history_full,
        history_actions="R-C",
        history_token_count=2,
        acting_position="CO",
        source_file="test.json",
        action_family=LegacyActionFamily.CALL_VS_OPEN,
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=5.5,
        raise_size_bb=2.0,
        is_in_position=True,
    )


def _make_action_records() -> tuple[ParsedStrategyActionRecord, ...]:
    base_range = PreflopRange(strategy=[0.5] * 169, evs=[0.1] * 169)
    return (
        ParsedStrategyActionRecord(
            order_index=0,
            action_code="F",
            action_type="FOLD",
            bet_size_bb=None,
            is_all_in=False,
            total_frequency=0.2,
            next_position="",
            preflop_range=base_range,
            total_ev=0.0,
            total_combos=10.0,
        ),
        ParsedStrategyActionRecord(
            order_index=1,
            action_code="C",
            action_type="CALL",
            bet_size_bb=None,
            is_all_in=False,
            total_frequency=0.8,
            next_position="",
            preflop_range=base_range,
            total_ev=0.1,
            total_combos=40.0,
        ),
    )


def _make_node_context() -> NodeContext:
    """构建测试用节点上下文.

    Returns:
        固定的 CALL_VS_OPEN 场景节点上下文.
    """

    return NodeContext(
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=5.5,
        raise_size_bb=2.0,
    )


def test_repository_adapter_candidate_lookup_and_stack_resolution(
    tmp_path: Path,
) -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=2,
    )
    node_ids = repo.insert_nodes(
        source_id=source_id,
        node_records=(
            _make_node_record(history_full="R2-C", stack_bb=100),
            _make_node_record(history_full="R3-C", stack_bb=50),
        ),
    )
    repo.insert_actions(
        node_id=node_ids["R2-C"],
        action_records=_make_action_records(),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()

    sources = adapter.resolve_source()
    assert len(sources) == 1
    source = sources[0]
    resolved_stack = adapter.resolve_stack_bb(
        source_id=source.source_id, requested_stack_bb=87
    )
    candidates = adapter.load_candidates(
        source_id=source.source_id,
        stack_bb=100,
        node_context=_make_node_context(),
    )
    actions = adapter.load_actions((node_ids["R2-C"],))

    assert source.format_version == 2
    assert resolved_stack == 100
    assert len(candidates) == 1
    assert candidates[0].history_full == "R2-C"
    assert candidates[0].raise_time == 1
    assert candidates[0].pot_size == pytest.approx(5.5)
    assert len(actions[node_ids["R2-C"]]) == 2
    assert actions[node_ids["R2-C"]][1].action_code == "C"

    adapter.close()


def test_repository_adapter_resolve_source_supports_multiple_sources(
    tmp_path: Path,
) -> None:
    """验证 resolve_source 支持通过多个选择器返回多个策略源.

    Args:
        tmp_path: pytest 临时目录.
    """

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    first_source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=2,
    )
    second_source_id = repo.upsert_source(
        strategy_name="Cash6m50zAggressive",
        source_dir="/tmp/Cash6m50zAggressive",
        format_version=2,
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()

    matched_by_ids = adapter.resolve_source(
        source_id=(first_source_id, second_source_id)
    )
    matched_by_names = adapter.resolve_source(
        strategy_name=("Cash6m50zGeneral", "Cash6m50zAggressive")
    )

    assert tuple(source.source_id for source in matched_by_ids) == (
        first_source_id,
        second_source_id,
    )
    assert tuple(source.strategy_name for source in matched_by_names) == (
        "Cash6m50zGeneral",
        "Cash6m50zAggressive",
    )

    adapter.close()


def test_repository_adapter_resolve_stack_bb_supports_multiple_sources(
    tmp_path: Path,
) -> None:
    """验证 resolve_stack_bb 支持多策略源联合解析.

    Args:
        tmp_path: pytest 临时目录.
    """

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    first_source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=2,
    )
    second_source_id = repo.upsert_source(
        strategy_name="Cash6m50zAggressive",
        source_dir="/tmp/Cash6m50zAggressive",
        format_version=2,
    )
    repo.insert_nodes(
        source_id=first_source_id,
        node_records=(_make_node_record(history_full="R2-C", stack_bb=80),),
    )
    repo.insert_nodes(
        source_id=second_source_id,
        node_records=(_make_node_record(history_full="R2-C", stack_bb=100),),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()

    resolved_stack = adapter.resolve_stack_bb(
        source_id=(first_source_id, second_source_id),
        requested_stack_bb=94,
    )

    assert resolved_stack == 100

    adapter.close()


def test_repository_adapter_load_candidates_supports_multiple_sources(
    tmp_path: Path,
) -> None:
    """验证 load_candidates 支持多策略源联合读取.

    Args:
        tmp_path: pytest 临时目录.
    """

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    first_source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=2,
    )
    second_source_id = repo.upsert_source(
        strategy_name="Cash6m50zAggressive",
        source_dir="/tmp/Cash6m50zAggressive",
        format_version=2,
    )
    repo.insert_nodes(
        source_id=first_source_id,
        node_records=(_make_node_record(history_full="R2-C", stack_bb=100),),
    )
    repo.insert_nodes(
        source_id=second_source_id,
        node_records=(_make_node_record(history_full="R3-C", stack_bb=100),),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()

    candidates = adapter.load_candidates(
        source_id=(first_source_id, second_source_id),
        stack_bb=100,
        node_context=_make_node_context(),
    )

    assert len(candidates) == 2
    assert {candidate.source_id for candidate in candidates} == {
        first_source_id,
        second_source_id,
    }

    adapter.close()


def test_loader_rejects_old_format_version(tmp_path: Path) -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    repo.upsert_source(
        strategy_name="Legacy",
        source_dir="/tmp/legacy",
        format_version=1,
    )
    repo.close()

    with pytest.raises(ValueError, match="格式版本过旧"):
        open_preflop_strategy_repository(tmp_path / "preflop_strategy.db")


def test_build_preflop_strategy_db_rebuilds_database_with_format_version_2(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "preflop_strategy.db"
    repo = PreflopStrategyRepository(db_path)
    repo.connect()
    repo.upsert_source(
        strategy_name="Legacy",
        source_dir="/tmp/legacy",
        format_version=1,
    )
    repo.close()

    strategy_dir = tmp_path / "Cash6m50zGeneral"
    strategy_dir.mkdir()
    (strategy_dir / "100bb_BTN.json").write_text(json.dumps({}), encoding="utf-8")

    build_preflop_strategy_db(strategy_dir=strategy_dir, db_path=db_path)

    reopened_repo = PreflopStrategyRepository(db_path)
    reopened_repo.connect()
    sources = reopened_repo.list_sources()

    assert len(sources) == 1
    assert sources[0].strategy_name == "Cash6m50zGeneral"
    assert sources[0].format_version == 2

    reopened_repo.close()


def test_repository_adapter_resolve_source_can_match_real_database_sources() -> None:
    """验证 resolve_source 可匹配真实数据库中的多个策略源.

    当测试数据库缺失时, 跳过该用例.
    """

    db_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "database"
        / "preflop_strategy.sqlite3"
    )
    if not db_path.exists():
        pytest.skip(f"测试数据库不存在: {db_path}")

    adapter = StrategyRepositoryAdapter(db_path)
    adapter.connect()
    try:
        matched_sources = adapter.resolve_source(
            strategy_name=REAL_PREFLOP_STRATEGY_SOURCE_NAMES
        )
    finally:
        adapter.close()

    assert len(matched_sources) == len(REAL_PREFLOP_STRATEGY_SOURCE_NAMES)
    assert {source.strategy_name for source in matched_sources} == set(
        REAL_PREFLOP_STRATEGY_SOURCE_NAMES
    )
