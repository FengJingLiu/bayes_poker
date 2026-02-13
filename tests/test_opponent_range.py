"""对手范围预测器测试。

测试 OpponentRangePredictor 的 preflop 和 postflop 范围更新逻辑。
"""

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.player_metrics.enums import (
    ActionType as MetricsActionType,
    Position as MetricsPosition,
    TableType,
)
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.strategy.opponent_range import (
    OpponentRangePredictor,
    create_opponent_range_predictor,
)
from bayes_poker.strategy.preflop_parse.models import (
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.preflop_parse.parser import parse_strategy_directory
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
    PostflopRange,
    get_hand_key_to_169_index,
)
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.table.observed_state import (
    Player,
    ObservedTableState,
    PlayerAction,
)

REAL_PRELFOP_STRATEGY_DIR = Path(
    "/home/autumn/project/gg_handhistory/preflop_strategy/Cash6m50zSimple25Open_SimpleIP"
)
REAL_PLAYER_STATS_DB_PATH = Path("data/database/player_stats.db")


def _range_with_single_hand_ev(hand_key: str, ev: float) -> PreflopRange:
    """构建单手牌 EV 峰值范围。

    Args:
        hand_key: 手牌键。
        ev: EV 峰值。

    Returns:
        翻前范围对象。
    """
    strategy = [1.0] * RANGE_169_LENGTH
    evs = [0.0] * RANGE_169_LENGTH
    evs[get_hand_key_to_169_index()[hand_key]] = ev
    return PreflopRange(strategy=strategy, evs=evs)


@lru_cache(maxsize=1)
def _load_real_preflop_strategy() -> PreflopStrategy:
    """加载真实翻前策略目录并缓存结果。

    Returns:
        翻前策略对象。
    """
    return parse_strategy_directory(REAL_PRELFOP_STRATEGY_DIR)


def _build_sixmax_players_with_hero_btn() -> list[Player]:
    """构建 Hero 在 BTN 的 6-max 玩家列表。

    Returns:
        玩家列表。
    """
    return [
        Player(seat_index=0, player_id="hero", position="BTN", stack=100.0),
        Player(seat_index=1, player_id="sb", position="SB", stack=100.0),
        Player(seat_index=2, player_id="bb", position="BB", stack=100.0),
        Player(seat_index=3, player_id="utg", position="UTG", stack=100.0),
        Player(seat_index=4, player_id="mp", position="MP", stack=100.0),
        Player(seat_index=5, player_id="co", position="CO", stack=100.0),
    ]


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
def real_predictor() -> OpponentRangePredictor:
    """构建使用真实策略与真实数据库的对手范围预测器。

    Returns:
        对手范围预测器。
    """
    if not REAL_PRELFOP_STRATEGY_DIR.is_dir():
        pytest.skip(f"策略目录不存在: {REAL_PRELFOP_STRATEGY_DIR}")
    if not REAL_PLAYER_STATS_DB_PATH.is_file():
        pytest.skip(f"统计数据库不存在: {REAL_PLAYER_STATS_DB_PATH}")

    preflop_strategy = _load_real_preflop_strategy()
    if preflop_strategy.node_count() <= 0:
        pytest.skip(f"策略目录无可用节点: {REAL_PRELFOP_STRATEGY_DIR}")

    stats_repo = PlayerStatsRepository(REAL_PLAYER_STATS_DB_PATH)
    stats_repo.connect()
    try:
        yield create_opponent_range_predictor(
            preflop_strategy=preflop_strategy,
            stats_repo=stats_repo,
            table_type=TableType.SIX_MAX,
        )
    finally:
        stats_repo.close()


