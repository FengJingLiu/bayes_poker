"""strategy_engine v2 的对手范围更新管线。"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from bayes_poker.comm.session import SessionConfig
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
)
from bayes_poker.strategy.range.belief_adjustment import (
    adjust_belief_range,
)
from bayes_poker.table.observed_state import ObservedTableState

from .calibrator import (
    ActionPolicy,
    ActionPolicyAction,
)
from .context_builder import build_player_node_context
from .gto_policy import (
    GtoPriorAction,
    GtoPriorBuilder,
    GtoPriorPolicy,
)
from .node_mapper import StrategyNodeMapper
from .repository_adapter import (
    StrategyRepositoryAdapter,
)
from .session_context import (
    StrategySessionContext,
    StrategySessionStore,
)
from .stats_adapter import (
    PlayerNodeStats,
    PlayerNodeStatsAdapter,
)

_BELIEF_LOW_MASS_THRESHOLD = 1e-9


@dataclass(frozen=True, slots=True)
class _PosteriorResult:
    """对手后验范围构建结果, 包含范围和节点统计。"""

    range: PreflopRange
    node_stats: PlayerNodeStats


@dataclass(frozen=True, slots=True)
class OpponentPipelineConfig:
    """对手范围更新管线配置。"""

    table_type: TableType = TableType.SIX_MAX
    session_timeout: float = SessionConfig.session_timeout


class OpponentPipeline:
    """在 hero 回合重建对手实际范围。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        stats_adapter: PlayerNodeStatsAdapter,
        source_id: int | Sequence[int],
        config: OpponentPipelineConfig | None = None,
    ) -> None:
        """初始化对手范围更新管线.

        Args:
            repository_adapter: 策略仓库适配器.
            stats_adapter: 节点统计适配器.
            source_id: 策略源 ID 或 ID 序列.
            config: 可选管线配置.
        """

        self._repository_adapter = repository_adapter
        self._stats_adapter = stats_adapter
        self._source_id = source_id
        self._config = config or OpponentPipelineConfig()
        self._session_store = StrategySessionStore(
            session_timeout=self._config.session_timeout,
        )

    def process_hero_snapshot(
        self,
        *,
        session_id: str,
        observed_state: ObservedTableState,
    ) -> StrategySessionContext:
        """在 hero 回合处理当前快照。"""

        self._session_store.cleanup_expired()
        context = self._session_store.get_or_create(
            session_id=session_id,
            table_id=observed_state.table_id,
            hand_id=observed_state.hand_id,
            state_version=observed_state.state_version,
        )
        context.last_seen_monotonic = time.monotonic()

        if observed_state.actor_seat != observed_state.hero_seat:
            return context

        fingerprint = observed_state.get_action_history_string()
        if context.last_action_fingerprint == fingerprint:
            return context

        live_opponents = [
            player
            for player in observed_state.players
            if player.seat_index != observed_state.hero_seat and not player.is_folded
        ]
        live_opponent_seats = {player.seat_index for player in live_opponents}
        live_opponents_by_seat = {
            player.seat_index: player for player in live_opponents
        }
        latest_live_action_indices = (
            observed_state.get_live_opponent_last_action_indices_before_current_turn()
        )
        acted_opponents = [
            (live_opponents_by_seat[seat], action_index)
            for seat, action_index in latest_live_action_indices
            if seat in live_opponents_by_seat
        ]
        acted_seats = {player.seat_index for player, _ in acted_opponents}
        prior_only_opponents = [
            player for player in live_opponents if player.seat_index not in acted_seats
        ]

        for seat in tuple(context.player_ranges):
            if seat not in live_opponent_seats:
                context.player_ranges.pop(seat, None)
        for seat in tuple(context.player_summaries):
            if seat not in live_opponent_seats:
                context.player_summaries.pop(seat, None)

        for player, action_index in acted_opponents:
            seat = player.seat_index
            prefix = list(
                observed_state.get_preflop_prefix_before_action_index(action_index)
            )
            action = observed_state.action_history[action_index]
            prior_policy = self._build_initial_prior_range(
                player=player,
                observed_state=observed_state,
                decision_prefix=prefix,
            )
            matched_prior_action = _select_matching_prior_action(
                prior_policy=prior_policy,
                action=action,
                big_blind=observed_state.big_blind,
            )
            posterior_result = self._build_posterior_range(
                player=player,
                observed_state=observed_state,
                action=action,
                decision_prefix=prefix,
                prior_policy=prior_policy,
            )
            context.player_ranges[seat] = posterior_result.range
            # GTO 先验各动作频率
            prior_action_dist = {
                a.action_name: a.blended_frequency for a in prior_policy.actions
            }
            # 贝叶斯平滑后的 F/C/R 概率
            ns = posterior_result.node_stats
            stats_action_dist = {
                "F": ns.fold_probability,
                "C": ns.call_probability,
                "R": ns.raise_probability,
            }
            context.player_summaries[seat] = {
                "status": "posterior",
                "source_kind": self._last_source_kind,
                "prior_frequency": matched_prior_action.blended_frequency,
                "matched_action_type": action.action_type.value,
                "prior_action_distribution": prior_action_dist,
                "stats_action_distribution": stats_action_dist,
            }

        for player in prior_only_opponents:
            seat = player.seat_index
            context.player_ranges.pop(seat, None)
            # TODO: 后续版本恢复未行动玩家的先验统计/摘要建模。
            context.player_summaries[seat] = {
                "status": "prior_only_deferred",
            }

        context.last_action_fingerprint = fingerprint
        return context

    def _build_posterior_range(
        self,
        *,
        player: Player,
        observed_state: ObservedTableState,
        action: PlayerAction,
        decision_prefix: list[PlayerAction],
        prior_policy: GtoPriorPolicy,
    ) -> _PosteriorResult:
        state_for_player = self._build_state_for_player(
            player=player,
            observed_state=observed_state,
            decision_prefix=decision_prefix,
        )
        node_context = build_player_node_context(
            state_for_player,
            table_type=self._config.table_type,
        )
        node_stats = self._stats_adapter.load(
            player_name=player.player_id,
            table_type=self._config.table_type,
            node_context=node_context,
        )
        self._last_source_kind = node_stats.source_kind

        matched_action = _select_matching_prior_action(
            prior_policy=prior_policy,
            action=action,
            big_blind=observed_state.big_blind,
        )
        prior = _resolve_action_prior_range(matched_action)
        posterior_range = _adjust_belief_with_stats_and_ev(
            prior=prior,
            observed_action_type=action.action_type,
            node_stats=node_stats,
        )
        return _PosteriorResult(range=posterior_range, node_stats=node_stats)

    def _build_initial_prior_range(
        self,
        *,
        player: Player,
        observed_state: ObservedTableState,
        decision_prefix: list[PlayerAction],
    ) -> GtoPriorPolicy:
        state_for_player = self._build_state_for_player(
            player=player,
            observed_state=observed_state,
            decision_prefix=decision_prefix,
        )
        node_context = build_player_node_context(
            state_for_player,
            table_type=self._config.table_type,
        )
        # TODO: 6max gtow 策略只下载了 100BB 深度的，这里默认写死，后续添加策略后改逻辑
        stack_bb = 100
        resolved_stack = self._repository_adapter.resolve_stack_bb(
            source_id=self._source_id,
            requested_stack_bb=stack_bb,
        )
        mapped = StrategyNodeMapper(
            repository_adapter=self._repository_adapter,
            source_id=self._source_id,
            stack_bb=resolved_stack,
        ).map_node_context(node_context.node_context)
        return GtoPriorBuilder(
            repository_adapter=self._repository_adapter,
        ).build_policy(mapped)

    def _build_state_for_player(
        self,
        *,
        player: Player,
        observed_state: ObservedTableState,
        decision_prefix: list[PlayerAction],
    ) -> ObservedTableState:
        return ObservedTableState(
            table_id=observed_state.table_id,
            player_count=observed_state.player_count,
            small_blind=observed_state.small_blind,
            big_blind=observed_state.big_blind,
            hand_id=observed_state.hand_id,
            street=Street.PREFLOP,
            pot=observed_state.pot,
            btn_seat=observed_state.btn_seat,
            actor_seat=player.seat_index,
            hero_seat=observed_state.hero_seat,
            hero_cards=observed_state.hero_cards,
            board_cards=observed_state.board_cards,
            players=observed_state.players,
            action_history=decision_prefix,
            state_version=observed_state.state_version,
            timestamp=observed_state.timestamp,
        )




