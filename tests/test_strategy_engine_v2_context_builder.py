from __future__ import annotations

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.strategy.preflop_parse.parser import _derive_mapper_fields
from bayes_poker.strategy.strategy_engine import build_player_node_context
from bayes_poker.strategy.strategy_engine.context_builder import UnsupportedContextError
from bayes_poker.table.observed_state import ObservedTableState


def _build_sixmax_players() -> list[Player]:
    return [
        Player(0, "btn", 100.0, 0.0, Position.BTN),
        Player(1, "sb", 100.0, 0.5, Position.SB),
        Player(2, "bb", 100.0, 1.0, Position.BB),
        Player(3, "utg", 100.0, 0.0, Position.UTG),
        Player(4, "mp", 100.0, 0.0, Position.MP),
        Player(5, "co", 100.0, 0.0, Position.CO),
    ]


def test_supported_context_open() -> None:
    observed_state = ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_sixmax_players(),
        action_history=[],
        state_version=1,
    )

    context = build_player_node_context(observed_state)

    assert context.node_context.actor_position == Position.UTG
    assert context.node_context.aggressor_position is None
    assert context.node_context.raise_time == 0
    assert context.node_context.pot_size == pytest.approx(1.5)
    assert (
        context.params.to_index()
        == PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=MetricsPosition.UTG,
            num_callers=0,
            num_raises=0,
            num_active_players=6,
            previous_action=MetricsActionType.FOLD,
            in_position_on_flop=False,
        ).to_index()
    )


def test_supported_context_call_vs_open() -> None:
    observed_state = ObservedTableState(
        table_id="t2",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h2",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=4,
        hero_seat=4,
        players=_build_sixmax_players(),
        action_history=[PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP)],
        state_version=1,
    )

    context = build_player_node_context(observed_state)

    assert context.node_context.actor_position == Position.MP
    assert context.node_context.aggressor_position == Position.UTG
    assert context.node_context.call_count == 0
    assert context.node_context.raise_time == 1
    assert context.node_context.pot_size == pytest.approx(4.0)
    assert context.node_context.raise_size_bb == pytest.approx(2.5)
    assert (
        context.params.to_index()
        == PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=MetricsPosition.HJ,
            num_callers=0,
            num_raises=1,
            num_active_players=6,
            previous_action=MetricsActionType.FOLD,
            in_position_on_flop=False,
        ).to_index()
    )


def test_supported_context_limp() -> None:
    observed_state = ObservedTableState(
        table_id="t3",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h3",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=5,
        hero_seat=5,
        players=_build_sixmax_players(),
        action_history=[
            PlayerAction(3, ActionType.CALL, 1.0, Street.PREFLOP),
            PlayerAction(4, ActionType.FOLD, 0.0, Street.PREFLOP),
        ],
        state_version=1,
    )

    context = build_player_node_context(observed_state)

    assert context.action_order == (3, 4)
    assert context.node_context.actor_position == Position.CO
    assert context.node_context.limp_count == 1
    assert context.node_context.raise_time == 0
    assert context.node_context.pot_size == pytest.approx(2.5)
    assert (
        context.params.to_index()
        == PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=MetricsPosition.CO,
            num_callers=1,
            num_raises=0,
            num_active_players=6,
            previous_action=MetricsActionType.FOLD,
            in_position_on_flop=False,
        ).to_index()
    )


def test_unsupported_context_non_preflop() -> None:
    observed_state = ObservedTableState(
        table_id="t4",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h4",
        street=Street.FLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_sixmax_players(),
        action_history=[],
        state_version=1,
    )

    with pytest.raises(UnsupportedContextError, match="preflop"):
        build_player_node_context(observed_state)


