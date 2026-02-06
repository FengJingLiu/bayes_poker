"""测试对手范围更新时未处理动作队列逻辑。"""

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.strategy.engine import StrategyDispatcher
from bayes_poker.table.observed_state import ObservedTableState, Player, PlayerAction


class _RecordingPredictor:
    """记录 update_range_on_action 调用顺序的测试替身。"""

    def __init__(self) -> None:
        self.calls: list[tuple[int, ActionType]] = []

    def update_range_on_action(
        self,
        player: Player,
        action: PlayerAction,
        table_state: ObservedTableState,
    ) -> None:
        _ = table_state
        self.calls.append((player.seat_index, action.action_type))

    def get_preflop_range(self, seat_index: int):
        _ = seat_index
        return None

    def get_postflop_range(self, seat_index: int):
        _ = seat_index
        return None


def _build_state(hand_id: str) -> ObservedTableState:
    return ObservedTableState(
        table_id="table-1",
        hand_id=hand_id,
        hero_seat=0,
        street=Street.PREFLOP,
        action_history=[
            PlayerAction(player_index=1, action_type=ActionType.CALL),
            PlayerAction(player_index=2, action_type=ActionType.CHECK),
            PlayerAction(player_index=1, action_type=ActionType.RAISE),
            PlayerAction(player_index=2, action_type=ActionType.BET),
            PlayerAction(player_index=1, action_type=ActionType.FOLD),
        ],
        players=[
            Player(seat_index=0, player_id="hero", action_history=[]),
            Player(
                seat_index=1,
                player_id="opp-1",
                is_folded=True,
            ),
            Player(
                seat_index=2,
                player_id="opp-2",
            ),
        ],
    )


def test_dispatcher_updates_pending_actions_in_order() -> None:
    predictor = _RecordingPredictor()
    dispatcher = StrategyDispatcher(range_predictor=predictor)

    state = _build_state(hand_id="hand-1")
    dispatcher._update_opponent_ranges(state)

    assert predictor.calls == [
        (1, ActionType.CALL),
        (2, ActionType.CHECK),
        (1, ActionType.RAISE),
        (2, ActionType.BET),
        (1, ActionType.FOLD),
    ]

    dispatcher._update_opponent_ranges(state)
    assert predictor.calls == [
        (1, ActionType.CALL),
        (2, ActionType.CHECK),
        (1, ActionType.RAISE),
        (2, ActionType.BET),
        (1, ActionType.FOLD),
    ]

    dispatcher._update_opponent_ranges(_build_state(hand_id="hand-2"))
    assert predictor.calls == [
        (1, ActionType.CALL),
        (2, ActionType.CHECK),
        (1, ActionType.RAISE),
        (2, ActionType.BET),
        (1, ActionType.FOLD),
        (1, ActionType.CALL),
        (2, ActionType.CHECK),
        (1, ActionType.RAISE),
        (2, ActionType.BET),
        (1, ActionType.FOLD),
    ]
