"""player_metrics.builder 模块测试。

测试 extract_actions_from_hand_history, increment_player_stats, build_player_stats_from_hands
三个核心函数，覆盖各种场景。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pokerkit import HandHistory

from bayes_poker.player_metrics.builder import (
    ParsedAction,
    build_player_stats_from_hands,
    calculate_bet_sizing_category,
    extract_actions_from_hand_history,
    get_player_position,
    increment_player_stats,
    is_in_position,
)
from bayes_poker.player_metrics.enums import (
    ActionType,
    Position,
    PreflopPotType,
    Street,
    TableType,
)
from bayes_poker.player_metrics.models import BetSizingCategory, PlayerStats


# =============================================================================
# Fixtures
# =============================================================================


def _to_phhs_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if isinstance(value, list):
        return "[" + ", ".join(_to_phhs_value(v) for v in value) + "]"
    raise TypeError(f"Unsupported PHHS value type: {type(value)}")


def make_hand_history_from_dict(data: dict[str, Any]) -> HandHistory:
    lines: list[str] = []
    for key, value in data.items():
        lines.append(f"{key} = {_to_phhs_value(value)}")
    return HandHistory.loads("\n".join(lines) + "\n")


@pytest.fixture
def simple_6max_preflop_fold_hand() -> HandHistory:
    """6人桌翻前全部弃牌到 BB 的手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 f",
            "p6 f",
            "p1 f",
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def simple_6max_raise_call_hand() -> HandHistory:
    """6人桌翻前有加注和跟注的手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cbr 6",  # CO raise to 6
            "p6 f",
            "p1 f",
            "p2 cc",  # BB call
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def postflop_hand() -> HandHistory:
    """包含翻后行动的手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cbr 6",  # CO raise
            "p6 f",
            "p1 f",
            "p2 cc",  # BB call
            "d db 9dTc8h",  # Flop
            "p2 cc",  # BB check
            "p5 cbr 10",  # CO bet 10
            "p2 cc",  # BB call
            "d db Kc",  # Turn
            "p2 cc",  # BB check
            "p5 cbr 25",  # CO bet 25
            "p2 f",  # BB fold
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def heads_up_hand() -> HandHistory:
    """单挑手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0],
        "blinds_or_straddles": [1, 2],
        "min_bet": 2,
        "starting_stacks": [200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "p1 cbr 6",  # SB raise
            "p2 cc",  # BB call
            "d db AhKs9d",  # Flop
            "p2 cc",  # BB check
            "p1 cbr 8",  # SB bet
            "p2 cc",  # BB call
        ],
        "players": ["Player_SB", "Player_BB"],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def all_in_hand() -> HandHistory:
    """包含 all-in 的手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [50, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cbr 200",  # CO all-in
            "p6 f",
            "p1 f",
            "p2 f",
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def limp_pot_hand() -> HandHistory:
    """Limp pot（无人加注）手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cc",  # CO limp
            "p6 f",
            "p1 cc",  # SB complete
            "p2 cc",  # BB check
            "d db 9dTc8h",  # Flop
            "p1 cc",
            "p2 cc",
            "p5 cc",
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def three_bet_pot_hand() -> HandHistory:
    """3-bet pot 手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cbr 6",  # CO open
            "p6 cbr 18",  # BTN 3-bet
            "p1 f",
            "p2 f",
            "p5 cc",  # CO call
            "d db AhKs9d",  # Flop
            "p5 cc",
            "p6 cbr 25",
            "p5 cc",
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


@pytest.fixture
def river_complete_hand() -> HandHistory:
    """完整打到河牌的手牌。"""
    data = {
        "variant": "NT",
        "ante_trimming_status": False,
        "antes": [0, 0, 0, 0, 0, 0],
        "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
        "min_bet": 2,
        "starting_stacks": [200, 200, 200, 200, 200, 200],
        "actions": [
            "d dh p1 ????",
            "d dh p2 ????",
            "d dh p3 ????",
            "d dh p4 ????",
            "d dh p5 ????",
            "d dh p6 ????",
            "p3 f",
            "p4 f",
            "p5 cbr 6",
            "p6 f",
            "p1 f",
            "p2 cc",
            "d db 9dTc8h",  # Flop
            "p2 cc",
            "p5 cbr 10",
            "p2 cc",
            "d db Kc",  # Turn
            "p2 cc",
            "p5 cbr 20",
            "p2 cc",
            "d db 2s",  # River
            "p2 cc",
            "p5 cbr 50",
            "p2 cc",
        ],
        "players": [
            "Player_SB",
            "Player_BB",
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
        ],
    }
    return make_hand_history_from_dict(data)


# =============================================================================
# Helper function tests
# =============================================================================


class TestGetPlayerPosition:
    """get_player_position 函数测试。"""

    @pytest.mark.parametrize(
        "player_index,num_players,expected",
        [
            (0, 6, Position.SMALL_BLIND),
            (1, 6, Position.BIG_BLIND),
            (2, 6, Position.UTG),
            (3, 6, Position.HJ),
            (4, 6, Position.CO),
            (5, 6, Position.BUTTON),
            (0, 2, Position.SMALL_BLIND),
            (1, 2, Position.BIG_BLIND),
            (0, 3, Position.SMALL_BLIND),
            (1, 3, Position.BIG_BLIND),
            (2, 3, Position.BUTTON),
        ],
    )
    def test_get_player_position(
        self, player_index: int, num_players: int, expected: Position
    ) -> None:
        assert get_player_position(player_index, num_players) == expected

    def test_invalid_position_returns_empty(self) -> None:
        # 超出正常范围时返回 EMPTY
        result = get_player_position(10, 6)
        assert result == Position.EMPTY


class TestIsInPosition:
    """is_in_position 函数测试。"""

    def test_empty_active_players(self) -> None:
        assert is_in_position([], "Player1", 6) is False

    def test_heads_up_sb_in_position(self) -> None:
        # 单挑时，SB（第一个）是 IP
        assert is_in_position(["SB", "BB"], "SB", 2) is True
        assert is_in_position(["SB", "BB"], "BB", 2) is False

    def test_multiway_last_is_in_position(self) -> None:
        # 多人时，最后一个是 IP
        active = ["BB", "CO", "BTN"]
        assert is_in_position(active, "BTN", 6) is True
        assert is_in_position(active, "CO", 6) is False
        assert is_in_position(active, "BB", 6) is False


class TestCalculateBetSizingCategory:
    """calculate_bet_sizing_category 函数测试。"""

    @pytest.mark.parametrize(
        "bet_amount,pot_size,expected",
        [
            (30, 100, BetSizingCategory.BET_0_40),  # 30% pot
            (39, 100, BetSizingCategory.BET_0_40),  # 39% pot
            (40, 100, BetSizingCategory.BET_40_80),  # 40% pot
            (50, 100, BetSizingCategory.BET_40_80),  # 50% pot
            (79, 100, BetSizingCategory.BET_40_80),  # 79% pot
            (80, 100, BetSizingCategory.BET_80_120),  # 80% pot
            (100, 100, BetSizingCategory.BET_80_120),  # 100% pot
            (119, 100, BetSizingCategory.BET_80_120),  # 119% pot
            (120, 100, BetSizingCategory.BET_OVER_120),  # 120% pot
            (150, 100, BetSizingCategory.BET_OVER_120),  # 150% pot
            (100, 0, BetSizingCategory.BET_OVER_120),  # pot = 0
            (100, -1, BetSizingCategory.BET_OVER_120),  # pot < 0
        ],
    )
    def test_sizing_categories(
        self, bet_amount: int, pot_size: int, expected: str
    ) -> None:
        assert calculate_bet_sizing_category(bet_amount, pot_size) == expected


class TestParsedAction:
    """ParsedAction 类测试。"""

    def test_pot_percentage_bet(self) -> None:
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Player1",
            action_type=ActionType.BET,
            amount=50,
            pot_size_before_action=100,
            call_amount=0,
        )
        assert action.pot_percentage == 0.5

    def test_pot_percentage_raise(self) -> None:
        # RAISE: raise_increment / (pot + call_amount)
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Player1",
            action_type=ActionType.RAISE,
            amount=30,  # total raise to 30
            pot_size_before_action=100,  # 底池 100 (包含对手的 bet)
            call_amount=10,  # 需要跟注 10
        )
        # raise_increment = 30 - 10 = 20
        # pot_after_call = 100 + 10 = 110
        # percentage = 20 / 110 ≈ 0.1818
        assert action.pot_percentage == pytest.approx(20 / 110, rel=1e-3)

    def test_pot_percentage_zero_pot(self) -> None:
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Player1",
            action_type=ActionType.BET,
            amount=50,
            pot_size_before_action=0,
            call_amount=0,
        )
        assert action.pot_percentage is None

    def test_pot_percentage_fold(self) -> None:
        action = ParsedAction(
            street=Street.PREFLOP,
            player_name="Player1",
            action_type=ActionType.FOLD,
            amount=0,
            pot_size_before_action=100,
            call_amount=0,
        )
        assert action.pot_percentage is None

    def test_pot_percentage_check(self) -> None:
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Player1",
            action_type=ActionType.CHECK,
            amount=0,
            pot_size_before_action=100,
            call_amount=0,
        )
        assert action.pot_percentage is None

    def test_pot_percentage_call(self) -> None:
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Player1",
            action_type=ActionType.CALL,
            amount=10,
            pot_size_before_action=100,
            call_amount=10,
        )
        assert action.pot_percentage is None


