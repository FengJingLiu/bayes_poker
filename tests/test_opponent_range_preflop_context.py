"""对手翻前上下文构建测试。"""

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.player_metrics.enums import Position, TableType
from bayes_poker.strategy.opponent_range.preflop_context import (
    build_opponent_preflop_context,
)
from bayes_poker.strategy.runtime.preflop_history import (
    PreflopScenario,
    classify_preflop_scenario,
)
from bayes_poker.table.observed_state import ObservedTableState, Player, PlayerAction


def _build_sixmax_players() -> list[Player]:
    """构造 6-max 固定座位玩家列表。

    Returns:
        固定按钮位的玩家列表。
    """
    return [
        Player(seat_index=0, player_id="btn"),
        Player(seat_index=1, player_id="sb"),
        Player(seat_index=2, player_id="bb"),
        Player(seat_index=3, player_id="utg"),
        Player(seat_index=4, player_id="mp"),
        Player(seat_index=5, player_id="co"),
    ]


def test_build_opponent_preflop_context_for_limp_prefix() -> None:
    """limp 前缀应正确映射场景与 PreFlopParams。"""
    players = _build_sixmax_players()
    players[5] = Player(seat_index=5, player_id="villain")
    table_state = ObservedTableState(
        player_count=6,
        btn_seat=0,
        hero_seat=0,
        street=Street.FLOP,
        big_blind=1.0,
        players=players,
    )
    action_prefix = [
        PlayerAction(
            player_index=3,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=4,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=5,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        ),
    ]

    context = build_opponent_preflop_context(
        player=players[5],
        action_prefix=action_prefix,
        table_state=table_state,
        table_type=TableType.SIX_MAX,
    )

    assert context.scenario == PreflopScenario.RFI_FACE_LIMPER
    assert context.query_history == "C-F-C"
    assert context.params is not None
    assert context.params.position == Position.CO
    assert context.params.num_callers == 1
    assert context.params.num_raises == 0


def test_build_opponent_preflop_context_for_utg_first_in_open_prefix() -> None:
    """UTG first-in open 前缀应提供共享 adapter 需要的参数。"""
    players = _build_sixmax_players()
    table_state = ObservedTableState(
        player_count=6,
        btn_seat=0,
        hero_seat=0,
        street=Street.PREFLOP,
        big_blind=1.0,
        players=players,
    )
    action_prefix = [
        PlayerAction(
            player_index=3,
            action_type=ActionType.RAISE,
            amount=2.5,
            street=Street.PREFLOP,
        ),
    ]

    context = build_opponent_preflop_context(
        player=players[3],
        action_prefix=action_prefix,
        table_state=table_state,
        table_type=TableType.SIX_MAX,
    )

    assert context.query_history == "R2.5"
    assert classify_preflop_scenario(context.query_history) == PreflopScenario.THREE_BET
    assert context.params is not None
    assert context.params.position == Position.UTG
    assert context.params.num_callers == 0
    assert context.params.num_raises == 0


def test_build_opponent_preflop_context_for_cold_call_prefix() -> None:
    """cold call vs open 前缀应提供共享 adapter 需要的参数。"""
    players = _build_sixmax_players()
    table_state = ObservedTableState(
        player_count=6,
        btn_seat=0,
        hero_seat=0,
        street=Street.PREFLOP,
        big_blind=1.0,
        players=players,
    )
    action_prefix = [
        PlayerAction(
            player_index=3,
            action_type=ActionType.RAISE,
            amount=2.5,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=4,
            action_type=ActionType.CALL,
            amount=2.5,
            street=Street.PREFLOP,
        ),
    ]

    context = build_opponent_preflop_context(
        player=players[4],
        action_prefix=action_prefix,
        table_state=table_state,
        table_type=TableType.SIX_MAX,
    )

    assert context.query_history == "R2.5-C"
    assert classify_preflop_scenario(context.query_history) == PreflopScenario.THREE_BET
    assert context.params is not None
    assert context.params.position == Position.HJ
    assert context.params.num_callers == 0
    assert context.params.num_raises == 1
