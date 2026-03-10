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
from bayes_poker.strategy.strategy_engine.core_types import ActionFamily, NodeContext
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository


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

    source = adapter.resolve_source()
    resolved_stack = adapter.resolve_stack_bb(
        source_id=source.source_id, requested_stack_bb=87
    )
    candidates = adapter.load_candidates(
        source_id=source.source_id,
        stack_bb=100,
        node_context=NodeContext(
            action_family=ActionFamily.CALL_VS_OPEN,
            actor_position=Position.CO,
            aggressor_position=Position.UTG,
            call_count=1,
            limp_count=0,
            raise_size_bb=2.0,
        ),
    )
    actions = adapter.load_actions((node_ids["R2-C"],))

    assert source.format_version == 2
    assert resolved_stack == 100
    assert len(candidates) == 1
    assert candidates[0].history_full == "R2-C"
    assert candidates[0].action_family == "CALL_VS_OPEN"
    assert len(actions[node_ids["R2-C"]]) == 2
    assert actions[node_ids["R2-C"]][1].action_code == "C"

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
