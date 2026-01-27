"""游戏阶段和动作检测器。

基于颜色特征和 OCR 识别，检测牌桌状态变化。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from bayes_poker.ocr.interface import OCREngine
from bayes_poker.ocr.schema import Area, Color, Point, CARD_SUIT_COLORS
from bayes_poker.table.layout.base import ScaledLayout

LOGGER = logging.getLogger(__name__)


class TablePhase(Enum):
    """牌桌阶段（与 Street 对应但用于解析层）。"""

    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()


@dataclass
class ParsedCard:
    """解析出的扑克牌。"""

    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def to_pokerkit_str(self) -> str:
        return f"{self.rank}{self.suit}"


@dataclass
class ParsedPlayerState:
    """解析出的玩家状态。"""

    seat_index: int
    player_id: str = ""
    chip_stack: float = 0.0
    bet_size: float = 0.0
    vpip: int = 0
    is_folded: bool = False
    is_thinking: bool = False
    is_button: bool = False


class TableDetector:
    """牌桌状态检测器。

    负责从截图中检测游戏阶段、玩家动作等状态。
    """

    def __init__(self, layout: ScaledLayout, ocr_engine: OCREngine) -> None:
        self._layout = layout
        self._ocr = ocr_engine

    def detect_phase(self, img: np.ndarray) -> TablePhase:
        """检测当前游戏阶段。"""
        has_flop = self._detect_flop(img)
        has_turn = self._detect_turn(img)
        has_river = self._detect_river(img)

        if has_flop and has_turn and has_river:
            return TablePhase.RIVER
        if has_flop and has_turn:
            return TablePhase.TURN
        if has_flop:
            return TablePhase.FLOP
        return TablePhase.PREFLOP

    def _detect_flop(self, img: np.ndarray) -> bool:
        """检测是否有翻牌。"""
        points = self._layout.get_flop_detect_points()
        color_config = self._layout.get_flop_detect_color()

        count = 0
        for point in points:
            if color_config.color.point_like(img, point, color_config.tolerance):
                count += 1

        return count >= 3

    def _detect_turn(self, img: np.ndarray) -> bool:
        """检测是否有转牌。"""
        point = self._layout.get_turn_detect_point()
        table_config = self._layout.layout.get_table_config()
        color_config = table_config.turn_detect_color

        return color_config.color.point_like(img, point, color_config.tolerance)

    def _detect_river(self, img: np.ndarray) -> bool:
        """检测是否有河牌。"""
        point = self._layout.get_river_detect_point()
        table_config = self._layout.layout.get_table_config()
        color_config = table_config.river_detect_color

        return color_config.color.point_like(img, point, color_config.tolerance)

    def detect_button_seat(self, img: np.ndarray) -> int:
        """检测庄家座位索引。"""
        player_count = self._layout.layout.player_count

        for i in range(player_count):
            area, color, tolerance, threshold = self._layout.get_player_btn_icon_check(
                i
            )
            cropped = area.crop(img)
            if color.area_like(cropped, tolerance, threshold):
                return i

        return -1

    def detect_thinking_seat(self, img: np.ndarray) -> int:
        """检测当前思考中的座位索引。"""
        player_count = self._layout.layout.player_count

        for i in range(player_count):
            point, color, tolerance = self._layout.get_player_thinking_bar_check(i)
            if color.point_like(img, point, tolerance):
                return i

        return -1

    def detect_player_folded(self, img: np.ndarray, seat_index: int) -> bool:
        """检测玩家是否已弃牌。"""
        points, color, tolerance = self._layout.get_player_fold_check(seat_index)

        for point in points:
            if not color.point_like(img, point, tolerance):
                return True

        return False

    def detect_player_has_bet(self, img: np.ndarray, seat_index: int) -> bool:
        """检测玩家是否有下注筹码。"""
        area, color, tolerance, threshold = self._layout.get_player_bet_icon_check(
            seat_index
        )
        cropped = area.crop(img)
        return color.area_like(cropped, tolerance, threshold)

    def parse_player_bet_size(self, img: np.ndarray, seat_index: int) -> float:
        """解析玩家下注金额。"""
        if not self.detect_player_has_bet(img, seat_index):
            return 0.0

        area = self._layout.get_player_bet_size_ocr_area(seat_index)
        cropped = area.crop(img)
        return self._ocr.recognize_number(cropped)

    def parse_player_chip_stack(self, img: np.ndarray, seat_index: int) -> float:
        """解析玩家筹码量。"""
        area = self._layout.get_player_chip_ocr_area(seat_index)
        cropped = area.crop(img)
        return self._ocr.recognize_number(cropped)

    def parse_player_id(self, img: np.ndarray, seat_index: int) -> str:
        """解析玩家 ID。"""
        area = self._layout.get_player_id_ocr_area(seat_index)
        cropped = area.crop(img)
        return self._ocr.recognize_text(cropped)

    def parse_player_vpip(self, img: np.ndarray, seat_index: int) -> int:
        """解析玩家 VPIP。"""
        area = self._layout.get_player_vpip_ocr_area(seat_index)
        cropped = area.crop(img)
        value = self._ocr.recognize_number(cropped)
        return int(value)

    def parse_hero_cards(self, img: np.ndarray) -> tuple[ParsedCard, ParsedCard] | None:
        """解析 Hero 底牌。"""
        left_area, right_area = self._layout.get_hero_card_rank_ocr_areas()
        left_color_point, right_color_point = self._layout.get_hero_card_color_points()

        left_rank = self._ocr.recognize_card_rank(left_area.crop(img))
        right_rank = self._ocr.recognize_card_rank(right_area.crop(img))

        if not left_rank or not right_rank:
            return None

        left_suit = self._detect_card_suit(img, left_color_point)
        right_suit = self._detect_card_suit(img, right_color_point)

        if not left_suit or not right_suit:
            return None

        return (
            ParsedCard(left_rank, left_suit),
            ParsedCard(right_rank, right_suit),
        )

    def parse_board_card(self, img: np.ndarray, index: int) -> ParsedCard | None:
        """解析公共牌。"""
        if index < 0 or index > 4:
            return None

        color_point = self._layout.get_board_color_point(index)
        rank_area = self._layout.get_board_rank_ocr_area(index)

        rank = self._ocr.recognize_card_rank(rank_area.crop(img))
        if not rank:
            return None

        suit = self._detect_card_suit(img, color_point)
        if not suit:
            return None

        return ParsedCard(rank, suit)

    def parse_board(self, img: np.ndarray, phase: TablePhase) -> list[ParsedCard]:
        """解析所有公共牌。"""
        card_count = {
            TablePhase.PREFLOP: 0,
            TablePhase.FLOP: 3,
            TablePhase.TURN: 4,
            TablePhase.RIVER: 5,
        }[phase]

        cards = []
        for i in range(card_count):
            card = self.parse_board_card(img, i)
            if card:
                cards.append(card)

        return cards

    def _detect_card_suit(self, img: np.ndarray, point: Point) -> str:
        """检测扑克牌花色。"""
        for suit, color in CARD_SUIT_COLORS.items():
            if color.point_like(img, point, 40):
                return suit
        return ""

    def parse_pot_size(self, img: np.ndarray) -> tuple[float, float]:
        """解析底池大小。

        Returns:
            (原始底池, 当前底池)
        """
        ori_area = self._layout.get_ori_pot_size_ocr_area()
        cur_area = self._layout.get_cur_pot_size_ocr_area()

        ori_pot = self._ocr.recognize_number(ori_area.crop(img))
        cur_pot = self._ocr.recognize_number(cur_area.crop(img))

        return ori_pot, cur_pot

    def detect_hero_decision_buttons(self, img: np.ndarray) -> tuple[bool, bool, bool]:
        """检测 Hero 操作按钮是否可用。

        Returns:
            (fold_available, call_available, raise_available)
        """
        fold_check = self._layout.get_btn_fold_check()
        call_check = self._layout.get_btn_call_check()
        raise_check = self._layout.get_btn_raise_check()

        def check_button(check_tuple) -> bool:
            area, color, tolerance, threshold = check_tuple
            cropped = area.crop(img)
            return color.area_like(cropped, tolerance, threshold)

        return (
            check_button(fold_check),
            check_button(call_check),
            check_button(raise_check),
        )

    def is_hero_turn(self, img: np.ndarray) -> bool:
        """检测是否轮到 Hero 行动。"""
        fold_btn, call_btn, _ = self.detect_hero_decision_buttons(img)
        return fold_btn and call_btn

    def parse_all_player_states(self, img: np.ndarray) -> list[ParsedPlayerState]:
        """解析所有玩家状态。"""
        player_count = self._layout.layout.player_count
        btn_seat = self.detect_button_seat(img)
        thinking_seat = self.detect_thinking_seat(img)

        states = []
        for i in range(player_count):
            state = ParsedPlayerState(
                seat_index=i,
                player_id=self.parse_player_id(img, i),
                chip_stack=self.parse_player_chip_stack(img, i),
                bet_size=self.parse_player_bet_size(img, i),
                vpip=self.parse_player_vpip(img, i),
                is_folded=self.detect_player_folded(img, i),
                is_thinking=(i == thinking_seat),
                is_button=(i == btn_seat),
            )
            states.append(state)

        return states