def _build_prior_range_from_policy(
    prior_policy: GtoPriorPolicy,
    *,
    action_name: str,
) -> PreflopRange:
    """按指定动作从 GTO 先验策略构建范围。

    Args:
        prior_policy: GTO 先验策略。
        action_name: 目标动作编码。

    Returns:
        目标动作对应的 hand-level 策略与 EV 范围。

    Raises:
        ValueError: 当先验策略不存在目标动作时抛出。
    """

    normalized_action_name = action_name.upper()
    for action in prior_policy.actions:
        if action.action_name.upper() != normalized_action_name:
            continue
        return _resolve_action_prior_range(action)
    raise ValueError(f"先验策略不存在目标动作: {action_name}")


def _select_matching_prior_action(
    *,
    prior_policy: GtoPriorPolicy,
    action: PlayerAction,
    big_blind: float,
) -> GtoPriorAction:
    """在先验策略中按真实动作匹配最接近动作。

    Args:
        prior_policy: 节点先验策略。
        action: 真实观测动作。
        big_blind: 大盲金额。

    Returns:
        与真实动作类型匹配, 且在同类型中尺度最接近的先验动作。

    Raises:
        ValueError: 当不存在动作类型匹配的先验动作时抛出。
    """

    expected_action_type = _expected_prior_action_type(action.action_type)
    candidates = [
        prior_action
        for prior_action in prior_policy.actions
        if _normalize_prior_action_type(prior_action.action_type)
        == expected_action_type
    ]
    if not candidates:
        raise ValueError(
            f"先验策略缺少与真实动作类型匹配的行为: {expected_action_type}"
        )

    if expected_action_type in {"RAISE", "BET", "ALL_IN"}:
        actual_size_bb = action.amount / big_blind if big_blind > 0 else 0.0
        return min(
            candidates,
            key=lambda prior_action: abs(
                _prior_action_size_bb(prior_action) - actual_size_bb
            ),
        )

    return max(candidates, key=lambda prior_action: prior_action.blended_frequency)