class TestOpponentRangePredictor:
    """OpponentRangePredictor 测试类。"""

    def test_create_predictor(self) -> None:
        """测试创建预测器。"""
        predictor = create_opponent_range_predictor()
        assert predictor is not None
        assert isinstance(predictor, OpponentRangePredictor)

    def test_initial_preflop_range_by_position(self) -> None:
        """测试根据位置生成初始翻前范围。"""
        predictor = create_opponent_range_predictor()

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

    def test_preflop_fold_clears_range(self) -> None:
        """测试弃牌时范围清零。"""
        predictor = create_opponent_range_predictor()

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

    def test_postflop_range_from_preflop(self) -> None:
        """测试当前阶段翻后逻辑留空。"""
        predictor = create_opponent_range_predictor()

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

    def test_board_blockers_applied(self) -> None:
        """测试当前阶段翻后公共牌逻辑留空。"""
        predictor = create_opponent_range_predictor()

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

    def test_reset_player_ranges(self) -> None:
        """测试重置玩家范围。"""
        predictor = create_opponent_range_predictor()

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

    def test_raise_action_narrows_range(self) -> None:
        """测试加注动作收窄范围。"""
        predictor = create_opponent_range_predictor()

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

    def test_reset_all_ranges(self) -> None:
        """测试重置所有玩家范围。"""
        predictor = create_opponent_range_predictor()

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

    def test_limp_preflop_uses_aggregated_stats_and_min_raise_ev(self) -> None:
        """limp 翻前重建应使用聚合统计与最小尺度 raise EV。"""

        class _Repo:
            def __init__(self) -> None:
                self.called_with: list[tuple[str, TableType]] = []
                self.stats = PlayerStats(
                    player_name="aggregated_sixmax_100",
                    table_type=TableType.SIX_MAX,
                )
                params = PreFlopParams(
                    table_type=TableType.SIX_MAX,
                    position=MetricsPosition.CO,
                    num_callers=1,
                    num_raises=0,
                    num_active_players=6,
                    previous_action=MetricsActionType.FOLD,
                    in_position_on_flop=False,
                )
                action_stats = self.stats.get_preflop_stats(params)
                action_stats.raise_samples = 0
                action_stats.check_call_samples = 1
                action_stats.fold_samples = 999

            def get(
                self,
                player_name: str,
                table_type: TableType,
            ) -> PlayerStats | None:
                self.called_with.append((player_name, table_type))
                if player_name == "aggregated_sixmax_100":
                    return self.stats
                return None

        strategy = PreflopStrategy(name="test", source_dir="/tmp")
        strategy.add_node(
            100,
            StrategyNode(
                history_full="C-F-C",
                history_actions="C-F-C",
                history_token_count=3,
                acting_position="CO",
                source_file="test.json",
                actions=(
                    StrategyAction(
                        order_index=0,
                        action_code="R2",
                        action_type="RAISE",
                        bet_size_bb=2.0,
                        is_all_in=False,
                        total_frequency=0.3,
                        next_position="BTN",
                        range=_range_with_single_hand_ev("AKs", 100.0),
                    ),
                    StrategyAction(
                        order_index=1,
                        action_code="R6",
                        action_type="RAISE",
                        bet_size_bb=6.0,
                        is_all_in=False,
                        total_frequency=0.2,
                        next_position="BTN",
                        range=_range_with_single_hand_ev("22", 200.0),
                    ),
                ),
            ),
        )

        repo = _Repo()
        predictor = create_opponent_range_predictor(
            preflop_strategy=strategy,
            stats_repo=repo,  # type: ignore[arg-type]
            table_type=TableType.SIX_MAX,
        )

        players = [
            Player(seat_index=0, player_id="btn", position="BTN", stack=100.0),
            Player(seat_index=1, player_id="sb", position="SB", stack=100.0),
            Player(seat_index=2, player_id="bb", position="BB", stack=100.0),
            Player(seat_index=3, player_id="utg", position="UTG", stack=100.0),
            Player(seat_index=4, player_id="mp", position="MP", stack=100.0),
            Player(seat_index=5, player_id="villain", position="CO", stack=100.0),
        ]
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
            action_prefix=action_prefix,
        )

        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert ("aggregated_sixmax_100", TableType.SIX_MAX) in repo.called_with
        aks = get_hand_key_to_169_index()["AKs"]
        pocket_twos = get_hand_key_to_169_index()["22"]
        assert preflop_range.strategy[aks] > preflop_range.strategy[pocket_twos]

    def test_limp_preflop_rebuilds_even_if_preflop_range_exists(self) -> None:
        """玩家已有翻前范围时, 仍应基于 limp 前缀重建预测。"""

        class _Repo:
            def __init__(self) -> None:
                self.called_with: list[tuple[str, TableType]] = []
                self.stats = PlayerStats(
                    player_name="aggregated_sixmax_100",
                    table_type=TableType.SIX_MAX,
                )
                params = PreFlopParams(
                    table_type=TableType.SIX_MAX,
                    position=MetricsPosition.CO,
                    num_callers=1,
                    num_raises=0,
                    num_active_players=6,
                    previous_action=MetricsActionType.FOLD,
                    in_position_on_flop=False,
                )
                action_stats = self.stats.get_preflop_stats(params)
                action_stats.raise_samples = 0
                action_stats.check_call_samples = 1
                action_stats.fold_samples = 999

            def get(
                self,
                player_name: str,
                table_type: TableType,
            ) -> PlayerStats | None:
                self.called_with.append((player_name, table_type))
                if player_name == "aggregated_sixmax_100":
                    return self.stats
                return None

        strategy = PreflopStrategy(name="test", source_dir="/tmp")
        strategy.add_node(
            100,
            StrategyNode(
                history_full="C-F-C",
                history_actions="C-F-C",
                history_token_count=3,
                acting_position="CO",
                source_file="test.json",
                actions=(
                    StrategyAction(
                        order_index=0,
                        action_code="R2",
                        action_type="RAISE",
                        bet_size_bb=2.0,
                        is_all_in=False,
                        total_frequency=0.3,
                        next_position="BTN",
                        range=_range_with_single_hand_ev("AKs", 100.0),
                    ),
                    StrategyAction(
                        order_index=1,
                        action_code="R6",
                        action_type="RAISE",
                        bet_size_bb=6.0,
                        is_all_in=False,
                        total_frequency=0.2,
                        next_position="BTN",
                        range=_range_with_single_hand_ev("22", 200.0),
                    ),
                ),
            ),
        )

        repo = _Repo()
        predictor = create_opponent_range_predictor(
            preflop_strategy=strategy,
            stats_repo=repo,  # type: ignore[arg-type]
            table_type=TableType.SIX_MAX,
        )

        players = [
            Player(seat_index=0, player_id="btn", position="BTN", stack=100.0),
            Player(seat_index=1, player_id="sb", position="SB", stack=100.0),
            Player(seat_index=2, player_id="bb", position="BB", stack=100.0),
            Player(seat_index=3, player_id="utg", position="UTG", stack=100.0),
            Player(seat_index=4, player_id="mp", position="MP", stack=100.0),
            Player(seat_index=5, player_id="villain", position="CO", stack=100.0),
        ]

        preflop_state = ObservedTableState(
            player_count=6,
            btn_seat=0,
            hero_seat=0,
            street=Street.PREFLOP,
            big_blind=1.0,
            players=players,
        )
        # 先让该玩家在翻前有一次行动, 确保 _preflop_ranges 已存在该 seat。
        predictor.update_range_on_action(
            players[5],
            PlayerAction(
                player_index=5,
                action_type=ActionType.CALL,
                amount=1.0,
                street=Street.PREFLOP,
            ),
            preflop_state,
        )

        preflop_state_2 = ObservedTableState(
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
        preflop_action = PlayerAction(
            player_index=5,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        predictor.update_range_on_action(
            players[5],
            preflop_action,
            preflop_state_2,
            action_prefix=action_prefix,
        )

        preflop_range = predictor.get_preflop_range(5)
        assert preflop_range is not None
        assert ("aggregated_sixmax_100", TableType.SIX_MAX) in repo.called_with
        aks = get_hand_key_to_169_index()["AKs"]
        pocket_twos = get_hand_key_to_169_index()["22"]
        assert preflop_range.strategy[aks] > preflop_range.strategy[pocket_twos]

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
