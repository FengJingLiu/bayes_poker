"""对手范围预测器。

根据对手的行动历史、位置信息和统计数据预测其手牌范围。

预测算法概述：
- Preflop：基于对手位置和行动类型，使用策略表或统计数据收窄范围
- Postflop：将 preflop 范围展开为 1326 维，排除公共牌阻挡，根据行动收窄
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    RANGE_1326_LENGTH,
    PreflopRange,
    PostflopRange,
    card_to_index52,
)

if TYPE_CHECKING:
    from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
    from bayes_poker.strategy.preflop_parse.models import PreflopStrategy
    from bayes_poker.table.observed_state import (
        Player,
        ObservedTableState,
        PlayerAction,
    )


LOGGER = logging.getLogger(__name__)


# 基于行动类型的范围缩放因子
_ACTION_SCALE_FACTORS = {
    ActionType.FOLD: 0.0,
    ActionType.CHECK: 0.7,
    ActionType.CALL: 0.6,
    ActionType.BET: 0.5,
    ActionType.RAISE: 0.4,
    ActionType.ALL_IN: 0.3,
}


@dataclass
class OpponentRangePredictor:
    """对手范围预测器。

    根据对手行动更新其手牌范围估计。范围数据由预测器内部维护，通过 seat_index 索引。

    Attributes:
        preflop_strategy: 翻前策略数据。
        stats_repo: 玩家统计仓库。
        table_type: 牌桌类型。
        _preflop_ranges: 内部翻前范围映射（seat_index → PreflopRange）。
        _postflop_ranges: 内部翻后范围映射（seat_index → PostflopRange）。
    """

    preflop_strategy: "PreflopStrategy | None" = None
    stats_repo: "PlayerStatsRepository | None" = None
    table_type: TableType = TableType.SIX_MAX
    _preflop_ranges: dict[int, PreflopRange] = field(default_factory=dict)
    _postflop_ranges: dict[int, PostflopRange] = field(default_factory=dict)

    def get_preflop_range(self, seat_index: int) -> PreflopRange | None:
        """获取指定座位的翻前范围。"""
        return self._preflop_ranges.get(seat_index)

    def get_postflop_range(self, seat_index: int) -> PostflopRange | None:
        """获取指定座位的翻后范围。"""
        return self._postflop_ranges.get(seat_index)

    def update_range_on_action(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """根据对手行动更新其范围。"""
        if action.street == Street.PREFLOP:
            self._update_preflop_range(player, action, table_state)
        else:
            self._update_postflop_range(player, action, table_state)

    def _update_preflop_range(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """更新翻前范围。"""
        seat = player.seat_index

        if seat not in self._preflop_ranges:
            self._preflop_ranges[seat] = self._get_initial_preflop_range(
                player, table_state
            )

        if action.action_type == ActionType.FOLD:
            self._preflop_ranges[seat] = PreflopRange.zeros()
            self._postflop_ranges[seat] = PostflopRange.zeros()
            return

        scale = self._get_preflop_action_scale(player, action, table_state)
        current_range = self._preflop_ranges[seat]
        for i in range(RANGE_169_LENGTH):
            current_range.strategy[i] *= scale
        current_range.normalize()

        LOGGER.debug(
            "更新玩家 %s 翻前范围: action=%s, scale=%.2f",
            player.player_id,
            action.action_type.value,
            scale,
        )

    def _update_postflop_range(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """更新翻后范围。"""
        seat = player.seat_index

        if seat not in self._preflop_ranges:
            self._preflop_ranges[seat] = self._get_initial_preflop_range(
                player, table_state
            )

        if seat not in self._postflop_ranges:
            self._postflop_ranges[seat] = self._preflop_ranges[seat].to_postflop()
            self._apply_board_blockers(
                self._postflop_ranges[seat], table_state.board_cards
            )

        if action.action_type == ActionType.FOLD:
            self._postflop_ranges[seat] = PostflopRange.zeros()
            return

        scale = self._get_postflop_action_scale(player, action, table_state)
        current_range = self._postflop_ranges[seat]
        for i in range(RANGE_1326_LENGTH):
            current_range.strategy[i] *= scale
        current_range.normalize()

        LOGGER.debug(
            "更新玩家 %s 翻后范围: street=%s, action=%s, scale=%.2f",
            player.player_id,
            action.street.value,
            action.action_type.value,
            scale,
        )

    def _get_initial_preflop_range(
        self,
        player: "Player",
        table_state: "ObservedTableState",
    ) -> PreflopRange:
        """获取初始翻前范围。"""
        if self.stats_repo and player.player_id:
            stats = self.stats_repo.get(player.player_id, self.table_type)
            if stats and stats.preflop_stats:
                initial_range = self._range_from_vpip(stats.vpip)
                if initial_range is not None:
                    return initial_range
        return self._get_position_default_range(player.position)

    def _range_from_vpip(self, vpip: float) -> PreflopRange | None:
        """根据 VPIP 生成初始范围。"""
        if vpip <= 0:
            return None
        frequency = min(1.0, vpip / 100.0)
        strategy = [frequency] * RANGE_169_LENGTH
        return PreflopRange(strategy=strategy)

    def _get_position_default_range(self, position: str) -> PreflopRange:
        """根据位置获取默认范围。"""
        position_vpip = {
            "UTG": 0.15,
            "MP": 0.18,
            "CO": 0.25,
            "BTN": 0.40,
            "SB": 0.35,
            "BB": 0.50,
        }
        frequency = position_vpip.get(position.upper(), 0.25)
        strategy = [frequency] * RANGE_169_LENGTH
        return PreflopRange(strategy=strategy)

    def _get_preflop_action_scale(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> float:
        """获取翻前行动的范围缩放因子。"""
        base_scale = _ACTION_SCALE_FACTORS.get(action.action_type, 0.5)

        if self.stats_repo and player.player_id:
            stats = self.stats_repo.get(player.player_id, self.table_type)
            if stats and stats.preflop_stats:
                if action.action_type in (ActionType.RAISE, ActionType.BET):
                    pfr = getattr(stats, "pfr", 0.0)
                    if pfr > 0:
                        base_scale = min(1.0, base_scale * (1 + pfr / 100))

        return base_scale

    def _get_postflop_action_scale(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> float:
        """获取翻后行动的范围缩放因子。"""
        base_scale = _ACTION_SCALE_FACTORS.get(action.action_type, 0.5)

        street_multiplier = {
            Street.FLOP: 1.0,
            Street.TURN: 0.9,
            Street.RIVER: 0.8,
        }
        multiplier = street_multiplier.get(action.street, 1.0)

        if action.amount > 0 and table_state.pot > 0:
            bet_ratio = action.amount / table_state.pot
            if bet_ratio > 1.0:
                base_scale *= 0.7
            elif bet_ratio > 0.66:
                base_scale *= 0.85

        return base_scale * multiplier

    def _apply_board_blockers(
        self,
        postflop_range: PostflopRange,
        board_cards: list[str],
    ) -> None:
        """移除被公共牌阻挡的组合。"""
        if not board_cards:
            return

        blocked_indices: list[int] = []
        for card in board_cards:
            if len(card) >= 2:
                try:
                    rank = card[0].upper()
                    suit = card[1].lower()
                    idx = card_to_index52(rank, suit)
                    blocked_indices.append(idx)
                except (KeyError, IndexError):
                    LOGGER.warning("无法解析公共牌: %s", card)

        if blocked_indices:
            postflop_range.ban_cards(blocked_indices)

    def reset_player_ranges(self, player: "Player") -> None:
        """重置玩家范围（新手牌开始时调用）。"""
        seat = player.seat_index
        self._preflop_ranges.pop(seat, None)
        self._postflop_ranges.pop(seat, None)

    def reset_all_ranges(self) -> None:
        """重置所有玩家范围（新手牌开始时调用）。"""
        self._preflop_ranges.clear()
        self._postflop_ranges.clear()


def create_opponent_range_predictor(
    preflop_strategy: "PreflopStrategy | None" = None,
    stats_repo: "PlayerStatsRepository | None" = None,
    table_type: TableType = TableType.SIX_MAX,
) -> OpponentRangePredictor:
    """创建对手范围预测器。"""
    return OpponentRangePredictor(
        preflop_strategy=preflop_strategy,
        stats_repo=stats_repo,
        table_type=table_type,
    )