def _adjust_belief_with_stats_and_ev(
    *,
    prior: PreflopRange,
    observed_action_type: ActionType,
    node_stats: PlayerNodeStats,
) -> PreflopRange:
    """按 stats 目标频率与 EV 排序做约束式信念重分配。

    Args:
        prior: 该动作对应的先验范围。
        observed_action_type: 真实观测动作类型。
        node_stats: 平滑后的节点统计概率。

    Returns:
        调整后的后验范围。
    """

    target_frequency = _stats_frequency_for_action_type(
        observed_action_type=observed_action_type,
        node_stats=node_stats,
    )
    target_frequency = min(max(target_frequency, 0.0), 1.0)
    return adjust_belief_range(
        belief_range=prior,
        target_frequency=target_frequency,
        low_mass_threshold=_BELIEF_LOW_MASS_THRESHOLD,
    )


def _stats_frequency_for_action_type(
    *,
    observed_action_type: ActionType,
    node_stats: PlayerNodeStats,
) -> float:
    """读取观测动作类型对应的 stats 概率。"""

    if observed_action_type == ActionType.FOLD:
        return node_stats.fold_probability
    if observed_action_type in {ActionType.CALL, ActionType.CHECK}:
        return node_stats.call_probability
    if observed_action_type in {ActionType.RAISE, ActionType.BET, ActionType.ALL_IN}:
        return node_stats.raise_probability
    return 0.0


