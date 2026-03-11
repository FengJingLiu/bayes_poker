from __future__ import annotations

from pathlib import Path

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.preflop_engine.state import ActionFamily as LegacyActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.core_types import NodeContext
from bayes_poker.strategy.strategy_engine.gto_policy import GtoPriorBuilder
from bayes_poker.strategy.strategy_engine.node_mapper import (
    StrategyNodeMapper,
    SyntheticTemplateKind,
)
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository


def _make_action_record(
    *,
    order_index: int,
    action_code: str,
    action_type: str,
    bet_size_bb: float | None,
    total_frequency: float,
) -> ParsedStrategyActionRecord:
    return ParsedStrategyActionRecord(
        order_index=order_index,
        action_code=action_code,
        action_type=action_type,
        bet_size_bb=bet_size_bb,
        is_all_in=False,
        total_frequency=total_frequency,
        next_position="",
        preflop_range=PreflopRange.zeros(),
        total_ev=0.0,
        total_combos=0.0,
    )


def _make_node_record(
    *,
    history_full: str,
    history_actions: str,
    acting_position: Position,
    action_family: LegacyActionFamily,
    aggressor_position: Position | None,
    call_count: int,
    limp_count: int,
    raise_time: int,
    pot_size: float,
    raise_size_bb: float | None,
    is_in_position: bool | None,
) -> ParsedStrategyNodeRecord:
    return ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full=history_full,
        history_actions=history_actions,
        history_token_count=len([token for token in history_full.split("-") if token]),
        acting_position=acting_position.value,
        source_file="test.json",
        action_family=action_family,
        actor_position=acting_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_time=raise_time,
        pot_size=pot_size,
        raise_size_bb=raise_size_bb,
        is_in_position=is_in_position,
    )


def _build_repository(
    tmp_path: Path,
    *,
    include_call_vs_open: bool = True,
    include_limp: bool = False,
) -> tuple[StrategyRepositoryAdapter, int]:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="TestStrategy",
        source_dir="/tmp/TestStrategy",
        format_version=2,
    )

    node_records: list[ParsedStrategyNodeRecord] = []
    node_actions: dict[str, tuple[ParsedStrategyActionRecord, ...]] = {}

    if include_call_vs_open:
        node_records.append(
            _make_node_record(
                history_full="R2-C",
                history_actions="R-C",
                acting_position=Position.CO,
                action_family=LegacyActionFamily.CALL_VS_OPEN,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=5.5,
                raise_size_bb=2.0,
                is_in_position=True,
            )
        )
        node_actions["R2-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.10,
            ),
            _make_action_record(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                total_frequency=0.80,
            ),
            _make_action_record(
                order_index=2,
                action_code="R9.5",
                action_type="RAISE",
                bet_size_bb=9.5,
                total_frequency=0.10,
            ),
        )
        node_records.append(
            _make_node_record(
                history_full="R2.5-C",
                history_actions="R-C",
                acting_position=Position.CO,
                action_family=LegacyActionFamily.CALL_VS_OPEN,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=6.0,
                raise_size_bb=2.5,
                is_in_position=True,
            )
        )
        node_actions["R2.5-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.90,
            ),
            _make_action_record(
                order_index=1,
                action_code="R9.5",
                action_type="RAISE",
                bet_size_bb=9.5,
                total_frequency=0.10,
            ),
        )

    if include_limp:
        node_records.append(
            _make_node_record(
                history_full="F-C",
                history_actions="F-C",
                acting_position=Position.CO,
                action_family=LegacyActionFamily.LIMP,
                aggressor_position=None,
                call_count=0,
                limp_count=1,
                raise_time=0,
                pot_size=2.5,
                raise_size_bb=None,
                is_in_position=None,
            )
        )
        node_actions["F-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.20,
            ),
            _make_action_record(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                total_frequency=0.50,
            ),
            _make_action_record(
                order_index=2,
                action_code="R4",
                action_type="RAISE",
                bet_size_bb=4.0,
                total_frequency=0.30,
            ),
        )

    node_ids = repo.insert_nodes(source_id=source_id, node_records=tuple(node_records))
    for history_full, action_records in node_actions.items():
        repo.insert_actions(
            node_id=node_ids[history_full], action_records=action_records
        )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    return adapter, source_id