# =============================================================================
# extract_actions_from_hand_history tests
# =============================================================================


class TestExtractActionsFromHandHistory:
    """extract_actions_from_hand_history 函数测试。"""

    def test_simple_preflop_folds(
        self, simple_6max_preflop_fold_hand: HandHistory
    ) -> None:
        """测试翻前弃牌手牌的 action 提取。"""
        actions = list(extract_actions_from_hand_history(simple_6max_preflop_fold_hand))

        # UTG, HJ, CO, BTN, SB fold -> 5 actions
        assert len(actions) == 5

        # 验证所有动作都是 FOLD
        for action in actions:
            assert action.action_type == ActionType.FOLD
            assert action.street == Street.PREFLOP

        # 验证玩家顺序
        expected_players = [
            "Player_UTG",
            "Player_HJ",
            "Player_CO",
            "Player_BTN",
            "Player_SB",
        ]
        actual_players = [a.player_name for a in actions]
        assert actual_players == expected_players

    def test_raise_and_call(self, simple_6max_raise_call_hand: HandHistory) -> None:
        """测试加注和跟注的 action 提取。"""
        actions = list(extract_actions_from_hand_history(simple_6max_raise_call_hand))

        # p3 f, p4 f, p5 cbr, p6 f, p1 f, p2 cc -> 6 actions
        assert len(actions) == 6

        # 验证加注
        raise_action = [a for a in actions if a.action_type == ActionType.RAISE]
        assert len(raise_action) == 1
        assert raise_action[0].player_name == "Player_CO"
        assert raise_action[0].amount == 6

        # 验证跟注
        call_action = [a for a in actions if a.action_type == ActionType.CALL]
        assert len(call_action) == 1
        assert call_action[0].player_name == "Player_BB"

    def test_postflop_actions(self, postflop_hand: HandHistory) -> None:
        """测试翻后行动的提取。"""
        actions = list(extract_actions_from_hand_history(postflop_hand))

        # 验证有不同街的 action
        streets = {a.street for a in actions}
        assert Street.PREFLOP in streets
        assert Street.FLOP in streets
        assert Street.TURN in streets

        # 验证翻牌圈和转牌圈的动作
        flop_actions = [a for a in actions if a.street == Street.FLOP]
        assert len(flop_actions) == 3

        turn_actions = [a for a in actions if a.street == Street.TURN]
        assert len(turn_actions) == 3  # check, bet, fold

    def test_heads_up_actions(self, heads_up_hand: HandHistory) -> None:
        """测试单挑手牌的 action 提取。"""
        actions = list(extract_actions_from_hand_history(heads_up_hand))

        # 验证玩家名称
        player_names = {a.player_name for a in actions}
        assert player_names == {"Player_SB", "Player_BB"}

        # 验证翻前和翻后都有动作
        preflop = [a for a in actions if a.street == Street.PREFLOP]
        flop = [a for a in actions if a.street == Street.FLOP]
        assert len(preflop) > 0
        assert len(flop) > 0

    def test_pot_tracking(self, simple_6max_raise_call_hand: HandHistory) -> None:
        """测试底池追踪。"""
        actions = list(extract_actions_from_hand_history(simple_6max_raise_call_hand))

        # 初始底池: SB(1) + BB(2) = 3
        # CO raise 后的底池: 3 + (6 - 0) = 9
        # 找到 BB call 的动作
        bb_call = [
            a
            for a in actions
            if a.player_name == "Player_BB" and a.action_type == ActionType.CALL
        ]
        assert len(bb_call) == 1
        # pot_size_before_action 应该是 9 (初始 3 + CO 的 6)
        assert bb_call[0].pot_size_before_action == 9

    def test_river_complete(self, river_complete_hand: HandHistory) -> None:
        """测试完整的河牌手牌。"""
        actions = list(extract_actions_from_hand_history(river_complete_hand))

        streets = {a.street for a in actions}
        assert Street.RIVER in streets

        river_actions = [a for a in actions if a.street == Street.RIVER]
        assert len(river_actions) >= 2  # check, bet, call

    def test_empty_hand_history(self) -> None:
        """测试空手牌历史。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [200, 200],
            "actions": [],
            "players": ["Player_SB", "Player_BB"],
        }
        hh = make_hand_history_from_dict(data)
        actions = list(extract_actions_from_hand_history(hh))
        assert len(actions) == 0

    def test_action_with_invalid_format_ignored(self) -> None:
        """测试无效格式的 action 被忽略。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "p1 cbr 6",  # 有效
                "",  # 空字符串
                "x",  # 单字符
                "p2 cc",  # 有效
            ],
            "players": ["Player_SB", "Player_BB"],
        }
        hh = make_hand_history_from_dict(data)
        actions = list(extract_actions_from_hand_history(hh))
        # 只有 2 个有效 action
        assert len(actions) == 2