def _normalize_prior_action_type(action_type: str | None) -> str:
    """标准化先验动作类型。"""

    if action_type is None:
        return ""
    return action_type.strip().upper()


def _expected_prior_action_type(observed_action_type: ActionType) -> str:
    """将真实动作类型映射为先验动作类型。"""

    return observed_action_type.value.upper()


def _prior_action_size_bb(prior_action: GtoPriorAction) -> float:
    """读取先验动作尺度（BB）。"""

    if prior_action.bet_size_bb is not None:
        return prior_action.bet_size_bb
    return _raise_action_key(prior_action.action_name)


def _build_prior_only_range_from_policy(prior_policy: GtoPriorPolicy) -> PreflopRange:
    """为未行动对手构建 prior-only 范围。

    Args:
        prior_policy: GTO 先验策略。

    Returns:
        由非弃牌动作聚合得到的 continue 范围；若不可用则回退均匀范围。
    """

    action_ranges = [
        action.belief_range
        for action in prior_policy.actions
        if action.action_name.upper() != "F" and action.belief_range is not None
    ]
    if not action_ranges:
        return _build_uniform_continue_prior_range(prior_policy)

    # 堆叠所有动作范围的策略和 EV 矩阵
    strategy_stack = np.stack([r.strategy for r in action_ranges], axis=0)
    evs_stack = np.stack([r.evs for r in action_ranges], axis=0)

    # 向量化聚合
    strategy_stack_clipped = np.maximum(0.0, strategy_stack)
    continue_probability = np.sum(strategy_stack_clipped, axis=0)
    weighted_ev_numerator = np.sum(strategy_stack_clipped * evs_stack, axis=0)

    # 计算加权平均 EV
    evs_result = np.where(
        continue_probability > 0.0,
        weighted_ev_numerator / continue_probability,
        0.0
    )

    # Clip 概率到 [0, 1]
    strategy_result = np.clip(continue_probability, 0.0, 1.0)

    if not np.any(strategy_result > 0.0):
        return _build_uniform_continue_prior_range(prior_policy)

    return PreflopRange(strategy=strategy_result.astype(np.float32), evs=evs_result.astype(np.float32))


def _build_uniform_continue_prior_range(prior_policy: GtoPriorPolicy) -> PreflopRange:
    """按动作总频率构建均匀 continue 先验范围。

    Args:
        prior_policy: GTO 先验策略。

    Returns:
        每手牌概率相同的 continue 先验范围。
    """

    total_frequency = sum(
        max(0.0, action.blended_frequency) for action in prior_policy.actions
    )
    if total_frequency <= 0.0:
        raise ValueError("初始 prior 动作频率总和无效。")

    fold_frequency = sum(
        max(0.0, action.blended_frequency)
        for action in prior_policy.actions
        if action.action_name.upper() == "F"
    )
    continue_frequency = (total_frequency - fold_frequency) / total_frequency
    clipped = max(0.0, min(1.0, continue_frequency))
    return PreflopRange.from_list([clipped] * RANGE_169_LENGTH, [0.0] * RANGE_169_LENGTH)


def _resolve_action_prior_range(
    action: GtoPriorAction,
) -> PreflopRange:
    """解析动作对应的校准输入范围。

    Args:
        action: 先验动作。

    Returns:
        包含 hand-level strategy/EV 的范围。

    Raises:
        ValueError: 当 belief_range 缺失时抛出。
    """

    belief_range = action.belief_range
    if belief_range is None:
        raise ValueError(f"动作缺少 belief_range: {action.action_name}")

    strategy, evs = belief_range.to_list()
    return PreflopRange.from_list(strategy, evs)


def _raise_action_key(action_name: str) -> float:
    normalized = action_name.upper()
    if normalized == "RAI":
        return 1000.0
    if normalized.startswith("R"):
        try:
            return float(normalized[1:])
        except ValueError:
            return 0.0
    return 0.0
