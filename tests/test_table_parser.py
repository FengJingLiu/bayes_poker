"""牌桌解析模块测试。

使用现有截图验证解析功能。
"""

from __future__ import annotations

import pytest
import numpy as np
from pathlib import Path

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import (
    Position as DomainPosition,
    Player,
    PlayerAction,
    get_position_by_seat as get_domain_position_by_seat,
)
from bayes_poker.ocr.schema import (
    Point,
    RelativePoint,
    Area,
    RelativeArea,
    Color,
)
from bayes_poker.table.layout.base import (
    ScaledLayout,
    get_position_by_seat,
    SEAT_ORDER_6MAX,
)
from bayes_poker.table.layout.gg_6max import (
    GGPoker6MaxLayout,
    get_gg_6max_layout,
    BASE_WIDTH,
    BASE_HEIGHT,
)
from bayes_poker.table.observed_state import ObservedTableState, create_observed_state


class TestPoint:
    def test_scale(self) -> None:
        p = Point(100, 200)
        scaled = p.scale(2.0)
        assert scaled.x == 200
        assert scaled.y == 400

    def test_to_relative(self) -> None:
        p = Point(100, 200)
        rel = p.to_relative(1000, 1000)
        assert rel.x == 0.1
        assert rel.y == 0.2


class TestRelativePoint:
    def test_to_absolute(self) -> None:
        rel = RelativePoint(0.5, 0.25)
        abs_point = rel.to_absolute(1000, 800)
        assert abs_point.x == 500
        assert abs_point.y == 200


class TestArea:
    def test_from_xywh(self) -> None:
        area = Area.from_xywh(10, 20, 100, 50)
        assert area.x1 == 10
        assert area.y1 == 20
        assert area.x2 == 110
        assert area.y2 == 70
        assert area.width == 100
        assert area.height == 50

    def test_center(self) -> None:
        area = Area(0, 0, 100, 100)
        center = area.center
        assert center.x == 50
        assert center.y == 50

    def test_crop(self) -> None:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[20:40, 30:50] = 255

        area = Area(30, 20, 50, 40)
        cropped = area.crop(img)

        assert cropped.shape == (20, 20, 3)
        assert cropped[0, 0, 0] == 255


class TestColor:
    def test_like_same_color(self) -> None:
        c1 = Color(100, 150, 200)
        c2 = Color(100, 150, 200)
        assert c1.like(c2)

    def test_like_within_tolerance(self) -> None:
        c1 = Color(100, 150, 200)
        c2 = Color(110, 160, 210)
        assert c1.like(c2, tolerance=20)

    def test_like_outside_tolerance(self) -> None:
        c1 = Color(100, 150, 200)
        c2 = Color(150, 150, 200)
        assert not c1.like(c2, tolerance=20)

    def test_point_like(self) -> None:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[50, 50] = [200, 150, 100]  # BGR

        color = Color(100, 150, 200)  # RGB
        point = Point(50, 50)

        assert color.point_like(img, point)


class TestPosition:
    def test_domain_table_exports_position_tools(self) -> None:
        assert DomainPosition.BTN.value == "BTN"
        assert get_domain_position_by_seat(0, 0, 6) == DomainPosition.BTN

    def test_get_position_by_seat_btn_is_seat_0(self) -> None:
        assert get_position_by_seat(0, 0, 6) == DomainPosition.BTN
        assert get_position_by_seat(1, 0, 6) == DomainPosition.SB
        assert get_position_by_seat(2, 0, 6) == DomainPosition.BB
        assert get_position_by_seat(3, 0, 6) == DomainPosition.UTG
        assert get_position_by_seat(4, 0, 6) == DomainPosition.MP
        assert get_position_by_seat(5, 0, 6) == DomainPosition.CO

    def test_get_position_by_seat_btn_is_seat_3(self) -> None:
        assert get_position_by_seat(3, 3, 6) == DomainPosition.BTN
        assert get_position_by_seat(4, 3, 6) == DomainPosition.SB
        assert get_position_by_seat(5, 3, 6) == DomainPosition.BB
        assert get_position_by_seat(0, 3, 6) == DomainPosition.UTG
        assert get_position_by_seat(1, 3, 6) == DomainPosition.MP
        assert get_position_by_seat(2, 3, 6) == DomainPosition.CO


