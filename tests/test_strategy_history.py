from bayes_poker.comm.strategy_history import build_preflop_history
from bayes_poker.table.observed_state import PlayerAction
from bayes_poker.domain.poker import ActionType


def test_build_preflop_history_encodes_actions_with_bb_sizes() -> None:
    actions = [
        PlayerAction(player_index=2, action_type=ActionType.FOLD, amount=0.0),
        PlayerAction(player_index=3, action_type=ActionType.RAISE, amount=2.0),
        PlayerAction(player_index=4, action_type=ActionType.CALL, amount=0.0),
    ]

    assert build_preflop_history(actions, big_blind=1.0) == "F-R2-C"


def test_build_preflop_history_formats_half_bb() -> None:
    actions = [
        PlayerAction(player_index=3, action_type=ActionType.RAISE, amount=2.5),
    ]

    assert build_preflop_history(actions, big_blind=1.0) == "R2.5"
