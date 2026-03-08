"""测试对手范围更新时未处理动作队列逻辑。

测试 WebSocketServer._update_opponent_ranges 方法按正确顺序处理行动。
"""

from bayes_poker.comm.server import ServerConfig, WebSocketServer
from bayes_poker.comm.session import SessionManager, TableSession
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction
from bayes_poker.table.observed_state import ObservedTableState


class _RecordingPredictor:
    """记录 update_range_on_action 调用顺序的测试替身。"""

    def __init__(self) -> None:
        self.calls: list[tuple[int, ActionType, tuple[ActionType, ...]]] = []
        self.preflop_strategy = None
        self.stats_repo = None
        self.table_type = None

    def update_range_on_action(
        self,
        player: Player,
        action: PlayerAction,
        table_state: ObservedTableState,
        action_prefix: list[PlayerAction] | None = None,
    ) -> None:
        _ = table_state
        prefix = tuple(a.action_type for a in (action_prefix or []))
        self.calls.append((player.seat_index, action.action_type, prefix))

    def get_preflop_range(self, seat_index: int):
        _ = seat_index
        return None

    def get_postflop_range(self, seat_index: int):
        _ = seat_index
        return None

    def reset_all_ranges(self) -> None:
        pass


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


def test_server_updates_pending_actions_in_order() -> None:
    """测试 server 层按正确顺序处理未处理的行动。"""
    predictor = _RecordingPredictor()

    config = ServerConfig(host="localhost", port=8765)
    server = WebSocketServer(config=config, range_predictor=predictor)

    # 创建 TableSession
    session_id = "test-session"
    session_manager = server.session_manager
    table_session = TableSession(session_id=session_id, client_id="test-client")
    table_session.range_predictor = predictor
    session_manager._table_sessions[session_id] = table_session

    state = _build_state(hand_id="hand-1")
    server._update_opponent_ranges(session_id, state)

    assert predictor.calls == [
        (1, ActionType.CALL, ()),
        (2, ActionType.CHECK, (ActionType.CALL,)),
        (1, ActionType.RAISE, (ActionType.CALL, ActionType.CHECK)),
        (
            2,
            ActionType.BET,
            (ActionType.CALL, ActionType.CHECK, ActionType.RAISE),
        ),
        (
            1,
            ActionType.FOLD,
            (ActionType.CALL, ActionType.CHECK, ActionType.RAISE, ActionType.BET),
        ),
    ]

    # 再次调用不应重复处理
    server._update_opponent_ranges(session_id, state)
    assert len(predictor.calls) == 5

    # 新手牌应重新处理
    predictor.calls.clear()
    server._update_opponent_ranges(session_id, _build_state(hand_id="hand-2"))
    assert len(predictor.calls) == 5
