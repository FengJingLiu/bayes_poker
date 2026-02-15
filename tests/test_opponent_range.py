"""对手范围预测器测试。

测试 OpponentRangePredictor 的 preflop 和 postflop 范围更新逻辑。
"""

from collections.abc import Iterator, Sequence
from functools import lru_cache
from pathlib import Path

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.opponent_range import (
    OpponentRangePredictor,
    create_opponent_range_predictor,
)
from bayes_poker.strategy.preflop_parse.models import PreflopStrategy
from bayes_poker.strategy.preflop_parse.parser import parse_strategy_directory
from bayes_poker.strategy.range import (
    PreflopRange,
)
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.table.layout.base import (
    Position as TablePosition,
    get_position_by_seat,
)
from bayes_poker.table.observed_state import (
    Player,
    ObservedTableState,
    PlayerAction,
)

REAL_PRELFOP_STRATEGY_DIR = Path(
    "/home/autumn/gg_handhistory/preflop_strategy/Cash6m50zSimple25Open_SimpleIP"
)
REAL_PLAYER_STATS_DB_PATH = Path("data/database/player_stats.db")


@lru_cache(maxsize=1)
def _load_real_preflop_strategy() -> PreflopStrategy:
    """加载真实翻前策略目录并缓存结果。

    Returns:
        翻前策略对象。
    """
    return parse_strategy_directory(REAL_PRELFOP_STRATEGY_DIR)


@pytest.fixture(scope="session")
def real_preflop_strategy() -> PreflopStrategy:
    """加载真实翻前策略。

    Returns:
        翻前策略对象。
    """
    if not REAL_PRELFOP_STRATEGY_DIR.is_dir():
        pytest.skip(f"策略目录不存在: {REAL_PRELFOP_STRATEGY_DIR}")
    preflop_strategy = _load_real_preflop_strategy()
    if preflop_strategy.node_count() <= 0:
        pytest.skip(f"策略目录无可用节点: {REAL_PRELFOP_STRATEGY_DIR}")
    return preflop_strategy


@pytest.fixture
def real_stats_repo() -> Iterator[PlayerStatsRepository]:
    """构建真实统计仓库连接。

    Yields:
        已连接的统计仓库。
    """
    if not REAL_PLAYER_STATS_DB_PATH.is_file():
        pytest.skip(f"统计数据库不存在: {REAL_PLAYER_STATS_DB_PATH}")
    stats_repo = PlayerStatsRepository(REAL_PLAYER_STATS_DB_PATH)
    stats_repo.connect()
    try:
        yield stats_repo
    finally:
        stats_repo.close()


def _build_sixmax_players_with_hero_btn(
    hero_position: str | TablePosition = TablePosition.BTN,
) -> list[Player]:
    """按 Hero 位置动态构建 6-max 玩家列表。

    Args:
        hero_position: Hero 的目标位置，支持字符串或位置枚举。

    Returns:
        玩家列表。
    """
    if isinstance(hero_position, str):
        target_position = TablePosition(hero_position.upper())
    else:
        target_position = hero_position

    seat_order_6max = [
        TablePosition.BTN,
        TablePosition.SB,
        TablePosition.BB,
        TablePosition.UTG,
        TablePosition.MP,
        TablePosition.CO,
    ]
    hero_offset = seat_order_6max.index(target_position)
    btn_seat = (-hero_offset) % 6

    players: list[Player] = []
    for seat_index in range(6):
        position = get_position_by_seat(
            seat_index=seat_index,
            btn_seat=btn_seat,
            player_count=6,
        )
        player_id = "hero" if seat_index == 0 else position.value.lower()
        players.append(
            Player(
                seat_index=seat_index,
                player_id=player_id,
                position=position.value,
                stack=100.0,
            )
        )
    return players


def _is_preflop_range_non_uniform(preflop_range: PreflopRange) -> bool:
    """判断翻前范围是否非均匀分布。

    Args:
        preflop_range: 翻前范围。

    Returns:
        若策略向量存在显著差异则返回 `True`。
    """
    min_frequency = min(preflop_range.strategy)
    max_frequency = max(preflop_range.strategy)
    return (max_frequency - min_frequency) > 1e-9