class TestGGPoker6MaxLayout:
    def test_base_dimensions(self) -> None:
        layout = get_gg_6max_layout()
        assert layout.base_width == 1491
        assert layout.base_height == 1056
        assert layout.player_count == 6

    def test_get_player_config_valid_index(self) -> None:
        layout = get_gg_6max_layout()
        for i in range(6):
            config = layout.get_player_config(i)
            assert config is not None
            assert config.id_ocr is not None
            assert config.chip_ocr is not None

    def test_get_player_config_invalid_index(self) -> None:
        layout = get_gg_6max_layout()
        with pytest.raises(IndexError):
            layout.get_player_config(6)

    def test_get_table_config(self) -> None:
        layout = get_gg_6max_layout()
        config = layout.get_table_config()
        assert config is not None
        assert config.hero_left_card_rank_ocr is not None
        assert len(config.board_rank_ocr_areas) == 5


class TestScaledLayout:
    def test_scale_preserves_proportions(self) -> None:
        layout = get_gg_6max_layout()

        scaled = ScaledLayout(
            layout=layout,
            actual_width=layout.base_width * 2,
            actual_height=layout.base_height * 2,
        )

        area1 = scaled.get_player_id_ocr_area(0)

        scaled_half = ScaledLayout(
            layout=layout,
            actual_width=layout.base_width,
            actual_height=layout.base_height,
        )
        area2 = scaled_half.get_player_id_ocr_area(0)

        assert area1.x1 == area2.x1 * 2
        assert area1.y1 == area2.y1 * 2


class TestObservedTableState:
    """ObservedTableState 测试。"""

    def test_create_observed_state(self) -> None:
        """测试创建观察者状态。"""
        state = create_observed_state(
            player_count=6,
            small_blind=0.5,
            big_blind=1.0,
        )
        assert state.player_count == 6
        assert state.small_blind == 0.5
        assert state.big_blind == 1.0
        assert state.street == Street.PREFLOP

    def test_record_action(self) -> None:
        """测试记录动作。"""
        state = create_observed_state()

        state.record_action(0, ActionType.FOLD)
        assert len(state.action_history) == 1
        assert state.action_history[0].action_type == ActionType.FOLD
        assert state.state_version == 1

        state.record_action(1, ActionType.RAISE, 3.0)
        assert len(state.action_history) == 2
        assert state.action_history[1].amount == 3.0
        assert state.state_version == 2

    def test_enter_new_street(self) -> None:
        """测试进入新街道。"""
        state = create_observed_state()

        state.enter_new_street(Street.FLOP, ["As", "Kh", "Qd"])
        assert state.street == Street.FLOP
        assert state.board_cards == ["As", "Kh", "Qd"]

    def test_get_hero_position(self) -> None:
        """测试获取 Hero 位置。"""
        state = create_observed_state()
        state.btn_seat = 0
        state.hero_seat = 0
        assert state.get_hero_position() == "BTN"

        state.hero_seat = 1
        assert state.get_hero_position() == "SB"

        state.hero_seat = 2
        assert state.get_hero_position() == "BB"

    def test_get_action_history_string(self) -> None:
        """测试获取动作历史字符串。"""
        state = create_observed_state()

        state.record_action(0, ActionType.FOLD)
        state.record_action(1, ActionType.CALL)
        state.record_action(2, ActionType.RAISE, 3.0)

        history = state.get_action_history_string()
        assert history == "F-C-R3"

    def test_to_dict_and_from_dict(self) -> None:
        """测试序列化和反序列化。"""
        state = create_observed_state()
        state.btn_seat = 2
        state.hero_seat = 0
        state.hero_cards = ("As", "Kd")
        state.record_action(0, ActionType.RAISE, 3.0)

        # 序列化
        data = state.to_dict()
        assert data["btn_seat"] == 2
        assert data["hero_cards"] == ["As", "Kd"]
        assert len(data["action_history"]) == 1

        # 反序列化
        restored = ObservedTableState.from_dict(data)
        assert restored.btn_seat == 2
        assert restored.hero_cards == ("As", "Kd")
        assert len(restored.action_history) == 1
        assert restored.action_history[0].amount == 3.0

    def test_to_json_and_from_json(self) -> None:
        """测试 JSON 序列化和反序列化。"""
        state = create_observed_state()
        state.pot = 10.5
        state.board_cards = ["As", "Kh", "Qd"]

        json_str = state.to_json()
        restored = ObservedTableState.from_json(json_str)

        assert restored.pot == 10.5
        assert restored.board_cards == ["As", "Kh", "Qd"]

    def test_get_hero_stack_bb(self) -> None:
        """测试获取 Hero 筹码（BB 单位）。"""
        state = create_observed_state(big_blind=1.0)
        state.hero_seat = 0
        state.players = [
            Player(seat_index=0, stack=100.0),
            Player(seat_index=1, stack=50.0),
        ]

        assert state.get_hero_stack_bb() == 100.0


