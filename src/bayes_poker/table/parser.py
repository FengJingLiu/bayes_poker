"""牌桌解析器。

基于多进程的实时牌桌状态解析器。
"""

from __future__ import annotations

import logging
import multiprocessing
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from bayes_poker.ocr.engine import get_ocr_engine
from bayes_poker.ocr.schema import Area
from bayes_poker.screen.capture import ScreenCapture, get_screen_capture
from bayes_poker.table.detector import (
    ParsedCard,
    ParsedPlayerState,
    TableDetector,
    TablePhase,
)
from bayes_poker.table.layout.base import ScaledLayout
from bayes_poker.table.layout.gg_6max import get_gg_6max_layout
from bayes_poker.table.state_bridge import (
    ActionType,
    PlayerAction,
    PokerKitStateBridge,
    Street,
    create_state_bridge,
)

if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock

LOGGER = logging.getLogger(__name__)


class ParserState(Enum):
    """解析器状态。"""

    IDLE = auto()
    WAITING_NEW_HAND = auto()
    PARSING = auto()
    STOPPED = auto()


@dataclass
class TableContext:
    """牌桌上下文。"""

    hwnd: int
    window_index: int
    capture_area: Area | None = None

    width: int = 0
    height: int = 0

    phase: TablePhase = TablePhase.PREFLOP
    btn_seat: int = -1
    thinking_seat: int = -1

    hero_cards: tuple[ParsedCard, ParsedCard] | None = None
    board_cards: list[ParsedCard] = field(default_factory=list)

    player_states: list[ParsedPlayerState] = field(default_factory=list)
    last_action_seat: int = -1

    state_bridge: PokerKitStateBridge | None = None


