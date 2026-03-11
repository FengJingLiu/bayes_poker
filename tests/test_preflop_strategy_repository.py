"""翻前策略 sqlite 仓库测试."""

from __future__ import annotations

from pathlib import Path

from bayes_poker.strategy.preflop_engine.state import ActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.domain.table import Position


def _make_node_record(
    *,
    history_full: str = "R2-C",
    stack_bb: int = 100,
    actor_position: Position = Position.CO,
    aggressor_position: Position | None = Position.UTG,
    call_count: int = 1,
    limp_count: int = 0,
    raise_time: int = 1,
    pot_size: float = 5.5,
    raise_size_bb: float | None = 2.0,
    is_in_position: bool | None = True,
) -> ParsedStrategyNodeRecord:
    """构造最小可用的节点记录."""

    return ParsedStrategyNodeRecord(
        stack_bb=stack_bb,
        history_full=history_full,
        history_actions="R-C",
        history_token_count=2,
        acting_position=actor_position.value,
        source_file="test.json",
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_time=raise_time,
        pot_size=pot_size,
        raise_size_bb=raise_size_bb,
        is_in_position=is_in_position,
    )


def _make_action_records() -> tuple[ParsedStrategyActionRecord, ...]:
    """构造最小可用的动作记录集合."""

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


def test_repository_initializes_schema_and_inserts_source(tmp_path: Path) -> None:
    """应能创建 schema 并插入策略源信息."""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()

    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )

    assert source_id > 0
    sources = repo.list_sources()
    assert len(sources) == 1
    assert sources[0].strategy_name == "Cash6m50zGeneral"
    repo.close()


def test_repository_reads_candidates_and_actions_by_node_id(tmp_path: Path) -> None:
    """应能按候选条件读取节点，并按 node_id 取回动作."""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )
    node_ids = repo.insert_nodes(
        source_id=source_id, node_records=(_make_node_record(),)
    )
    repo.insert_actions(
        node_id=node_ids["R2-C"],
        action_records=_make_action_records(),
    )

    candidates = repo.list_candidates(
        source_id=source_id,
        stack_bb=100,
        is_in_position=True,
        raise_time=1,
        pot_size=5.5,
    )
    actions_by_node_id = repo.get_actions_for_nodes((node_ids["R2-C"],))

    assert len(candidates) == 1
    assert candidates[0].node_id == node_ids["R2-C"]
    assert len(actions_by_node_id[node_ids["R2-C"]]) == 2
    assert actions_by_node_id[node_ids["R2-C"]][1].action_code == "C"
    assert repo.count_nodes() == 1
    assert repo.count_actions() == 2
    repo.close()


def test_repository_resolve_stack_bb_returns_nearest_available_stack(
    tmp_path: Path,
) -> None:
    """应能按仓库内容解析最接近的可用筹码深度."""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )
    repo.insert_nodes(
        source_id=source_id,
        node_records=(
            _make_node_record(history_full="R2-C"),
            _make_node_record(history_full="R3-C", stack_bb=50),
        ),
    )

    assert repo.list_stack_bbs(source_id=source_id) == [50, 100]
    assert repo.resolve_stack_bb(source_id=source_id, requested_stack_bb=87) == 100
    assert repo.resolve_stack_bb(source_id=source_id, requested_stack_bb=51) == 50
    repo.close()


def test_repository_list_candidates_supports_multi_source_selector(
    tmp_path: Path,
) -> None:
    """应支持在单次 SQL 中按多个 source_id 检索候选节点."""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    first_source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )
    second_source_id = repo.upsert_source(
        strategy_name="Cash6m50zAggressive",
        source_dir="/tmp/Cash6m50zAggressive",
        format_version=1,
    )
    first_node_ids = repo.insert_nodes(
        source_id=first_source_id,
        node_records=(_make_node_record(history_full="R2-C"),),
    )
    second_node_ids = repo.insert_nodes(
        source_id=second_source_id,
        node_records=(_make_node_record(history_full="R2.2-C"),),
    )

    candidates = repo.list_candidates(
        source_ids=(first_source_id, second_source_id),
        stack_bb=100,
        is_in_position=True,
        raise_time=1,
        pot_size=5.5,
    )

    assert {candidate.source_id for candidate in candidates} == {
        first_source_id,
        second_source_id,
    }
    assert {candidate.node_id for candidate in candidates} == {
        first_node_ids["R2-C"],
        second_node_ids["R2.2-C"],
    }
    repo.close()


def test_repository_list_limp_candidates_filters_actor_and_raise_time_zero(
    tmp_path: Path,
) -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="Cash6m50zGeneral",
        source_dir="/tmp/Cash6m50zGeneral",
        format_version=1,
    )
    node_ids = repo.insert_nodes(
        source_id=source_id,
        node_records=(
            _make_node_record(
                history_full="CO_LIMP",
                actor_position=Position.CO,
                aggressor_position=None,
                call_count=0,
                limp_count=1,
                raise_time=0,
                pot_size=2.5,
                raise_size_bb=None,
                is_in_position=None,
            ),
            _make_node_record(
                history_full="UTG_OPEN",
                actor_position=Position.UTG,
                aggressor_position=None,
                call_count=0,
                limp_count=0,
                raise_time=0,
                pot_size=1.5,
                raise_size_bb=2.5,
                is_in_position=None,
            ),
            _make_node_record(
                history_full="CO_CALL_VS_OPEN",
                actor_position=Position.CO,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=5.5,
                raise_size_bb=2.5,
                is_in_position=True,
            ),
        ),
    )

    candidates = repo.list_limp_candidates(
        source_id=source_id,
        stack_bb=100,
        actor_position=Position.CO,
        pot_size=2.5,
    )

    assert [candidate.node_id for candidate in candidates] == [node_ids["CO_LIMP"]]
    repo.close()
