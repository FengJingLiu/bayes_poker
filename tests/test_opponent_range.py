"""对手范围预测器测试。

测试 OpponentRangePredictor 的 preflop 和 postflop 范围更新逻辑。
"""

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.strategy.opponent_range import (
    OpponentRangePredictor,
    create_opponent_range_predictor,
)
from bayes_poker.strategy.range import PreflopRange, PostflopRange
from bayes_poker.table.observed_state import (
    Player,
    ObservedTableState,
    PlayerAction,
)


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
        """测试翻后范围从翻前范围展开。"""
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

        # 验证 postflop 范围已创建
        postflop_range = predictor.get_postflop_range(player.seat_index)
        assert postflop_range is not None
        assert isinstance(postflop_range, PostflopRange)
        # 范围应该小于 1（因为公共牌阻挡 + 行动收窄）
        assert postflop_range.total_frequency() < 1.0

    def test_board_blockers_applied(self) -> None:
        """测试公共牌阻挡效果。"""
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

        # 所有包含 A 的组合应该被排除
        postflop_range = predictor.get_postflop_range(player.seat_index)
        assert postflop_range is not None
        freq = postflop_range.total_frequency()
        assert freq < 1.0

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
