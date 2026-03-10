from __future__ import annotations

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.strategy.strategy_engine import ActionFamily, build_player_node_context
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

    assert context.query_history == ""
    assert context.node_context.action_family == ActionFamily.OPEN
    assert context.node_context.actor_position == Position.UTG
    assert context.node_context.aggressor_position is None
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

    assert context.query_history == "R2.5"
    assert context.node_context.action_family == ActionFamily.CALL_VS_OPEN
    assert context.node_context.actor_position == Position.MP
    assert context.node_context.aggressor_position == Position.UTG
    assert context.node_context.call_count == 0
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

    assert context.query_history == "C-F"
    assert context.action_order == (3, 4)
    assert context.node_context.action_family == ActionFamily.LIMP
    assert context.node_context.actor_position == Position.CO
    assert context.node_context.limp_count == 1
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


def test_unsupported_context_three_bet_plus() -> None:
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

    with pytest.raises(UnsupportedContextError, match="多次加注"):
        build_player_node_context(observed_state)


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