# =============================================================================
# increment_player_stats tests
# =============================================================================


class TestIncrementPlayerStats:
    """increment_player_stats 函数测试。"""

    def test_player_not_in_hand(self) -> None:
        """测试玩家不在这手牌中。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [200, 200],
            "actions": ["d dh p1 ????", "d dh p2 ????", "p1 f"],
            "players": ["Player_A", "Player_B"],
        }
        hh = make_hand_history_from_dict(data)
        stats = PlayerStats(player_name="NotInHand", table_type=TableType.HEADS_UP)

        # VPIP 应该为初始值
        old_vpip_total = stats.vpip.total
        increment_player_stats(stats, hh)
        assert stats.vpip.total == old_vpip_total  # 未改变

    def test_vpip_tracking_fold(
        self, simple_6max_preflop_fold_hand: HandHistory
    ) -> None:
        """测试 VPIP 追踪 - 弃牌。"""
        stats = PlayerStats(player_name="Player_UTG", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, simple_6max_preflop_fold_hand)

        # UTG 弃牌，VPIP = 0
        assert stats.vpip.total == 1
        assert stats.vpip.positive == 0

    def test_vpip_tracking_call(self, simple_6max_raise_call_hand: HandHistory) -> None:
        """测试 VPIP 追踪 - 跟注。"""
        stats = PlayerStats(player_name="Player_BB", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, simple_6max_raise_call_hand)

        # BB 跟注，VPIP = 1
        assert stats.vpip.total == 1
        assert stats.vpip.positive == 1

    def test_vpip_tracking_raise(
        self, simple_6max_raise_call_hand: HandHistory
    ) -> None:
        """测试 VPIP 追踪 - 加注。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, simple_6max_raise_call_hand)

        # CO 加注，VPIP = 1
        assert stats.vpip.total == 1
        assert stats.vpip.positive == 1

    def test_preflop_stats_increment(
        self, simple_6max_raise_call_hand: HandHistory
    ) -> None:
        """测试翻前统计更新。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, simple_6max_raise_call_hand)

        # 检查 preflop_stats 中有样本
        total_samples = sum(s.total_samples() for s in stats.preflop_stats)
        assert total_samples > 0

    def test_postflop_stats_increment(self, postflop_hand: HandHistory) -> None:
        """测试翻后统计更新。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, postflop_hand)

        # 检查 postflop_stats 中有样本
        total_samples = sum(s.total_samples() for s in stats.postflop_stats)
        assert total_samples > 0

    def test_heads_up_stats(self, heads_up_hand: HandHistory) -> None:
        """测试单挑统计。"""
        stats = PlayerStats(player_name="Player_SB", table_type=TableType.HEADS_UP)
        increment_player_stats(stats, heads_up_hand)

        assert stats.vpip.total == 1
        assert stats.vpip.positive == 1

    def test_all_in_tracking(self, all_in_hand: HandHistory) -> None:
        """测试 all-in 追踪。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, all_in_hand)

        # CO all-in，VPIP = 1
        assert stats.vpip.total == 1
        assert stats.vpip.positive == 1

    def test_multiple_hands_accumulate(
        self,
        simple_6max_preflop_fold_hand: HandHistory,
        simple_6max_raise_call_hand: HandHistory,
    ) -> None:
        """测试多手牌累积。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)

        # 第一手：CO 弃牌
        increment_player_stats(stats, simple_6max_preflop_fold_hand)
        assert stats.vpip.total == 1
        assert stats.vpip.positive == 0

        # 第二手：CO 加注
        increment_player_stats(stats, simple_6max_raise_call_hand)
        assert stats.vpip.total == 2
        assert stats.vpip.positive == 1

    def test_limp_pot_postflop(self, limp_pot_hand: HandHistory) -> None:
        """测试 limp pot 翻后。"""
        stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, limp_pot_hand)

        # CO limp 进底池
        assert stats.vpip.positive == 1

    def test_three_bet_pot_postflop(self, three_bet_pot_hand: HandHistory) -> None:
        """测试 3-bet pot 翻后。"""
        # BTN 是 3-bet 的发起者
        stats = PlayerStats(player_name="Player_BTN", table_type=TableType.SIX_MAX)
        increment_player_stats(stats, three_bet_pot_hand)

        # BTN 3bet 进底池
        assert stats.vpip.positive == 1

        # 检查 postflop_stats 中有样本
        total_samples = sum(s.total_samples() for s in stats.postflop_stats)
        assert total_samples > 0