class TestPlayer:
    """Player 测试。"""

    def test_to_dict_from_dict(self) -> None:
        """测试 Player 序列化往返。"""
        player = Player(
            seat_index=0,
            player_id="player1",
            stack=100.0,
            bet=5.0,
            position=DomainPosition.BTN,
            is_folded=False,
            is_thinking=True,
            is_button=True,
            vpip=25,
        )

        data = player.to_dict()
        assert data["seat_index"] == 0
        assert data["player_id"] == "player1"
        assert data["stack"] == 100.0
        assert data["position"] == "BTN"

        restored = Player.from_dict(data)
        assert restored.seat_index == 0
        assert restored.player_id == "player1"
        assert restored.stack == 100.0
        assert restored.position == DomainPosition.BTN
        assert restored.is_button is True

    def test_player_action_history(self) -> None:
        """测试玩家级别行动历史记录。"""
        player = Player(seat_index=0, player_id="hero")

        action = PlayerAction(
            player_index=0,
            action_type=ActionType.RAISE,
            amount=3.0,
            street=Street.PREFLOP,
        )
        player.record_action(action)

        assert len(player.action_history) == 1
        assert player.action_history[0].action_type == ActionType.RAISE
        assert player.action_history[0].amount == 3.0

    def test_get_stack_bb(self) -> None:
        """测试获取 BB 单位筹码量。"""
        player = Player(seat_index=0, stack=100.0)

        assert player.get_stack_bb(1.0) == 100.0
        assert player.get_stack_bb(2.0) == 50.0
        assert player.get_stack_bb(0.0) == 100.0  # 边界情况

    def test_action_history_serialization(self) -> None:
        """测试行动历史的序列化/反序列化。"""
        player = Player(seat_index=0, player_id="test")
        action = PlayerAction(
            player_index=0,
            action_type=ActionType.CALL,
            amount=1.0,
            street=Street.PREFLOP,
        )
        player.record_action(action)

        data = player.to_dict()
        restored = Player.from_dict(data)

        assert len(restored.action_history) == 1
        assert restored.action_history[0].action_type == ActionType.CALL

    def test_record_action_propagates_to_player(self) -> None:
        """测试 ObservedTableState.record_action 同时记录到玩家历史。"""
        state = create_observed_state()
        state.players = [
            Player(seat_index=0, player_id="p0"),
            Player(seat_index=1, player_id="p1"),
        ]

        state.record_action(0, ActionType.RAISE, 3.0)
        state.record_action(1, ActionType.CALL)

        # 全局历史
        assert len(state.action_history) == 2

        # 玩家级别历史
        assert len(state.players[0].action_history) == 1
        assert state.players[0].action_history[0].action_type == ActionType.RAISE
        assert len(state.players[1].action_history) == 1
        assert state.players[1].action_history[0].action_type == ActionType.CALL


class TestIntegration:
    """集成测试 - 需要截图文件。"""

    @pytest.fixture
    def sample_image_path(self) -> Path | None:
        candidates = [
            Path("/mnt/d/project/gg_bot/pic/single"),
            Path("D:/project/gg_bot/pic/single"),
        ]
        for path in candidates:
            if path.exists():
                images = list(path.glob("*.jpg"))
                if images:
                    return images[0]
        return None

    @pytest.mark.skipif(
        not any(
            Path(p).exists()
            for p in [
                "/mnt/d/project/gg_bot/pic/single",
                "D:/project/gg_bot/pic/single",
            ]
        ),
        reason="测试截图目录不存在",
    )
    def test_detector_with_real_image(self, sample_image_path: Path | None) -> None:
        if sample_image_path is None:
            pytest.skip("未找到测试截图")

        try:
            import cv2
        except ImportError:
            pytest.skip("需要安装 opencv-python")

        img = cv2.imread(str(sample_image_path))
        if img is None:
            pytest.skip(f"无法读取图像: {sample_image_path}")

        from bayes_poker.ocr.engine import CnOcrEngine
        from bayes_poker.table.detector import TableDetector

        layout = get_gg_6max_layout()
        h, w = img.shape[:2]
        scaled = ScaledLayout(layout=layout, actual_width=w, actual_height=h)

        try:
            ocr = CnOcrEngine()
            detector = TableDetector(scaled, ocr)

            phase = detector.detect_phase(img)
            assert phase is not None

            btn_seat = detector.detect_button_seat(img)

            is_hero_turn = detector.is_hero_turn(img)

        except ImportError:
            pytest.skip("需要安装 cnocr")