def test_supported_context_three_bet_plus_uses_last_aggressor() -> None:
    observed_state = ObservedTableState(
        table_id="t5",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h5",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=5,
        hero_seat=5,
        players=_build_sixmax_players(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
        ],
        state_version=1,
    )

    context = build_player_node_context(observed_state)

    assert context.node_context.actor_position == Position.CO
    assert context.node_context.aggressor_position == Position.MP
    assert context.node_context.call_count == 0
    assert context.node_context.limp_count == 0
    assert context.node_context.raise_time == 2
    assert context.node_context.pot_size == pytest.approx(12.0)
    assert context.node_context.raise_size_bb == pytest.approx(8.0)
    assert (
        context.params.to_index()
        == PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=MetricsPosition.CO,
            num_callers=0,
            num_raises=2,
            num_active_players=6,
            previous_action=MetricsActionType.FOLD,
            in_position_on_flop=False,
        ).to_index()
    )


def test_unsupported_context_actor_already_acted() -> None:
    observed_state = ObservedTableState(
        table_id="t6",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h6",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=4,
        hero_seat=4,
        players=_build_sixmax_players(),
        action_history=[PlayerAction(4, ActionType.CALL, 1.0, Street.PREFLOP)],
        state_version=1,
    )

    with pytest.raises(UnsupportedContextError, match="首次翻前行动"):
        build_player_node_context(observed_state)


@pytest.mark.parametrize(
    (
        "history_full",
        "acting_position",
        "actions",
        "expected_aggressor",
        "expected_call_count",
        "expected_limp_count",
        "expected_raise_time",
        "expected_pot_size",
    ),
    [
        ("", Position.UTG, [], None, 0, 0, 0, 1.5),
        (
            "R2.5",
            Position.MP,
            [PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP)],
            Position.UTG,
            0,
            0,
            1,
            4.0,
        ),
        (
            "C-F",
            Position.CO,
            [
                PlayerAction(3, ActionType.CALL, 1.0, Street.PREFLOP),
                PlayerAction(4, ActionType.FOLD, 0.0, Street.PREFLOP),
            ],
            None,
            0,
            1,
            0,
            2.5,
        ),
        (
            "R2.5-R8",
            Position.CO,
            [
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
                PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
            ],
            Position.MP,
            0,
            0,
            2,
            12.0,
        ),
    ],
)
def test_context_builder_and_parser_fields_should_be_consistent(
    history_full: str,
    acting_position: Position,
    actions: list[PlayerAction],
    expected_aggressor: Position | None,
    expected_call_count: int,
    expected_limp_count: int,
    expected_raise_time: int,
    expected_pot_size: float,
) -> None:
    """在线上下文与离线解析的关键 mapper 字段应保持一致。"""

    actor_seat_by_position: dict[Position, int] = {
        Position.BTN: 0,
        Position.SB: 1,
        Position.BB: 2,
        Position.UTG: 3,
        Position.MP: 4,
        Position.CO: 5,
    }
    observed_state = ObservedTableState(
        table_id="parity",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="parity",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=actor_seat_by_position[acting_position],
        hero_seat=actor_seat_by_position[acting_position],
        players=_build_sixmax_players(),
        action_history=actions,
        state_version=1,
    )

    context = build_player_node_context(observed_state)
    (
        _,
        actor_position,
        aggressor_position,
        call_count,
        limp_count,
        raise_time,
        pot_size,
        _,
        _,
    ) = _derive_mapper_fields(
        acting_position=acting_position.value,
        history_full=history_full,
    )

    assert actor_position == acting_position
    assert context.node_context.actor_position == acting_position
    assert aggressor_position == expected_aggressor
    assert context.node_context.aggressor_position == expected_aggressor
    assert call_count == expected_call_count
    assert context.node_context.call_count == expected_call_count
    assert limp_count == expected_limp_count
    assert context.node_context.limp_count == expected_limp_count
    assert raise_time == expected_raise_time
    assert context.node_context.raise_time == expected_raise_time
    assert pot_size == pytest.approx(expected_pot_size)
    assert context.node_context.pot_size == pytest.approx(expected_pot_size)
