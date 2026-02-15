"""对手范围预测器。

根据对手的行动历史、位置信息和统计数据预测其手牌范围。

流程说明文档位置(更新当前文件需要同步更新说明文文档):
- src/bayes_poker/strategy/opponent_range/predictor_flow.md

预测算法概述:
- Preflop:基于对手位置和行动类型，使用策略表或统计数据收窄范围
- Postflop:将 preflop 范围展开为 1326 维，排除公共牌阻挡，根据行动收窄
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from bayes_poker.comm.strategy_history import build_preflop_history
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.opponent_range.frequency_fill import build_limp_calling_range
from bayes_poker.strategy.opponent_range.preflop_context import (
    build_opponent_preflop_context,
)
from bayes_poker.strategy.opponent_range.stats_source import get_aggregated_player_stats
from bayes_poker.strategy.range import (
    RANGE_169_ORDER,
    RANGE_169_LENGTH,
    RANGE_1326_LENGTH,
    PreflopRange,
    PostflopRange,
    card_to_index52,
    combos_per_hand,
)
from bayes_poker.strategy.runtime.preflop_history import PreflopScenario
from bayes_poker.table.layout.base import Position as TablePosition

if TYPE_CHECKING:
    from bayes_poker.player_metrics.models import PlayerStats
    from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
    from bayes_poker.strategy.preflop_parse.models import (
        PreflopStrategy,
        StrategyAction,
        StrategyNode,
    )
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


class FirstPreflopScenario(str, Enum):
    """首次翻前行动场景枚举。"""

    FIRST_LIMP = "first_limp"
    FOLLOW_LIMP = "follow_limp"
    RFI_NO_LIMPER = "rfi_no_limper"
    RFI_HAVE_LIMPER = "rfi_have_limper"
    THREE_BET = "three_bet"
    FOUR_BET = "four_bet"
    UNKNOWN = "unknown"


def _coerce_table_position(value: object) -> TablePosition | None:
    """将输入值转换为位置枚举。

    Args:
        value: 输入位置值, 支持枚举或字符串。

    Returns:
        位置枚举, 失败时返回 `None`。
    """
    if isinstance(value, TablePosition):
        return value
    if isinstance(value, str):
        try:
            return TablePosition(value.upper())
        except ValueError:
            return None
    return None


def _clamp_probability(value: float) -> float:
    """限制概率到 [0.0, 1.0] 区间。

    Args:
        value: 输入概率值。

    Returns:
        限制后的概率值。
    """
    return max(0.0, min(1.0, float(value)))


@dataclass
class OpponentRangePredictor:
    """对手范围预测器。

    根据对手行动更新其手牌范围估计。范围数据由预测器内部维护，通过 seat_index 索引。

    Attributes:
        preflop_strategy: 翻前策略数据。
        stats_repo: 玩家统计仓库。
        table_type: 牌桌类型。
        _preflop_ranges: 内部翻前范围映射(seat_index → PreflopRange)。
        _postflop_ranges: 内部翻后范围映射(seat_index → PostflopRange)。
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
        action_prefix: Sequence["PlayerAction"] | None = None,
    ) -> None:
        """根据对手行动更新其范围。

        Args:
            player: 触发动作的玩家。
            action: 当前动作。
            table_state: 当前牌桌状态。
            action_prefix: 当前动作前的全量动作前缀。
        """
        if action.street == Street.PREFLOP:
            self._update_preflop_range(
                player,
                action,
                table_state,
                action_prefix=action_prefix,
            )
        else:
            self._update_postflop_range(player, action, table_state)

    def _update_preflop_range(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        action_prefix: Sequence["PlayerAction"] | None = None,
    ) -> None:
        """更新翻前范围。

        Args:
            player: 触发动作的玩家。
            action: 当前动作。
            table_state: 当前牌桌状态。
            action_prefix: 当前动作前的全量动作前缀。
        """
        seat = player.seat_index

        if action.action_type == ActionType.FOLD:
            self._preflop_ranges[seat] = PreflopRange.zeros()
            self._postflop_ranges[seat] = PostflopRange.zeros()
            return
        preflop_prefix = tuple(
            each for each in tuple(action_prefix or ()) if each.street == Street.PREFLOP
        )
        previous_prefix = self._strip_current_action_suffix(
            preflop_prefix=preflop_prefix,
            action=action,
        )
        current_prefix = self._build_preflop_prefix_with_current(
            preflop_prefix=previous_prefix,
            action=action,
        )
        if self._is_player_first_preflop_action(player=player, preflop_prefix=previous_prefix):
            self._handle_preflop_first_action(
                player=player,
                action=action,
                table_state=table_state,
                preflop_prefix=previous_prefix,
                current_prefix=current_prefix,
            )
            return
        self._handle_preflop_non_first_action(
            player=player,
            action=action,
            table_state=table_state,
            preflop_prefix=previous_prefix,
            current_prefix=current_prefix,
        )

    def _update_postflop_range(
        self,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """更新翻后范围。

        Args:
            player: 触发动作的玩家。
            action: 当前动作。
            table_state: 当前牌桌状态。
        """
        LOGGER.debug(
            "postflop 预测暂未实现: player=%s, action=%s, street=%s",
            player.player_id,
            action.action_type.value,
            action.street.value,
        )

    def _build_preflop_prefix_with_current(
        self,
        *,
        preflop_prefix: Sequence["PlayerAction"],
        action: "PlayerAction",
    ) -> tuple["PlayerAction", ...]:
        """构建包含当前动作的翻前前缀。

        Args:
            preflop_prefix: 当前动作前的翻前前缀。
            action: 当前动作。

        Returns:
            包含当前动作的翻前前缀。
        """
        raw_prefix = tuple(preflop_prefix)
        if (
            raw_prefix
            and raw_prefix[-1].player_index == action.player_index
            and raw_prefix[-1].street == action.street
            and raw_prefix[-1].action_type == action.action_type
            and abs(raw_prefix[-1].amount - action.amount) < 1e-9
        ):
            return raw_prefix
        return (*raw_prefix, action)

    def _strip_current_action_suffix(
        self,
        *,
        preflop_prefix: Sequence["PlayerAction"],
        action: "PlayerAction",
    ) -> tuple["PlayerAction", ...]:
        """去除前缀末尾可能重复的当前动作。"""
        raw_prefix = tuple(preflop_prefix)
        if (
            raw_prefix
            and raw_prefix[-1].player_index == action.player_index
            and raw_prefix[-1].street == action.street
            and raw_prefix[-1].action_type == action.action_type
            and abs(raw_prefix[-1].amount - action.amount) < 1e-9
        ):
            return raw_prefix[:-1]
        return raw_prefix

    def _is_player_first_preflop_action(
        self,
        *,
        player: "Player",
        preflop_prefix: Sequence["PlayerAction"],
    ) -> bool:
        """判断是否为玩家首次翻前行动。"""
        for each in preflop_prefix:
            if each.player_index == player.seat_index:
                return False
        return True

    def _is_raise_like_action(self, action: "PlayerAction") -> bool:
        """判断是否为加注类动作。"""
        return action.action_type in (
            ActionType.RAISE,
            ActionType.BET,
            ActionType.ALL_IN,
        )

    def _is_call_like_action(self, action: "PlayerAction") -> bool:
        """判断是否为跟注类动作。"""
        return action.action_type in (ActionType.CALL, ActionType.CHECK)

    def _classify_first_preflop_scenario(
        self,
        *,
        preflop_prefix: Sequence["PlayerAction"],
        action: "PlayerAction",
    ) -> FirstPreflopScenario:
        """分类首次翻前行动场景。"""
        raise_count = 0
        limp_count = 0
        for each in preflop_prefix:
            if self._is_raise_like_action(each):
                raise_count += 1
            elif self._is_call_like_action(each):
                limp_count += 1
        if self._is_call_like_action(action):
            if raise_count > 0:
                return FirstPreflopScenario.UNKNOWN
            if limp_count <= 0:
                return FirstPreflopScenario.FIRST_LIMP
            return FirstPreflopScenario.FOLLOW_LIMP
        if self._is_raise_like_action(action):
            if raise_count >= 2:
                return FirstPreflopScenario.FOUR_BET
            if raise_count == 1:
                return FirstPreflopScenario.THREE_BET
            if limp_count > 0:
                return FirstPreflopScenario.RFI_HAVE_LIMPER
            return FirstPreflopScenario.RFI_NO_LIMPER
        return FirstPreflopScenario.UNKNOWN

    def _ensure_preflop_range_initialized(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
    ) -> None:
        """确保玩家翻前范围已初始化。"""
        seat = player.seat_index
        if seat not in self._preflop_ranges:
            self._preflop_ranges[seat] = self._get_initial_preflop_range(player, table_state)

    def _apply_preflop_action_scale(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """应用翻前动作缩放。"""
        seat = player.seat_index
        self._ensure_preflop_range_initialized(player=player, table_state=table_state)
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

    def _handle_preflop_first_action(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        preflop_prefix: Sequence["PlayerAction"],
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理首次翻前行动。"""
        scenario = self._classify_first_preflop_scenario(
            preflop_prefix=preflop_prefix,
            action=action,
        )
        if scenario == FirstPreflopScenario.FIRST_LIMP:
            self._handle_first_limp(player=player, action=action, table_state=table_state)
            return
        if scenario == FirstPreflopScenario.FOLLOW_LIMP:
            self._handle_follow_limp(
                player=player,
                action=action,
                table_state=table_state,
                current_prefix=current_prefix,
            )
            return
        if scenario == FirstPreflopScenario.RFI_NO_LIMPER:
            self._handle_rfi_no_limper(
                player=player,
                action=action,
                table_state=table_state,
                decision_prefix=preflop_prefix,
                current_prefix=current_prefix,
            )
            return
        if scenario == FirstPreflopScenario.RFI_HAVE_LIMPER:
            self._handle_rfi_have_limper(
                player=player,
                action=action,
                table_state=table_state,
                decision_prefix=preflop_prefix,
                current_prefix=current_prefix,
            )
            return
        if scenario == FirstPreflopScenario.THREE_BET:
            self._handle_three_bet(player=player, action=action, table_state=table_state)
            return
        if scenario == FirstPreflopScenario.FOUR_BET:
            self._handle_four_bet(player=player, action=action, table_state=table_state)
            return
        self._apply_preflop_action_scale(
            player=player,
            action=action,
            table_state=table_state,
        )

    def _handle_preflop_non_first_action(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        preflop_prefix: Sequence["PlayerAction"],
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理非首次翻前行动。"""
        first_action = self._get_player_first_preflop_action(
            player=player,
            preflop_prefix=preflop_prefix,
        )
        if first_action is None:
            self._apply_preflop_action_scale(
                player=player,
                action=action,
                table_state=table_state,
            )
            return
        if self._is_call_like_action(first_action):
            self._handle_non_first_after_first_call(
                player=player,
                action=action,
                table_state=table_state,
                current_prefix=current_prefix,
            )
            return
        if self._is_raise_like_action(first_action):
            self._handle_non_first_after_first_raise(
                player=player,
                action=action,
                table_state=table_state,
                current_prefix=current_prefix,
            )
            return
        self._apply_preflop_action_scale(
            player=player,
            action=action,
            table_state=table_state,
        )

    def _get_player_first_preflop_action(
        self,
        *,
        player: "Player",
        preflop_prefix: Sequence["PlayerAction"],
    ) -> "PlayerAction | None":
        """获取玩家首次翻前动作。"""
        for each in preflop_prefix:
            if each.player_index == player.seat_index:
                return each
        return None

    def _handle_first_limp(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """处理 first limp 场景。"""
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_follow_limp(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理 follow limp 场景。"""
        prefixed_range = self._build_preflop_range_from_prefix(
            player=player,
            table_state=table_state,
            action_prefix=current_prefix,
        )
        if prefixed_range is not None:
            self._preflop_ranges[player.seat_index] = prefixed_range
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_rfi_no_limper(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        decision_prefix: Sequence["PlayerAction"],
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理无 limper 的 RFI 场景。"""
        prefixed_range = self._build_rfi_preflop_range_from_prefix(
            player=player,
            table_state=table_state,
            decision_prefix=decision_prefix,
            current_prefix=current_prefix,
        )
        if prefixed_range is not None:
            self._preflop_ranges[player.seat_index] = prefixed_range
            return
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_rfi_have_limper(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        decision_prefix: Sequence["PlayerAction"],
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理有 limper 的 RFI 场景。"""
        prefixed_range = self._build_rfi_preflop_range_from_prefix(
            player=player,
            table_state=table_state,
            decision_prefix=decision_prefix,
            current_prefix=current_prefix,
        )
        if prefixed_range is not None:
            self._preflop_ranges[player.seat_index] = prefixed_range
            return
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_three_bet(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """处理 3Bet 场景。"""
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_four_bet(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
    ) -> None:
        """处理 4Bet 场景。"""
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_non_first_after_first_call(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理首次行动为 call 的非首次翻前行动。"""
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _handle_non_first_after_first_raise(
        self,
        *,
        player: "Player",
        action: "PlayerAction",
        table_state: "ObservedTableState",
        current_prefix: Sequence["PlayerAction"],
    ) -> None:
        """处理首次行动为 raise 的非首次翻前行动。"""
        self._apply_preflop_action_scale(player=player, action=action, table_state=table_state)

    def _is_strategy_raise_action(self, action: "StrategyAction") -> bool:
        """判断策略动作是否为加注类动作。

        Args:
            action: 策略动作。

        Returns:
            若为 raise/bet/all-in 则返回 `True`。
        """
        action_type = str(action.action_type).upper()
        if action.is_all_in:
            return True
        return action_type in {"RAISE", "BET"} or action.action_code.upper().startswith("R")

    def _build_weighted_raise_evs(self, node: "StrategyNode") -> list[float] | None:
        """按 raise 动作频率加权聚合 169 维 EV。

        Args:
            node: 策略节点。

        Returns:
            聚合后的 EV 向量, 不存在 raise 动作时返回 `None`。
        """
        raise_actions = [
            action for action in node.actions if self._is_strategy_raise_action(action)
        ]
        if not raise_actions:
            return None

        raw_weights = [max(0.0, float(action.total_frequency)) for action in raise_actions]
        weight_sum = sum(raw_weights)
        if weight_sum <= 1e-9:
            raw_weights = [1.0] * len(raise_actions)
            weight_sum = float(len(raise_actions))

        evs_169 = [0.0] * RANGE_169_LENGTH
        for idx_169 in range(RANGE_169_LENGTH):
            weighted_ev = 0.0
            for action, weight in zip(raise_actions, raw_weights):
                weighted_ev += float(action.range.evs[idx_169]) * float(weight)
            evs_169[idx_169] = weighted_ev / weight_sum
        return evs_169

    def _build_ev_ranked_rfi_range(
        self,
        *,
        evs_169: Sequence[float],
        target_frequency: float,
    ) -> PreflopRange:
        """按 EV 排序并按目标频率裁剪 RFI 范围。

        Args:
            evs_169: 169 维 EV 向量。
            target_frequency: 目标 RFI 频率。

        Returns:
            裁剪后的翻前范围。
        """
        sorted_indices = sorted(
            range(RANGE_169_LENGTH),
            key=lambda idx_169: (float(evs_169[idx_169]), -idx_169),
            reverse=True,
        )
        remaining_combos = _clamp_probability(target_frequency) * float(RANGE_1326_LENGTH)
        strategy = [0.0] * RANGE_169_LENGTH

        for idx_169 in sorted_indices:
            if remaining_combos <= 0.0:
                break
            combo_count = float(combos_per_hand(RANGE_169_ORDER[idx_169]))
            if remaining_combos >= combo_count:
                strategy[idx_169] = 1.0
                remaining_combos -= combo_count
                continue
            strategy[idx_169] = remaining_combos / combo_count
            remaining_combos = 0.0

        return PreflopRange(strategy=strategy, evs=list(evs_169))

    def _get_player_or_aggregated_stats(self, player: "Player") -> "PlayerStats | None":
        """获取玩家统计, 无命中时回退聚合统计。

        Args:
            player: 对手玩家。

        Returns:
            玩家统计或聚合统计, 不存在时返回 `None`。
        """
        if self.stats_repo is None:
            return None

        if player.player_id:
            player_stats = self.stats_repo.get(player.player_id, self.table_type)
            if player_stats is not None and player_stats.preflop_stats:
                return player_stats

        aggregated_stats = get_aggregated_player_stats(self.stats_repo, self.table_type)
        if aggregated_stats is None or not aggregated_stats.preflop_stats:
            return None
        return aggregated_stats

    def _get_rfi_frequency_for_prefix(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
        current_prefix: Sequence["PlayerAction"],
    ) -> float | None:
        """读取当前 prefix 的 RFI 频率。

        Args:
            player: 对手玩家。
            table_state: 当前牌桌状态。
            current_prefix: 包含当前动作的翻前前缀。

        Returns:
            RFI 频率, 不可获取时返回 `None`。
        """
        context = build_opponent_preflop_context(
            player=player,
            action_prefix=current_prefix,
            table_state=table_state,
            table_type=self.table_type,
        )
        if context.params is None:
            return None

        stats = self._get_player_or_aggregated_stats(player)
        if stats is None:
            return None

        action_stats = stats.get_preflop_stats(context.params)
        return _clamp_probability(float(action_stats.bet_raise_probability()))

    def _query_preflop_decision_node(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
        decision_prefix: Sequence["PlayerAction"],
    ) -> tuple["StrategyNode", str] | None:
        """根据决策前 prefix 查询翻前策略节点。

        Args:
            player: 对手玩家。
            table_state: 当前牌桌状态。
            decision_prefix: 玩家动作前的翻前前缀。

        Returns:
            `(策略节点, 查询历史)` 二元组, 未命中时返回 `None`。
        """
        if self.preflop_strategy is None:
            return None

        stack_bb = int(round(player.get_stack_bb(table_state.big_blind)))
        if stack_bb <= 0:
            return None

        history = build_preflop_history(
            list(decision_prefix),
            big_blind=table_state.big_blind,
        )
        # 当前实现先固定到 100bb 策略树。
        match = self.preflop_strategy.query(100, history)
        if match is None:
            LOGGER.debug(
                "rfi range: 未匹配策略节点 (history=%s, stack=%s)",
                history,
                stack_bb,
            )
            return None
        return match.node, history

    def _build_rfi_preflop_range_from_prefix(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
        decision_prefix: Sequence["PlayerAction"],
        current_prefix: Sequence["PlayerAction"],
    ) -> PreflopRange | None:
        """基于 prefix 构建 RFI 范围。

        Args:
            player: 对手玩家。
            table_state: 当前牌桌状态。
            decision_prefix: 玩家动作前的翻前前缀。
            current_prefix: 包含当前动作的翻前前缀。

        Returns:
            RFI 范围, 不满足条件时返回 `None`。
        """
        if self.preflop_strategy is None or self.stats_repo is None:
            return None

        rfi_frequency = self._get_rfi_frequency_for_prefix(
            player=player,
            table_state=table_state,
            current_prefix=current_prefix,
        )
        if rfi_frequency is None:
            return None

        query_result = self._query_preflop_decision_node(
            player=player,
            table_state=table_state,
            decision_prefix=decision_prefix,
        )
        if query_result is None:
            return None
        node, history = query_result

        evs_169 = self._build_weighted_raise_evs(node)
        if evs_169 is None:
            return None

        rfi_range = self._build_ev_ranked_rfi_range(
            evs_169=evs_169,
            target_frequency=rfi_frequency,
        )
        LOGGER.debug(
            "rfi range: player=%s, history=%s, rfi_freq=%.4f, total_freq=%.4f",
            player.player_id,
            history,
            rfi_frequency,
            rfi_range.total_frequency(),
        )
        return rfi_range

    def _build_preflop_range_from_prefix(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
        action_prefix: Sequence["PlayerAction"],
    ) -> PreflopRange | None:
        """按翻前场景分层构建翻前范围。

        Args:
            player: 触发动作玩家。
            table_state: 当前牌桌状态。
            action_prefix: 当前动作前缀。

        Returns:
            构建出的翻前范围, 不满足条件时返回 `None`。
        """
        context = build_opponent_preflop_context(
            player=player,
            action_prefix=action_prefix,
            table_state=table_state,
            table_type=self.table_type,
        )
        if context.scenario == PreflopScenario.RFI_FACE_LIMPER:
            return self._build_limp_preflop_range_from_prefix(
                player=player,
                table_state=table_state,
                action_prefix=action_prefix,
            )
        LOGGER.debug(
            "非 limp 前缀分层暂不处理: player=%s, scenario=%s, history=%s",
            player.player_id,
            context.scenario.value,
            context.query_history,
        )
        return None

    def _build_limp_preflop_range_from_prefix(
        self,
        *,
        player: "Player",
        table_state: "ObservedTableState",
        action_prefix: Sequence["PlayerAction"],
    ) -> PreflopRange | None:
        """基于动作前缀构建 limp calling range。

        Args:
            player: 触发动作玩家。
            table_state: 当前牌桌状态。
            action_prefix: 当前动作前缀。

        Returns:
            构建出的翻前范围, 不满足条件时返回 `None`。
        """
        if not self.preflop_strategy or not self.stats_repo:
            return None

        context = build_opponent_preflop_context(
            player=player,
            action_prefix=action_prefix,
            table_state=table_state,
            table_type=self.table_type,
        )
        if context.scenario != PreflopScenario.RFI_FACE_LIMPER:
            return None
        if context.params is None:
            return None

        stack_bb = int(round(player.get_stack_bb(table_state.big_blind)))
        if stack_bb <= 0:
            return None
        # 筹码深度写死 100
        match = self.preflop_strategy.query(100, context.query_history)
        if match is None:
            LOGGER.debug(
                "limp calling range: 未匹配策略节点 (history=%s, stack=%s)",
                context.query_history,
                stack_bb,
            )
            return None

        aggregated_stats = get_aggregated_player_stats(self.stats_repo, self.table_type)
        if aggregated_stats is None:
            LOGGER.debug(
                "limp calling range: 缺少聚合玩家统计 (table_type=%s)", self.table_type
            )
            return None

        action_stats = aggregated_stats.get_preflop_stats(context.params)
        raise_frequency = float(action_stats.bet_raise_probability())
        call_frequency = float(action_stats.check_call_probability())
        calling_range = build_limp_calling_range(
            node=match.node,
            raise_frequency=raise_frequency,
            call_frequency=call_frequency,
        )
        LOGGER.debug(
            (
                "limp calling range: player=%s, history=%s, "
                "raise_freq=%.4f, call_freq=%.4f, total_freq=%.4f"
            ),
            player.player_id,
            context.query_history,
            raise_frequency,
            call_frequency,
            calling_range.total_frequency(),
        )
        return calling_range

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
        return self._get_position_default_range(_coerce_table_position(player.position))

    def _range_from_vpip(self, vpip: float) -> PreflopRange | None:
        """根据 VPIP 生成初始范围。"""
        if vpip <= 0:
            return None
        frequency = min(1.0, vpip / 100.0)
        strategy = [frequency] * RANGE_169_LENGTH
        return PreflopRange(strategy=strategy)

    def _get_position_default_range(
        self,
        position: TablePosition | None,
    ) -> PreflopRange:
        """根据位置获取默认范围。"""
        position_vpip = {
            TablePosition.UTG: 0.15,
            TablePosition.MP: 0.18,
            TablePosition.CO: 0.25,
            TablePosition.BTN: 0.40,
            TablePosition.SB: 0.35,
            TablePosition.BB: 0.50,
        }
        frequency = position_vpip.get(position, 0.25)
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