@pytest.fixture
def real_predictor(
    real_preflop_strategy: PreflopStrategy,
    real_stats_repo: PlayerStatsRepository,
) -> OpponentRangePredictor:
    """构建使用真实策略与真实数据库的对手范围预测器。

    Returns:
        对手范围预测器。
    """
    return create_opponent_range_predictor(
        preflop_strategy=real_preflop_strategy,
        stats_repo=real_stats_repo,
        table_type=TableType.SIX_MAX,
    )


class TestOpponentRangePredictor:
    """OpponentRangePredictor 测试类。"""

    def test_create_predictor(
        self,
        real_preflop_strategy: PreflopStrategy,
        real_stats_repo: PlayerStatsRepository,
    ) -> None:
        """测试创建预测器。"""
        predictor = create_opponent_range_predictor(
            preflop_strategy=real_preflop_strategy,
            stats_repo=real_stats_repo,
            table_type=TableType.SIX_MAX,
        )
        assert predictor is not None
        assert isinstance(predictor, OpponentRangePredictor)

    def test_initial_preflop_range_by_position(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试根据位置生成初始翻前范围。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="BTN")
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=1,
            hero_seat=0,
            street=Street.PREFLOP,
        )

        action = PlayerAction(
            player_index=1,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )

        predictor.update_range_on_action(player, action, table_state)

        # 通过 predictor 获取范围
        preflop_range = predictor.get_preflop_range(player.seat_index)
        assert preflop_range is not None
        assert isinstance(preflop_range, PreflopRange)
        assert preflop_range.total_frequency() > 0

    def test_preflop_fold_clears_range(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试弃牌时范围清零。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="UTG")
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.PREFLOP,
        )

        # 先触发一个 call 初始化范围
        call_action = PlayerAction(
            player_index=1,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, call_action, table_state)

        # 弃牌动作
        fold_action = PlayerAction(
            player_index=1,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, fold_action, table_state)

        # 范围应该清零
        preflop_range = predictor.get_preflop_range(player.seat_index)
        assert preflop_range is not None
        assert preflop_range.total_frequency() == 0.0

    def test_postflop_range_from_preflop(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试当前阶段翻后逻辑留空。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="CO")

        # 先在 preflop 行动
        preflop_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.PREFLOP,
        )
        preflop_action = PlayerAction(
            player_index=1,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, preflop_action, preflop_state)

        # flop 行动
        flop_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.FLOP,
            board_cards=["As", "Kd", "7c"],
        )
        bet_action = PlayerAction(
            player_index=1,
            action_type=ActionType.BET,
            amount=5.0,
            street=Street.FLOP,
        )
        predictor.update_range_on_action(player, bet_action, flop_state)

        # 当前阶段 postflop 逻辑留空，不应生成翻后范围。
        postflop_range = predictor.get_postflop_range(player.seat_index)
        assert postflop_range is None

    def test_board_blockers_applied(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试当前阶段翻后公共牌逻辑留空。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="BB")

        # 先在 preflop 行动
        preflop_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.PREFLOP,
        )
        preflop_action = PlayerAction(
            player_index=1,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, preflop_action, preflop_state)

        # flop 行动（3 张 A）
        flop_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.FLOP,
            board_cards=["As", "Ah", "Ad"],
        )
        check_action = PlayerAction(
            player_index=1,
            action_type=ActionType.CHECK,
            amount=0.0,
            street=Street.FLOP,
        )
        predictor.update_range_on_action(player, check_action, flop_state)

        postflop_range = predictor.get_postflop_range(player.seat_index)
        assert postflop_range is None

    def test_preflop_first_action_dispatches_first_handler(self) -> None:
        """首次翻前行动应进入 first-action 分发。"""

        class _SpyPredictor(OpponentRangePredictor):
            def __init__(self) -> None:
                super().__init__()
                self.first_calls = 0
                self.non_first_calls = 0

            def _handle_preflop_first_action(  # type: ignore[override]
                self,
                *,
                player: Player,
                action: PlayerAction,
                table_state: ObservedTableState,
                preflop_prefix: Sequence[PlayerAction],
                current_prefix: Sequence[PlayerAction],
            ) -> None:
                self.first_calls += 1

            def _handle_preflop_non_first_action(  # type: ignore[override]
                self,
                *,
                player: Player,
                action: PlayerAction,
                table_state: ObservedTableState,
                preflop_prefix: Sequence[PlayerAction],
                current_prefix: Sequence[PlayerAction],
            ) -> None:
                self.non_first_calls += 1

        predictor = _SpyPredictor()
        player = Player(seat_index=4, player_id="mp", position="MP")
        state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
        )
        action = PlayerAction(
            player_index=4,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )

        predictor.update_range_on_action(player, action, state, action_prefix=())
        assert predictor.first_calls == 1
        assert predictor.non_first_calls == 0

    def test_preflop_non_first_action_dispatches_non_first_handler(self) -> None:
        """非首次翻前行动应进入 non-first-action 分发。"""

        class _SpyPredictor(OpponentRangePredictor):
            def __init__(self) -> None:
                super().__init__()
                self.first_calls = 0
                self.non_first_calls = 0

            def _handle_preflop_first_action(  # type: ignore[override]
                self,
                *,
                player: Player,
                action: PlayerAction,
                table_state: ObservedTableState,
                preflop_prefix: Sequence[PlayerAction],
                current_prefix: Sequence[PlayerAction],
            ) -> None:
                self.first_calls += 1

            def _handle_preflop_non_first_action(  # type: ignore[override]
                self,
                *,
                player: Player,
                action: PlayerAction,
                table_state: ObservedTableState,
                preflop_prefix: Sequence[PlayerAction],
                current_prefix: Sequence[PlayerAction],
            ) -> None:
                self.non_first_calls += 1

        predictor = _SpyPredictor()
        player = Player(seat_index=4, player_id="mp", position="MP")
        state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
        )
        action = PlayerAction(
            player_index=4,
            action_type=ActionType.RAISE,
            amount=3.0,
            street=Street.PREFLOP,
        )
        prefix = (
            PlayerAction(
                player_index=4,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
        )

        predictor.update_range_on_action(player, action, state, action_prefix=prefix)
        assert predictor.first_calls == 0
        assert predictor.non_first_calls == 1

    def test_reset_player_ranges(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试重置玩家范围。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="MP")
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.PREFLOP,
        )

        # 触发一个行动初始化范围
        action = PlayerAction(
            player_index=1,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, action, table_state)

        # 验证范围已初始化
        assert predictor.get_preflop_range(player.seat_index) is not None

        # 重置范围
        predictor.reset_player_ranges(player)

        # 验证范围已清除
        assert predictor.get_preflop_range(player.seat_index) is None
        assert predictor.get_postflop_range(player.seat_index) is None

    def test_raise_action_narrows_range(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试加注动作收窄范围。"""
        predictor = real_predictor

        player = Player(seat_index=1, player_id="opponent", position="UTG")
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=5,
            hero_seat=0,
            street=Street.PREFLOP,
        )

        # 加注动作
        raise_action = PlayerAction(
            player_index=1,
            action_type=ActionType.RAISE,
            amount=6.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(player, raise_action, table_state)

        # 验证范围已初始化（加注后范围应该收窄但仍存在）
        preflop_range = predictor.get_preflop_range(player.seat_index)
        assert preflop_range is not None

    def test_reset_all_ranges(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """测试重置所有玩家范围。"""
        predictor = real_predictor

        # 为多个玩家初始化范围
        for seat in range(3):
            player = Player(seat_index=seat, player_id=f"player_{seat}", position="MP")
            table_state = ObservedTableState(
                player_count=6,
                btn_seat=5,
                hero_seat=0,
                street=Street.PREFLOP,
            )
            action = PlayerAction(
                player_index=seat,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            )
            predictor.update_range_on_action(player, action, table_state)

        # 验证范围已初始化
        assert predictor.get_preflop_range(0) is not None
        assert predictor.get_preflop_range(1) is not None
        assert predictor.get_preflop_range(2) is not None

        # 重置所有范围
        predictor.reset_all_ranges()

        # 验证所有范围已清除
        assert predictor.get_preflop_range(0) is None
        assert predictor.get_preflop_range(1) is None
        assert predictor.get_preflop_range(2) is None

    def test_limp_preflop_uses_aggregated_stats_and_min_raise_ev(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实场景: CO follow limp 后应生成非均匀翻前范围。"""
        predictor = real_predictor
        players = _build_sixmax_players_with_hero_btn()
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        preflop_action = PlayerAction(
            player_index=5,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(
            players[5],
            preflop_action,
            table_state,
            action_prefix=[
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
            ],
        )
        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert preflop_range.total_frequency() > 0.0
        assert _is_preflop_range_non_uniform(preflop_range)

    def test_limp_preflop_rebuilds_even_if_preflop_range_exists(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实场景: 已有翻前范围时, CO follow limp 仍可重建非均匀范围。"""
        predictor = real_predictor
        players = _build_sixmax_players_with_hero_btn()
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            table_state,
        )
        predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            table_state,
            action_prefix=[
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
            ],
        )
        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert preflop_range.total_frequency() > 0.0
        assert _is_preflop_range_non_uniform(preflop_range)

    def test_preflop_non_limp_prefix_does_not_enter_limp_builder(self) -> None:
        """非 limp 分层场景下不应进入 limp 专用预测分支。"""

        class _SpyPredictor(OpponentRangePredictor):
            def __init__(self) -> None:
                super().__init__()
                self.limp_builder_calls = 0

            def _build_limp_preflop_range_from_prefix(
                self,
                *,
                player: Player,
                table_state: ObservedTableState,
                action_prefix: Sequence[PlayerAction],
            ) -> PreflopRange | None:
                self.limp_builder_calls += 1
                return None

        predictor = _SpyPredictor()
        player = Player(seat_index=5, player_id="villain", position="CO", stack=100.0)
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=[
                Player(seat_index=0, player_id="btn", position="BTN", stack=100.0),
                Player(seat_index=1, player_id="sb", position="SB", stack=100.0),
                Player(seat_index=2, player_id="bb", position="BB", stack=100.0),
                Player(seat_index=3, player_id="utg", position="UTG", stack=100.0),
                Player(seat_index=4, player_id="mp", position="MP", stack=100.0),
                player,
            ],
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
                action_type=ActionType.FOLD,
                amount=0.0,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=5,
                action_type=ActionType.CALL,
                amount=2.5,
                street=Street.PREFLOP,
            ),
        ]
        preflop_action = PlayerAction(
            player_index=5,
            action_type=ActionType.CALL,
            amount=2.5,
            street=Street.PREFLOP,
        )

        predictor.update_range_on_action(
            player,
            preflop_action,
            table_state,
            action_prefix=action_prefix,
        )

        assert predictor.limp_builder_calls == 0

    def test_rfi_no_limper_uses_prefix_frequency_and_ev_rank(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实场景: CO 无 limper open 后应生成非均匀翻前范围。"""
        predictor = real_predictor
        players = _build_sixmax_players_with_hero_btn()
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.RAISE,
                amount=2.5,
                street=Street.PREFLOP,
            ),
            table_state,
            action_prefix=[
                PlayerAction(
                    player_index=3,
                    action_type=ActionType.FOLD,
                    amount=0.0,
                    street=Street.PREFLOP,
                ),
                PlayerAction(
                    player_index=4,
                    action_type=ActionType.FOLD,
                    amount=0.0,
                    street=Street.PREFLOP,
                ),
            ],
        )
        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert preflop_range.total_frequency() > 0.0
        assert _is_preflop_range_non_uniform(preflop_range)

    def test_rfi_have_limper_uses_prefix_frequency_and_ev_rank(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实场景: CO 面对 limper open 后应生成非均匀翻前范围。"""
        predictor = real_predictor
        players = _build_sixmax_players_with_hero_btn()
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.RAISE,
                amount=4.0,
                street=Street.PREFLOP,
            ),
            table_state,
            action_prefix=[
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
            ],
        )
        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert preflop_range.total_frequency() > 0.0
        assert _is_preflop_range_non_uniform(preflop_range)

    def test_rfi_utg_first_in_uses_aggregated_stats_and_ev_rank(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实场景: UTG first-in open 后应生成非均匀翻前范围。"""
        predictor = real_predictor
        players = _build_sixmax_players_with_hero_btn()
        table_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        predictor.update_range_on_action(
            players[3],
            PlayerAction(
                player_index=3,
                action_type=ActionType.RAISE,
                amount=2.5,
                street=Street.PREFLOP,
            ),
            table_state,
            action_prefix=[],
        )
        preflop_range = predictor.get_preflop_range(3)
        assert preflop_range is not None
        assert preflop_range.total_frequency() > 0.0
        assert _is_preflop_range_non_uniform(preflop_range)

    def test_real_predictor_hero_btn_utg_fold_mp_limp_co_fold(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实数据场景: hero BTN, UTG fold, MP limp, CO fold。"""
        players = _build_sixmax_players_with_hero_btn()
        preflop_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        preflop_actions = [
            PlayerAction(
                player_index=3,
                action_type=ActionType.FOLD,
                amount=0.0,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=4,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=5,
                action_type=ActionType.FOLD,
                amount=0.0,
                street=Street.PREFLOP,
            ),
        ]
        for idx, preflop_action in enumerate(preflop_actions):
            real_predictor.update_range_on_action(
                players[preflop_action.player_index],
                preflop_action,
                preflop_state,
                action_prefix=preflop_actions[:idx],
            )

        flop_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.FLOP,
            big_blind=1.0,
            players=players,
            board_cards=["As", "Kd", "7c"],
        )
        real_predictor.update_range_on_action(
            players[4],
            PlayerAction(
                player_index=4,
                action_type=ActionType.CHECK,
                amount=0.0,
                street=Street.FLOP,
            ),
            flop_state,
            action_prefix=preflop_actions,
        )

        utg_range = real_predictor.get_preflop_range(3)
        mp_range = real_predictor.get_preflop_range(4)
        co_range = real_predictor.get_preflop_range(5)
        assert utg_range is not None
        assert mp_range is not None
        assert co_range is not None
        assert utg_range.total_frequency() == 0.0
        assert co_range.total_frequency() == 0.0
        assert mp_range.total_frequency() > 0.0

    def test_real_predictor_hero_btn_utg_limp_mp_limp_co_limp(
        self,
        real_predictor: OpponentRangePredictor,
    ) -> None:
        """真实数据场景: hero BTN, UTG limp, MP limp, CO limp。"""
        players = _build_sixmax_players_with_hero_btn()
        preflop_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        preflop_actions = [
            PlayerAction(
                player_index=3,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=4,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=5,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
        ]
        for idx, preflop_action in enumerate(preflop_actions):
            real_predictor.update_range_on_action(
                players[preflop_action.player_index],
                preflop_action,
                preflop_state,
                action_prefix=preflop_actions[:idx],
            )

        flop_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.FLOP,
            big_blind=1.0,
            players=players,
            board_cards=["As", "Kd", "7c"],
        )
        real_predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.BET,
                amount=2.0,
                street=Street.FLOP,
            ),
            flop_state,
            action_prefix=preflop_actions,
        )

        utg_range = real_predictor.get_preflop_range(3)
        mp_range = real_predictor.get_preflop_range(4)
        co_range = real_predictor.get_preflop_range(5)
        assert utg_range is not None
        assert mp_range is not None
        assert co_range is not None
        assert utg_range.total_frequency() > 0.0
        assert mp_range.total_frequency() > 0.0
        assert co_range.total_frequency() > 0.0
        assert co_range.total_frequency() > 0.0