class TableParser(multiprocessing.Process):
    """牌桌解析器进程。

    每个窗口一个进程，独立解析牌桌状态。
    """

    def __init__(
        self,
        hwnd: int,
        window_index: int,
        capture_area: Area | None = None,
        small_blind: float = 0.5,
        big_blind: float = 1.0,
        stop_event: multiprocessing.Event | None = None,
        lock: Lock | None = None,
        poll_interval: float = 0.1,
    ) -> None:
        super().__init__(daemon=True)

        self._hwnd = hwnd
        self._window_index = window_index
        self._capture_area = capture_area
        self._small_blind = small_blind
        self._big_blind = big_blind
        self._stop_event = stop_event or multiprocessing.Event()
        self._lock = lock
        self._poll_interval = poll_interval

        self._state = ParserState.IDLE
        self._context: TableContext | None = None
        self._capture: ScreenCapture | None = None
        self._detector: TableDetector | None = None
        self._scaled_layout: ScaledLayout | None = None

        self._prev_phase: TablePhase = TablePhase.PREFLOP
        self._prev_btn_seat: int = -1
        self._prev_player_bets: list[float] = []
        self._prev_player_folded: list[bool] = []

    def run(self) -> None:
        """进程主循环。"""
        LOGGER.info(
            "TableParser 启动: hwnd=%d, index=%d", self._hwnd, self._window_index
        )

        self._initialize()

        while not self._stop_event.is_set():
            try:
                self._parse_loop()
            except Exception as e:
                LOGGER.exception("解析循环异常: %s", e)
                time.sleep(1.0)

        self._state = ParserState.STOPPED
        LOGGER.info("TableParser 停止: hwnd=%d", self._hwnd)

    def stop(self) -> None:
        """停止解析器。"""
        self._stop_event.set()

    def _initialize(self) -> None:
        """初始化解析器组件。"""
        self._capture = get_screen_capture()
        ocr_engine = get_ocr_engine()

        layout = get_gg_6max_layout()

        if self._capture_area is not None:
            width = self._capture_area.width
            height = self._capture_area.height
            if width <= 0 or height <= 0:
                LOGGER.error(
                    "无效截图区域: hwnd=%d, area=%s", self._hwnd, self._capture_area
                )
                return
        else:
            rect = self._capture.get_window_rect(self._hwnd)
            if rect is None:
                LOGGER.error("无法获取窗口尺寸: hwnd=%d", self._hwnd)
                return

            _, _, width, height = rect

        self._scaled_layout = ScaledLayout(
            layout=layout,
            actual_width=width,
            actual_height=height,
        )

        self._detector = TableDetector(self._scaled_layout, ocr_engine)

        self._context = TableContext(
            hwnd=self._hwnd,
            window_index=self._window_index,
            capture_area=self._capture_area,
            width=width,
            height=height,
        )

        self._state = ParserState.WAITING_NEW_HAND

    def _parse_loop(self) -> None:
        """单次解析循环。"""
        if self._capture is None or self._detector is None or self._context is None:
            time.sleep(self._poll_interval)
            return

        if self._capture_area is not None:
            img = self._capture.capture_region(
                hwnd=0,
                x=self._capture_area.x1,
                y=self._capture_area.y1,
                width=self._capture_area.width,
                height=self._capture_area.height,
            )
        else:
            img = self._capture.capture_window(self._hwnd)
        if img is None:
            time.sleep(self._poll_interval)
            return

        if self._lock:
            with self._lock:
                self._parse_frame(img)
        else:
            self._parse_frame(img)

        time.sleep(self._poll_interval)

    def _parse_frame(self, img: np.ndarray) -> None:
        """解析单帧。"""
        if self._detector is None or self._context is None:
            return

        phase = self._detector.detect_phase(img)
        btn_seat = self._detector.detect_button_seat(img)
        thinking_seat = self._detector.detect_thinking_seat(img)

        if self._is_new_hand(phase, btn_seat):
            self._start_new_hand(img, phase, btn_seat)

        self._context.phase = phase
        self._context.btn_seat = btn_seat
        self._context.thinking_seat = thinking_seat

        if self._state == ParserState.PARSING:
            self._detect_phase_changes(img, phase)

            if phase == TablePhase.PREFLOP and self._context.hero_cards is None:
                self._context.hero_cards = self._detector.parse_hero_cards(img)
                if self._context.hero_cards:
                    cards_str = "".join(
                        c.to_pokerkit_str() for c in self._context.hero_cards
                    )
                    LOGGER.info("Hero 底牌: %s", cards_str)

            self._context.player_states = self._detector.parse_all_player_states(img)

            self._detect_actions(img)

        self._prev_phase = phase
        self._prev_btn_seat = btn_seat

    def _is_new_hand(self, phase: TablePhase, btn_seat: int) -> bool:
        """判断是否为新一手牌。"""
        if self._state == ParserState.WAITING_NEW_HAND:
            if phase == TablePhase.PREFLOP and btn_seat >= 0:
                return True

        if (
            btn_seat >= 0
            and btn_seat != self._prev_btn_seat
            and self._prev_btn_seat >= 0
        ):
            if phase == TablePhase.PREFLOP:
                return True

        return False

    def _start_new_hand(
        self, img: np.ndarray, phase: TablePhase, btn_seat: int
    ) -> None:
        """开始新一手牌。"""
        if self._detector is None or self._context is None:
            return

        LOGGER.info("新手牌开始: btn_seat=%d", btn_seat)

        player_states = self._detector.parse_all_player_states(img)
        stacks = [p.chip_stack for p in player_states]

        if all(s == 0 for s in stacks):
            stacks = [self._big_blind * 100] * 6

        self._context.state_bridge = create_state_bridge(
            player_count=6,
            small_blind=self._small_blind,
            big_blind=self._big_blind,
            starting_stacks=stacks,
        )
        self._context.state_bridge.create_new_hand(stacks)

        self._context.phase = phase
        self._context.btn_seat = btn_seat
        self._context.hero_cards = None
        self._context.board_cards = []
        self._context.player_states = player_states
        self._context.last_action_seat = -1

        self._prev_player_bets = [0.0] * 6
        self._prev_player_folded = [p.is_folded for p in player_states]
        self._state = ParserState.PARSING

    def _detect_phase_changes(self, img: np.ndarray, new_phase: TablePhase) -> None:
        """检测阶段变化并更新公共牌。"""
        if self._detector is None or self._context is None:
            return

        if new_phase == self._prev_phase:
            return

        LOGGER.info("阶段变化: %s -> %s", self._prev_phase.name, new_phase.name)

        new_cards = self._detector.parse_board(img, new_phase)
        new_cards_str = "".join(c.to_pokerkit_str() for c in new_cards)

        existing_count = len(self._context.board_cards)
        if len(new_cards) > existing_count:
            added_cards = new_cards[existing_count:]
            added_str = "".join(c.to_pokerkit_str() for c in added_cards)

            if self._context.state_bridge:
                self._context.state_bridge.deal_board(added_str)

            self._context.board_cards = new_cards
            LOGGER.info("公共牌: %s (新增: %s)", new_cards_str, added_str)

        self._prev_player_bets = [0.0] * 6

    def _detect_actions(self, img: np.ndarray) -> None:
        """检测玩家动作。"""
        if self._detector is None or self._context is None:
            return

        if not self._prev_player_folded:
            self._prev_player_folded = [False] * len(self._context.player_states)

        current_bets = [p.bet_size for p in self._context.player_states]
        current_folded = [p.is_folded for p in self._context.player_states]

        for i, (prev_bet, curr_bet) in enumerate(
            zip(self._prev_player_bets, current_bets, strict=False)
        ):
            player_state = self._context.player_states[i]

            if player_state.is_folded and not self._was_folded(i):
                self._record_action(i, ActionType.FOLD)
            elif curr_bet > prev_bet:
                if prev_bet == 0 and self._is_first_bet_in_round():
                    action_type = ActionType.BET
                else:
                    action_type = ActionType.RAISE
                self._record_action(i, action_type, curr_bet)

        self._prev_player_bets = current_bets
        self._prev_player_folded = current_folded

    def _was_folded(self, seat_index: int) -> bool:
        """检查玩家之前是否已弃牌。"""
        if 0 <= seat_index < len(self._prev_player_folded):
            return self._prev_player_folded[seat_index]
        return False

    def _is_first_bet_in_round(self) -> bool:
        """检查是否为本轮第一次下注。"""
        return all(b == 0 for b in self._prev_player_bets)

    def _record_action(
        self, seat_index: int, action_type: ActionType, amount: float = 0.0
    ) -> None:
        """记录玩家动作。"""
        if self._context is None:
            return

        action = PlayerAction(
            player_index=seat_index,
            action_type=action_type,
            amount=amount,
        )

        if self._context.state_bridge:
            self._context.state_bridge.apply_action(action)

        self._context.last_action_seat = seat_index
        LOGGER.debug(
            "动作记录: seat=%d, type=%s, amount=%.2f",
            seat_index,
            action_type.name,
            amount,
        )

    @property
    def context(self) -> TableContext | None:
        """获取当前牌桌上下文。"""
        return self._context

    @property
    def parser_state(self) -> ParserState:
        """获取解析器状态。"""
        return self._state