def test_price_adjustment_and_gto_prior(tmp_path: Path) -> None:
    adapter, source_id = _build_repository(
        tmp_path, include_call_vs_open=True, include_limp=True
    )
    mapper = StrategyNodeMapper(
        repository_adapter=adapter, source_id=source_id, stack_bb=100
    )
    mapped = mapper.map_node_context(
        NodeContext(
            actor_position=Position.CO,
            aggressor_position=Position.UTG,
            call_count=1,
            limp_count=0,
            raise_time=1,
            pot_size=6.5,
            raise_size_bb=3.0,
        )
    )
    policy = GtoPriorBuilder(repository_adapter=adapter).build_policy(mapped)

    assert mapped.matched_history == "R2.5-C"
    assert mapped.price_adjustment_applied is True
    assert mapped.price_adjustment_factor == 0.75
    assert policy.action_names == ("F", "C", "R9.5")

    adapter.close()


def test_exact_match(tmp_path: Path) -> None:
    adapter, source_id = _build_repository(
        tmp_path, include_call_vs_open=True, include_limp=False
    )
    mapper = StrategyNodeMapper(
        repository_adapter=adapter, source_id=source_id, stack_bb=100
    )
    mapped = mapper.map_node_context(
        NodeContext(
            actor_position=Position.CO,
            aggressor_position=Position.UTG,
            call_count=1,
            limp_count=0,
            raise_time=1,
            pot_size=5.5,
            raise_size_bb=2.0,
        )
    )

    assert mapped.matched_history == "R2-C"
    assert mapped.distance_score == pytest.approx(0.0)
    assert mapped.candidate_node_ids != ()

    adapter.close()


def test_limp_without_candidates_uses_synthetic_template(tmp_path: Path) -> None:
    adapter, source_id = _build_repository(
        tmp_path, include_call_vs_open=True, include_limp=False
    )
    mapper = StrategyNodeMapper(
        repository_adapter=adapter, source_id=source_id, stack_bb=100
    )
    mapped = mapper.map_node_context(
        NodeContext(
            actor_position=Position.CO,
            aggressor_position=None,
            call_count=0,
            limp_count=1,
            raise_time=0,
            pot_size=2.5,
            raise_size_bb=None,
        )
    )
    policy = GtoPriorBuilder(repository_adapter=adapter).build_policy(mapped)

    assert mapped.synthetic_template_kind == SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3
    assert policy.action_names == ("F", "C", "R4")

    adapter.close()


def test_no_match_for_non_limp_raises_value_error(tmp_path: Path) -> None:
    adapter, source_id = _build_repository(
        tmp_path, include_call_vs_open=False, include_limp=False
    )
    mapper = StrategyNodeMapper(
        repository_adapter=adapter, source_id=source_id, stack_bb=100
    )

    with pytest.raises(ValueError, match="solver 节点"):
        mapper.map_node_context(
            NodeContext(
                actor_position=Position.CO,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=5.5,
                raise_size_bb=2.0,
            )
        )

    adapter.close()


def test_mapper_supports_multiple_source_ids(tmp_path: Path) -> None:
    """验证 StrategyNodeMapper 可接收多个 source_id 并跨源匹配最近节点.

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
        node_records=(
            _make_node_record(
                history_full="R2-C",
                history_actions="R-C",
                acting_position=Position.CO,
                action_family=LegacyActionFamily.CALL_VS_OPEN,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=7.5,
                raise_size_bb=3.0,
                is_in_position=True,
            ),
        ),
    )
    repo.insert_nodes(
        source_id=second_source_id,
        node_records=(
            _make_node_record(
                history_full="R2.2-C",
                history_actions="R-C",
                acting_position=Position.CO,
                action_family=LegacyActionFamily.CALL_VS_OPEN,
                aggressor_position=Position.UTG,
                call_count=1,
                limp_count=0,
                raise_time=1,
                pot_size=5.5,
                raise_size_bb=2.2,
                is_in_position=True,
            ),
        ),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()

    mapper = StrategyNodeMapper(
        repository_adapter=adapter,
        source_id=[first_source_id, second_source_id],
        stack_bb=100,
    )
    mapped = mapper.map_node_context(
        NodeContext(
            actor_position=Position.CO,
            aggressor_position=Position.UTG,
            call_count=1,
            limp_count=0,
            raise_time=1,
            pot_size=5.5,
            raise_size_bb=2.2,
        )
    )

    assert mapped.matched_history == "R2.2-C"
    assert set(mapped.candidate_histories) == {"R2-C", "R2.2-C"}

    adapter.close()