# =============================================================================
# build_player_stats_from_hands tests
# =============================================================================


class TestBuildPlayerStatsFromHands:
    """build_player_stats_from_hands 函数测试。"""

    def test_empty_hands_list(self) -> None:
        """测试空手牌列表。"""
        result = build_player_stats_from_hands([], TableType.SIX_MAX)
        assert result == {}

    def test_single_hand(self, simple_6max_raise_call_hand: HandHistory) -> None:
        """测试单手牌。"""
        result = build_player_stats_from_hands(
            [simple_6max_raise_call_hand], TableType.SIX_MAX
        )

        # 应该有 6 个玩家
        assert len(result) == 6
        assert "Player_SB" in result
        assert "Player_BB" in result
        assert "Player_CO" in result

        # 验证 VPIP
        assert result["Player_CO"].vpip.positive == 1  # 加注
        assert result["Player_BB"].vpip.positive == 1  # 跟注
        assert result["Player_UTG"].vpip.positive == 0  # 弃牌

    def test_multiple_hands(
        self,
        simple_6max_preflop_fold_hand: HandHistory,
        simple_6max_raise_call_hand: HandHistory,
        postflop_hand: HandHistory,
    ) -> None:
        """测试多手牌。"""
        hands = [
            simple_6max_preflop_fold_hand,
            simple_6max_raise_call_hand,
            postflop_hand,
        ]
        result = build_player_stats_from_hands(hands, TableType.SIX_MAX)

        # 验证累积
        assert result["Player_CO"].vpip.total == 3  # 3 手牌

    def test_different_players_across_hands(self) -> None:
        """测试不同手牌中的不同玩家。"""
        hand1_data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 f",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",
            ],
            "players": ["Alice", "Bob", "Charlie", "David", "Eve", "Frank"],
        }
        hand2_data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 cbr 6",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",
                "p2 cc",
            ],
            "players": [
                "George",
                "Helen",
                "Alice",
                "Ivan",
                "Julia",
                "Kevin",
            ],  # Alice 出现在两手
        }
        hand1 = make_hand_history_from_dict(hand1_data)
        hand2 = make_hand_history_from_dict(hand2_data)

        result = build_player_stats_from_hands([hand1, hand2], TableType.SIX_MAX)

        # 应该包含所有玩家
        all_players = {
            "Alice",
            "Bob",
            "Charlie",
            "David",
            "Eve",
            "Frank",
            "George",
            "Helen",
            "Ivan",
            "Julia",
            "Kevin",
        }
        assert set(result.keys()) == all_players

        # Alice 出现在两手
        assert result["Alice"].vpip.total == 2

    def test_heads_up_table_type(self, heads_up_hand: HandHistory) -> None:
        """测试单挑桌型。"""
        result = build_player_stats_from_hands([heads_up_hand], TableType.HEADS_UP)

        assert len(result) == 2
        assert result["Player_SB"].table_type == TableType.HEADS_UP
        assert result["Player_BB"].table_type == TableType.HEADS_UP

    def test_hand_with_no_players(self) -> None:
        """测试没有玩家的手牌（边界情况）。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [],
            "blinds_or_straddles": [],
            "min_bet": 2,
            "starting_stacks": [],
            "actions": [],
            "players": [],
        }
        hh = make_hand_history_from_dict(data)
        result = build_player_stats_from_hands([hh], TableType.SIX_MAX)
        assert result == {}


# =============================================================================
# Real phhs file integration tests
# =============================================================================


class TestRealPhhs:
    """使用真实 phhs 文件的集成测试。"""

    PHHS_DIR = Path("/home/autumn/project/bayes_poker/data/outputs")

    @pytest.fixture
    def sample_phhs_file(self) -> Path:
        """获取一个样本 phhs 文件。"""
        if not self.PHHS_DIR.exists():
            pytest.skip("data/outputs 目录不存在")
        phhs_files = list(self.PHHS_DIR.glob("*.phhs"))
        if not phhs_files:
            pytest.skip("没有找到 phhs 文件")
        phhs_files.sort(key=lambda f: f.stat().st_size)
        return phhs_files[0]

    def _load_hands_from_phhs(
        self, phhs_path: Path, max_hands: int = 100
    ) -> list[HandHistory]:
        hands: list[HandHistory] = []
        with phhs_path.open("rb") as fp:
            for hh in HandHistory.load_all(fp):
                hands.append(hh)
                if len(hands) >= max_hands:
                    break
        return hands

    def test_load_and_extract_actions(self, sample_phhs_file: Path) -> None:
        """测试从真实文件加载并提取 actions。"""
        hands = self._load_hands_from_phhs(sample_phhs_file, max_hands=10)
        assert len(hands) > 0

        for hh in hands:
            actions = list(extract_actions_from_hand_history(hh))
            # 每手牌应该有一些 actions
            # （除非是非常特殊的情况，如全员坐出）
            for action in actions:
                assert isinstance(action, ParsedAction)
                assert action.street in (
                    Street.PREFLOP,
                    Street.FLOP,
                    Street.TURN,
                    Street.RIVER,
                    Street.UNKNOWN,
                )
                assert isinstance(action.action_type, ActionType)

    def test_build_stats_from_real_hands(self, sample_phhs_file: Path) -> None:
        """测试从真实文件构建玩家统计。"""
        hands = self._load_hands_from_phhs(sample_phhs_file, max_hands=50)
        if not hands:
            pytest.skip("无法加载手牌")

        # 判断桌型
        num_players = len(hands[0].players) if hands[0].players else 6
        table_type = TableType.HEADS_UP if num_players == 2 else TableType.SIX_MAX

        result = build_player_stats_from_hands(hands, table_type)

        assert len(result) > 0

        # 验证每个玩家的统计数据
        for player_name, stats in result.items():
            assert stats.player_name == player_name
            assert stats.table_type == table_type
            assert stats.vpip.total > 0 or len(hands) == 1  # 至少有一些样本

    def test_increment_stats_all_hands(self, sample_phhs_file: Path) -> None:
        """测试对所有手牌增量更新统计。"""
        hands = self._load_hands_from_phhs(sample_phhs_file, max_hands=20)
        if not hands:
            pytest.skip("无法加载手牌")

        # 取第一个玩家
        first_player = list(hands[0].players)[0] if hands[0].players else None
        if not first_player:
            pytest.skip("无法获取玩家名")

        num_players = len(hands[0].players) if hands[0].players else 6
        table_type = TableType.HEADS_UP if num_players == 2 else TableType.SIX_MAX

        stats = PlayerStats(player_name=first_player, table_type=table_type)

        hands_with_player = 0
        for hh in hands:
            if first_player in (hh.players or []):
                increment_player_stats(stats, hh)
                hands_with_player += 1

        # VPIP total 应该等于该玩家参与的手牌数
        assert stats.vpip.total == hands_with_player

    @pytest.mark.parametrize("file_index", range(3))
    def test_multiple_phhs_files(self, file_index: int) -> None:
        """测试多个不同的 phhs 文件。"""
        if not self.PHHS_DIR.exists():
            pytest.skip("data/outputs 目录不存在")
        phhs_files = list(self.PHHS_DIR.glob("*.phhs"))
        phhs_files.sort(key=lambda f: f.stat().st_size)
        if len(phhs_files) <= file_index:
            pytest.skip(f"phhs 文件不足 {file_index + 1} 个")

        phhs_file = phhs_files[file_index]
        hands = self._load_hands_from_phhs(phhs_file, max_hands=10)
        if not hands:
            pytest.skip(f"无法从 {phhs_file.name} 加载手牌")

        num_players = len(hands[0].players) if hands[0].players else 6
        table_type = TableType.HEADS_UP if num_players == 2 else TableType.SIX_MAX

        result = build_player_stats_from_hands(hands, table_type)
        assert len(result) > 0


class TestRealPhhs6Max:
    """专门测试 6-max 真实手牌。"""

    PHHS_DIR = Path("/home/autumn/project/bayes_poker/data/outputs")

    def _load_6max_hands(self, max_hands: int = 50) -> list[HandHistory]:
        """加载 6-max 手牌。"""
        if not self.PHHS_DIR.exists():
            return []

        hands: list[HandHistory] = []
        phhs_files = list(self.PHHS_DIR.glob("*.phhs"))
        phhs_files.sort(key=lambda f: f.stat().st_size)

        for phhs_file in phhs_files[:5]:
            try:
                with phhs_file.open("rb") as fp:
                    for hh in HandHistory.load_all(fp):
                        if hh.players and len(hh.players) == 6:
                            hands.append(hh)
                            if len(hands) >= max_hands:
                                return hands
            except Exception:
                continue

        return hands

    def test_6max_vpip_range(self) -> None:
        """测试 6-max VPIP 在合理范围内。"""
        hands = self._load_6max_hands(100)
        if len(hands) < 10:
            pytest.skip("6-max 手牌数量不足")

        result = build_player_stats_from_hands(hands, TableType.SIX_MAX)

        for player_name, stats in result.items():
            if stats.vpip.total >= 10:  # 至少 10 手样本
                vpip_rate = stats.vpip.to_float()
                # VPIP 应该在 0 到 1 之间
                assert 0.0 <= vpip_rate <= 1.0

    def test_6max_preflop_action_distribution(self) -> None:
        """测试 6-max 翻前动作分布。"""
        hands = self._load_6max_hands(50)
        if len(hands) < 5:
            pytest.skip("6-max 手牌数量不足")

        all_actions: list[ParsedAction] = []
        for hh in hands:
            all_actions.extend(extract_actions_from_hand_history(hh))

        preflop_actions = [a for a in all_actions if a.street == Street.PREFLOP]

        if not preflop_actions:
            pytest.skip("没有翻前动作")

        # 统计动作类型分布
        action_counts: dict[ActionType, int] = {}
        for action in preflop_actions:
            action_counts[action.action_type] = (
                action_counts.get(action.action_type, 0) + 1
            )

        # 应该有多种动作类型
        assert len(action_counts) > 1
        # FOLD 应该是最常见的动作之一
        assert ActionType.FOLD in action_counts

    def test_6max_postflop_streets(self) -> None:
        """测试 6-max 翻后各街动作。"""
        hands = self._load_6max_hands(100)
        if len(hands) < 10:
            pytest.skip("6-max 手牌数量不足")

        all_actions: list[ParsedAction] = []
        for hh in hands:
            all_actions.extend(extract_actions_from_hand_history(hh))

        # 统计各街动作
        street_counts: dict[Street, int] = {}
        for action in all_actions:
            street_counts[action.street] = street_counts.get(action.street, 0) + 1

        # 应该有 preflop
        assert Street.PREFLOP in street_counts

        # 可能有 flop/turn/river（取决于手牌内容）
        # 只验证数据结构正确


class TestEdgeCases:
    """边界情况测试。"""

    def test_player_folds_immediately_after_posting_blind(self) -> None:
        """测试玩家发完盲注后立即弃牌。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 cbr 6",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",  # SB 发完盲后弃牌
                "p2 f",  # BB 面对加注弃牌
            ],
            "players": [
                "Player_SB",
                "Player_BB",
                "Player_UTG",
                "Player_HJ",
                "Player_CO",
                "Player_BTN",
            ],
        }
        hh = make_hand_history_from_dict(data)

        sb_stats = PlayerStats(player_name="Player_SB", table_type=TableType.SIX_MAX)
        increment_player_stats(sb_stats, hh)

        # SB 弃牌，VPIP = 0（盲注不算主动投入）
        assert sb_stats.vpip.positive == 0

    def test_big_blind_walks(self) -> None:
        """测试大盲位自动赢得底池（其他人全弃）。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 f",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",
            ],
            "players": [
                "Player_SB",
                "Player_BB",
                "Player_UTG",
                "Player_HJ",
                "Player_CO",
                "Player_BTN",
            ],
        }
        hh = make_hand_history_from_dict(data)

        bb_stats = PlayerStats(player_name="Player_BB", table_type=TableType.SIX_MAX)
        increment_player_stats(bb_stats, hh)

        # BB 没有主动行动，VPIP = 0
        assert bb_stats.vpip.positive == 0

    def test_check_back_on_river(self) -> None:
        """测试河牌圈 check back。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "p1 cc",
                "p2 cc",
                "d db 9dTc8h",
                "p1 cc",
                "p2 cc",
                "d db Kc",
                "p1 cc",
                "p2 cc",
                "d db 2s",
                "p1 cc",
                "p2 cc",
            ],
            "players": ["Player_SB", "Player_BB"],
        }
        hh = make_hand_history_from_dict(data)

        actions = list(extract_actions_from_hand_history(hh))
        river_actions = [a for a in actions if a.street == Street.RIVER]

        assert len(river_actions) == 2
        assert all(a.action_type == ActionType.CHECK for a in river_actions)

    def test_all_in_less_than_call(self) -> None:
        """测试 all-in 金额小于跟注金额（short stack）。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [5, 200],  # SB 只有 5 筹码
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "p1 cbr 5",  # SB all-in 5 (相当于 raise)
                "p2 cc",  # BB call
            ],
            "players": ["Player_SB", "Player_BB"],
        }
        hh = make_hand_history_from_dict(data)

        sb_stats = PlayerStats(player_name="Player_SB", table_type=TableType.HEADS_UP)
        increment_player_stats(sb_stats, hh)

        assert sb_stats.vpip.positive == 1

    def test_straddle_present(self) -> None:
        """测试有 straddle 的情况。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 4, 0, 0, 0],  # UTG straddle
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",
                "p2 f",
            ],
            "players": [
                "Player_SB",
                "Player_BB",
                "Player_UTG",
                "Player_HJ",
                "Player_CO",
                "Player_BTN",
            ],
        }
        hh = make_hand_history_from_dict(data)

        actions = list(extract_actions_from_hand_history(hh))
        # 应该有 5 个 fold 动作
        assert len(actions) == 5

    def test_ante_game(self) -> None:
        """测试有 ante 的游戏。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [1, 1, 1, 1, 1, 1],  # 每人 1 ante
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 cbr 6",
                "p4 f",
                "p5 f",
                "p6 f",
                "p1 f",
                "p2 cc",
            ],
            "players": [
                "Player_SB",
                "Player_BB",
                "Player_UTG",
                "Player_HJ",
                "Player_CO",
                "Player_BTN",
            ],
        }
        hh = make_hand_history_from_dict(data)

        actions = list(extract_actions_from_hand_history(hh))
        # 初始 pot = 6 (antes) + 3 (blinds) = 9
        utg_raise = [a for a in actions if a.player_name == "Player_UTG"]
        assert len(utg_raise) == 1
        assert utg_raise[0].pot_size_before_action == 9


class TestStatisticsAccuracy:
    """统计准确性测试。"""

    def test_preflop_raise_count(self) -> None:
        """测试翻前加注次数追踪。"""
        # 3-bet pot
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0, 0, 0, 0, 0],
            "blinds_or_straddles": [1, 2, 0, 0, 0, 0],
            "min_bet": 2,
            "starting_stacks": [200, 200, 200, 200, 200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "d dh p3 ????",
                "d dh p4 ????",
                "d dh p5 ????",
                "d dh p6 ????",
                "p3 f",
                "p4 f",
                "p5 cbr 6",  # Open
                "p6 cbr 18",  # 3-bet
                "p1 f",
                "p2 f",
                "p5 cc",  # Call 3-bet
            ],
            "players": [
                "Player_SB",
                "Player_BB",
                "Player_UTG",
                "Player_HJ",
                "Player_CO",
                "Player_BTN",
            ],
        }
        hh = make_hand_history_from_dict(data)

        co_stats = PlayerStats(player_name="Player_CO", table_type=TableType.SIX_MAX)
        increment_player_stats(co_stats, hh)

        btn_stats = PlayerStats(player_name="Player_BTN", table_type=TableType.SIX_MAX)
        increment_player_stats(btn_stats, hh)

        # 两人都有 VPIP
        assert co_stats.vpip.positive == 1
        assert btn_stats.vpip.positive == 1

    def test_bet_sizing_distribution(self) -> None:
        """测试下注尺寸分布。"""
        data = {
            "variant": "NT",
            "ante_trimming_status": False,
            "antes": [0, 0],
            "blinds_or_straddles": [1, 2],
            "min_bet": 2,
            "starting_stacks": [200, 200],
            "actions": [
                "d dh p1 ????",
                "d dh p2 ????",
                "p1 cc",
                "p2 cc",
                "d db 9dTc8h",
                "p1 cc",
                "p2 cbr 2",  # 50% pot bet (pot = 4)
                "p1 cc",
            ],
            "players": ["Player_SB", "Player_BB"],
        }
        hh = make_hand_history_from_dict(data)

        bb_stats = PlayerStats(player_name="Player_BB", table_type=TableType.HEADS_UP)
        increment_player_stats(bb_stats, hh)

        # 检查 postflop stats 中有下注样本
        total_bet_samples = sum(s.bet_samples for s in bb_stats.postflop_stats)
        assert total_bet_samples >= 1
