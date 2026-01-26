"""pokerkit 状态桥接模块。

将牌桌解析结果同步到 pokerkit.State，实现实时游戏状态维护。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

LOGGER = logging.getLogger(__name__)


class ActionType(Enum):
    """玩家动作类型。"""

    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    BET = auto()
    RAISE = auto()
    ALL_IN = auto()


@dataclass
class PlayerAction:
    """玩家动作记录。"""

    player_index: int
    action_type: ActionType
    amount: float = 0.0


class Street(Enum):
    """游戏阶段。"""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


@dataclass
class PokerKitStateBridge:
    """pokerkit 状态桥接器。

    将解析到的玩家动作转换为 pokerkit.State 的方法调用，
    实时维护游戏状态。
    """

    player_count: int
    small_blind: float
    big_blind: float
    starting_stacks: list[float]
    ante: float = 0.0

    _state: object = field(default=None, repr=False)
    _action_history: list[PlayerAction] = field(default_factory=list, repr=False)
    _current_street: Street = field(default=Street.PREFLOP, repr=False)

    def create_new_hand(self, starting_stacks: list[float] | None = None) -> None:
        """创建新的一手牌。

        Args:
            starting_stacks: 各玩家起始筹码，None 则使用默认值
        """
        try:
            from pokerkit import Automation, NoLimitTexasHoldem
        except ImportError as e:
            raise ImportError("需要安装 pokerkit: uv add pokerkit") from e

        stacks = starting_stacks or self.starting_stacks

        if len(stacks) != self.player_count:
            raise ValueError(
                f"筹码数量 ({len(stacks)}) 与玩家数量 ({self.player_count}) 不匹配"
            )

        self._state = NoLimitTexasHoldem.create_state(
            automations=(
                Automation.ANTE_POSTING,
                Automation.BET_COLLECTION,
                Automation.BLIND_OR_STRADDLE_POSTING,
                Automation.HOLE_DEALING,
                Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
                Automation.HAND_KILLING,
                Automation.CHIPS_PUSHING,
                Automation.CHIPS_PULLING,
            ),
            ante_trimming_status=True,
            raw_antes={-1: self.ante} if self.ante > 0 else {},
            raw_blinds_or_straddles=(self.small_blind, self.big_blind),
            min_bet=self.big_blind,
            raw_starting_stacks=stacks,
            player_count=self.player_count,
        )

        self._action_history.clear()
        self._current_street = Street.PREFLOP
        LOGGER.debug(
            "创建新手牌: players=%d, blinds=%.2f/%.2f",
            self.player_count,
            self.small_blind,
            self.big_blind,
        )

    @property
    def state(self):
        """获取 pokerkit State 对象。"""
        if self._state is None:
            raise RuntimeError("尚未创建手牌，请先调用 create_new_hand()")
        return self._state

    @property
    def current_street(self) -> Street:
        """当前游戏阶段。"""
        return self._current_street

    @property
    def actor_index(self) -> int | None:
        """当前行动玩家索引。"""
        if self._state is None:
            return None
        return self.state.actor_index

    @property
    def stacks(self) -> list[float]:
        """各玩家当前筹码。"""
        if self._state is None:
            return []
        return list(self.state.stacks)

    @property
    def total_pot(self) -> float:
        """当前底池总额。"""
        if self._state is None:
            return 0.0
        return float(self.state.total_pot_amount)

    @property
    def is_hand_complete(self) -> bool:
        """手牌是否已结束。"""
        if self._state is None:
            return True
        return self.state.status is False

    def apply_action(self, action: PlayerAction) -> bool:
        """应用玩家动作。

        Args:
            action: 玩家动作

        Returns:
            True 如果动作成功应用
        """
        if self._state is None:
            LOGGER.warning("尝试应用动作但没有活跃的手牌")
            return False

        try:
            match action.action_type:
                case ActionType.FOLD:
                    self.state.fold()
                case ActionType.CHECK:
                    self.state.check_or_call()
                case ActionType.CALL:
                    self.state.check_or_call()
                case ActionType.BET:
                    self.state.complete_bet_or_raise_to(action.amount)
                case ActionType.RAISE:
                    self.state.complete_bet_or_raise_to(action.amount)
                case ActionType.ALL_IN:
                    max_bet = max(self.stacks[action.player_index], action.amount)
                    self.state.complete_bet_or_raise_to(max_bet)

            self._action_history.append(action)
            LOGGER.debug(
                "动作已应用: player=%d, type=%s, amount=%.2f",
                action.player_index,
                action.action_type.name,
                action.amount,
            )
            return True

        except Exception as e:
            LOGGER.warning(
                "应用动作失败: player=%d, type=%s, amount=%.2f, error=%s",
                action.player_index,
                action.action_type.name,
                action.amount,
                e,
            )
            return False

    def deal_hole_cards(self, player_index: int, cards: str) -> bool:
        """发底牌。

        Args:
            player_index: 玩家索引
            cards: 牌面字符串，如 "AcKd"

        Returns:
            True 如果成功
        """
        if self._state is None:
            return False

        try:
            self.state.deal_hole(cards)
            LOGGER.debug("发底牌: player=%d, cards=%s", player_index, cards)
            return True
        except Exception as e:
            LOGGER.warning("发底牌失败: %s", e)
            return False

    def deal_board(self, cards: str) -> bool:
        """发公共牌。

        Args:
            cards: 公共牌字符串，如 "2c7dJh"

        Returns:
            True 如果成功
        """
        if self._state is None:
            return False

        try:
            self.state.deal_board(cards)

            card_count = len(cards) // 2
            if card_count == 3:
                self._current_street = Street.FLOP
            elif card_count == 1 and self._current_street == Street.FLOP:
                self._current_street = Street.TURN
            elif card_count == 1 and self._current_street == Street.TURN:
                self._current_street = Street.RIVER

            LOGGER.debug(
                "发公共牌: cards=%s, street=%s", cards, self._current_street.value
            )
            return True
        except Exception as e:
            LOGGER.warning("发公共牌失败: %s", e)
            return False

    def enter_street(self, street: Street, board_cards: str | None = None) -> bool:
        """进入新的游戏阶段。

        Args:
            street: 目标阶段
            board_cards: 该阶段的公共牌

        Returns:
            True 如果成功
        """
        self._current_street = street

        if board_cards:
            return self.deal_board(board_cards)

        return True

    def get_action_history(self) -> list[PlayerAction]:
        """获取动作历史。"""
        return self._action_history.copy()

    def reset(self) -> None:
        """重置状态。"""
        self._state = None
        self._action_history.clear()
        self._current_street = Street.PREFLOP


def create_state_bridge(
    player_count: int = 6,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
    starting_stacks: list[float] | None = None,
    ante: float = 0.0,
) -> PokerKitStateBridge:
    """创建 pokerkit 状态桥接器。

    Args:
        player_count: 玩家数量
        small_blind: 小盲注
        big_blind: 大盲注
        starting_stacks: 起始筹码，None 则使用默认 100BB
        ante: 前注

    Returns:
        PokerKitStateBridge 实例
    """
    if starting_stacks is None:
        starting_stacks = [big_blind * 100] * player_count

    return PokerKitStateBridge(
        player_count=player_count,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_stacks=starting_stacks,
        ante=ante,
    )
