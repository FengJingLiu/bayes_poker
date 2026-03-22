"""strategy_engine v2 的 hero GTO resolver。"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Sequence

from bayes_poker.domain.table import Player
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
)
from bayes_poker.strategy.range.belief_adjustment import (
    adjust_belief_range,
)
from bayes_poker.table.observed_state import ObservedTableState

from .context_builder import build_player_node_context
from .contracts import (
    RecommendationDecision,
    SafeFallbackDecision,
    StrategyDecision,
    UnsupportedScenarioDecision,
)
from .gto_policy import GtoPriorAction, GtoPriorBuilder, GtoPriorPolicy
from .node_mapper import StrategyNodeMapper
from .repository_adapter import (
    StrategyRepositoryAdapter,
)
from .session_context import StrategySessionContext

LOGGER = logging.getLogger(__name__)

_HERO_ADJUST_LOW_MASS_THRESHOLD = 1e-9

# 对手激进度比值的 clamp 上下界, 防止极端调整.
_AGGRESSION_RATIO_MIN = 0.1
_AGGRESSION_RATIO_MAX = 5.0

# 幂阻尼指数: adjusted_ratio = raw_ratio ^ _DAMPING_EXPONENT.
# 0.5 = 开方, 双向对称压缩极端值.
_DAMPING_EXPONENT = 0.5


class HeroGtoResolver:
    """根据当前 hero 节点返回 GTO 推荐。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        source_id: int | Sequence[int] | None = None,
        source_ids: Sequence[int] | None = None,
        random_generator: random.Random | None = None,
    ) -> None:
        """初始化 hero resolver.

        Args:
            repository_adapter: 策略仓库适配器.
            source_id: 策略源 ID 或 ID 序列.
            source_ids: 优先级更高的策略源 ID 序列.
            random_generator: 可注入的随机数生成器, 用于采样动作.

        Raises:
            ValueError: 当策略源选择器为空或无效时抛出.
        """

        self._repository_adapter = repository_adapter
        self._source_ids = _normalize_source_ids(
            source_id=source_id,
            source_ids=source_ids,
        )
        self._random = (
            random_generator if random_generator is not None else random.Random()
        )

    def resolve(
        self,
        *,
        observed_state: ObservedTableState,
        session_context: StrategySessionContext,
        source_ids: Sequence[int] | None = None,
    ) -> StrategyDecision:
        """解析当前 hero 节点的 GTO 推荐。

        Args:
            observed_state: 当前观测到的牌桌状态.
            session_context: 当前会话上下文.
            source_ids: 可选的策略源优先级序列, 会覆盖初始化参数.

        Returns:
            Hero 决策结果.
        """

        _assert_acted_opponents_have_posterior(
            observed_state=observed_state,
            session_context=session_context,
        )

        try:
            active_source_ids = (
                _normalize_source_ids(source_id=None, source_ids=source_ids)
                if source_ids is not None
                else self._source_ids
            )
            node_context = build_player_node_context(observed_state)
            hero_player = _find_player(observed_state, observed_state.hero_seat)
            if hero_player is None:
                raise ValueError("找不到 hero 玩家信息。")
            stack_bb = max(
                1, int(round(hero_player.get_stack_bb(observed_state.big_blind)))
            )
            resolved_stack = self._repository_adapter.resolve_stack_bb(
                source_id=active_source_ids,
                requested_stack_bb=stack_bb,
            )
            mapped_context = StrategyNodeMapper(
                repository_adapter=self._repository_adapter,
                source_id=active_source_ids,
                stack_bb=resolved_stack,
            ).map_node_context(
                node_context.node_context,
                preferred_history_actions=_build_acted_history_actions(observed_state),
            )
            policy = GtoPriorBuilder(
                repository_adapter=self._repository_adapter,
            ).build_policy(mapped_context)
            prior_action_distribution = _build_action_distribution(policy)
            aggression_ratio, opponent_details = _compute_opponent_aggression_ratio(
                session_context=session_context,
                observed_state=observed_state,
            )
            adjusted_policy = _adjust_hero_policy(
                policy=policy,
                aggression_ratio=aggression_ratio,
            )
            action_distribution = _build_action_distribution(adjusted_policy)
            random_value = self._random.random()
            sampled_action = _sample_action(
                policy=adjusted_policy,
                action_distribution=action_distribution,
                random_value=random_value,
            )
            adjusted_belief_ranges = _extract_adjusted_belief_ranges(adjusted_policy)
            return RecommendationDecision(
                state_version=observed_state.state_version,
                action_code=sampled_action.action_name,
                amount=_extract_amount(sampled_action.action_name),
                confidence=action_distribution[sampled_action.action_name],
                ev=None,
                notes=(
                    f"hero_posterior_deferred_v1; matched_history={mapped_context.matched_history}"
                    f"; aggression_ratio={aggression_ratio:.4f}"
                ),
                action_evs={
                    action.action_name: action.total_ev
                    for action in adjusted_policy.actions
                    if action.total_ev is not None
                },
                action_distribution=action_distribution,
                prior_action_distribution=prior_action_distribution,
                selected_node_id=mapped_context.matched_node_id,
                selected_source_id=mapped_context.matched_source_id,
                sampling_random=random_value,
                range_breakdown={
                    f"seat_{seat}": player_range.total_frequency()
                    for seat, player_range in session_context.player_ranges.items()
                },
                opponent_aggression_details=opponent_details,
                adjusted_belief_ranges=adjusted_belief_ranges,
            )
        except ValueError as exc:
            return UnsupportedScenarioDecision(
                state_version=observed_state.state_version,
                reason=str(exc),
            )
        except Exception as exc:
            LOGGER.exception("hero_resolver 意外错误: %s", exc)
            return SafeFallbackDecision(
                state_version=observed_state.state_version,
                error_code="hero_resolver_error",
                notes=str(exc),
            )


def _find_player(observed_state: ObservedTableState, seat_index: int) -> Player | None:
    """按座位号查找玩家。

    Args:
        observed_state: 当前观测状态.
        seat_index: 目标座位号.

    Returns:
        命中的玩家对象, 未命中返回 `None`.
    """

    for player in observed_state.players:
        if player.seat_index == seat_index:
            return player
    return None


def _normalize_source_ids(
    *,
    source_id: int | Sequence[int] | None,
    source_ids: Sequence[int] | None,
) -> tuple[int, ...]:
    """规范化策略源优先级序列。

    Args:
        source_id: 单个或多个策略源 ID.
        source_ids: 显式策略源优先级序列.

    Returns:
        去重后的策略源优先级元组.

    Raises:
        ValueError: 当输入为空或包含非整型值时抛出.
    """

    if source_ids is not None:
        ordered = tuple(source_ids)
    elif isinstance(source_id, int):
        ordered = (source_id,)
    elif source_id is not None:
        ordered = tuple(source_id)
    else:
        raise ValueError("source_ids 不能为空。")

    if not ordered:
        raise ValueError("source_ids 不能为空。")
    if any(not isinstance(current_source_id, int) for current_source_id in ordered):
        raise ValueError("source_ids 必须为 int 序列。")

    deduplicated: list[int] = []
    seen_source_ids: set[int] = set()
    for current_source_id in ordered:
        if current_source_id in seen_source_ids:
            continue
        deduplicated.append(current_source_id)
        seen_source_ids.add(current_source_id)
    return tuple(deduplicated)


def _collect_acted_live_opponent_seats(
    observed_state: ObservedTableState,
) -> tuple[int, ...]:
    """收集当前决策点前已行动且仍存活的对手座位。

    Args:
        observed_state: 当前观测状态.

    Returns:
        按最近一次动作索引升序排列的对手座位元组.
    """

    last_actions = (
        observed_state.get_live_opponent_last_action_indices_before_current_turn()
    )
    return tuple(seat for seat, _ in last_actions)


def _build_acted_history_actions(observed_state: ObservedTableState) -> str:
    """构建当前决策点之前的翻前行动线签名。

    Args:
        observed_state: 当前观测状态。

    Returns:
        以 `-` 拼接的行动线签名, 例如 `R-C`。
    """

    return observed_state.get_preflop_history_tokens_before_current_turn()


def _assert_acted_opponents_have_posterior(
    *,
    observed_state: ObservedTableState,
    session_context: StrategySessionContext,
) -> None:
    """校验 hero 决策前已行动对手的后验范围已经准备完毕。

    Args:
        observed_state: 当前观测状态.
        session_context: 当前会话上下文.

    Raises:
        ValueError: 当存在已行动对手缺少 posterior 范围时抛出.
    """

    missing_seats: list[int] = []
    for seat in _collect_acted_live_opponent_seats(observed_state):
        summary = session_context.player_summaries.get(seat)
        if summary is None or summary.get("status") != "posterior":
            missing_seats.append(seat)
            continue
        player_range = session_context.player_ranges.get(seat)
        if player_range is None:
            missing_seats.append(seat)
            continue
        if player_range.total_frequency() <= 0.0:
            missing_seats.append(seat)

    if missing_seats:
        raise ValueError(
            "hero 决策前存在未完成后验范围计算的已行动玩家: "
            + ",".join(str(seat) for seat in missing_seats)
        )


def _extract_adjusted_belief_ranges(
    policy: GtoPriorPolicy,
) -> dict[str, PreflopRange]:
    """从调整后策略中提取 belief_range 映射.

    Args:
        policy: 经 ``_adjust_hero_policy`` 调整后的 GTO 策略.

    Returns:
        ``action_code -> PreflopRange`` 映射; 只包含有 belief_range 的动作.
    """
    result: dict[str, PreflopRange] = {}
    for action in policy.actions:
        if action.belief_range is not None:
            result[action.action_name] = action.belief_range
    return result


def _build_action_distribution(policy: GtoPriorPolicy) -> dict[str, float]:
    """构建并校验动作分布。

    Args:
        policy: 当前节点的先验策略。

    Returns:
        动作到概率的映射, 概率和为 1。

    Raises:
        ValueError: 当动作为空、存在负值, 或总和不等于 1 时抛出.
    """

    if not policy.actions:
        raise ValueError("当前节点不存在可用动作。")

    raw_distribution: dict[str, float] = {}
    for action in policy.actions:
        if action.blended_frequency < 0.0:
            raise ValueError(f"动作概率不能为负: {action.action_name}")
        raw_distribution[action.action_name] = action.blended_frequency

    total_frequency = sum(raw_distribution.values())
    if not math.isfinite(total_frequency) or total_frequency <= 0.0:
        raise ValueError("动作概率总和无效。")
    if not math.isclose(total_frequency, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError(f"动作概率总和必须为 1, 当前为 {total_frequency:.6f}")

    return {
        action_name: probability / total_frequency
        for action_name, probability in raw_distribution.items()
    }


def _sample_action(
    *,
    policy: GtoPriorPolicy,
    action_distribution: dict[str, float],
    random_value: float,
) -> GtoPriorAction:
    """根据动作分布和随机数采样一个动作。

    Args:
        policy: 当前节点的先验策略。
        action_distribution: 动作概率分布。
        random_value: 区间 `[0, 1)` 上的随机数。

    Returns:
        被采样到的动作。

    Raises:
        ValueError: 当随机数越界或动作分布缺失时抛出.
    """

    if random_value < 0.0 or random_value >= 1.0:
        raise ValueError("采样随机数必须在 [0, 1) 区间。")

    cumulative_probability = 0.0
    for action in policy.actions:
        probability = action_distribution.get(action.action_name)
        if probability is None:
            raise ValueError(f"动作分布缺少动作: {action.action_name}")
        cumulative_probability += probability
        if random_value <= cumulative_probability:
            return action

    return policy.actions[-1]


def _extract_amount(action_name: str) -> float | None:
    """从动作编码中解析下注量。

    Args:
        action_name: 动作编码。

    Returns:
        解析出的下注量, 无法解析时返回 `0.0`。
    """

    normalized = action_name.upper()
    if normalized == "RAI":
        return 0.0
    if normalized.startswith("R"):
        try:
            return float(normalized[1:])
        except ValueError:
            return 0.0
    return 0.0


def _is_aggressive_action(action_name: str) -> bool:
    """判断动作编码是否属于激进动作 (Raise/Bet/All-in).

    Args:
        action_name: 动作编码, 如 'R2.5', 'RAI', 'F', 'C'.

    Returns:
        是否为激进动作.
    """
    normalized = action_name.upper()
    return normalized.startswith("R") or normalized == "RAI"


def _is_call_action(action_name: str) -> bool:
    """判断动作编码是否属于 call/check 类动作.

    Args:
        action_name: 动作编码, 如 'C', 'X', 'F'.

    Returns:
        是否为 call/check 动作.
    """
    normalized = action_name.upper()
    return normalized in {"C", "X"}


def _compute_opponent_aggression_ratio(
    *,
    session_context: StrategySessionContext,
    observed_state: ObservedTableState,
) -> tuple[float, list[dict[str, object]]]:
    """计算所有已行动对手的聚合激进度比值(含幂阻尼), 并返回逐对手明细.

    对每位后验状态对手, 读取 posterior_freq / prior_freq 比值,
    然后应用幂阻尼 dampened = raw^_DAMPING_EXPONENT 压缩极端值.

    多个对手的 dampened 比值取乘积后做 clamp.

    Args:
        session_context: 当前会话上下文, 包含对手后验范围与摘要.
        observed_state: 当前观测状态.

    Returns:
        (clamped_ratio, details) 二元组.
        - clamped_ratio: 聚合后的激进度调整系数 (>1 => hero 应更激进, <1 => hero 应更保守).
        - details: 逐对手明细列表, 每项包含 seat / player_id / prior_freq / posterior_freq / ratio.
    """
    acted_seats = _collect_acted_live_opponent_seats(observed_state)
    if not acted_seats:
        return 1.0, []

    combined_ratio = 1.0
    details: list[dict[str, object]] = []
    for seat in acted_seats:
        summary = session_context.player_summaries.get(seat)
        if summary is None or summary.get("status") != "posterior":
            continue

        prior_freq_raw = summary.get("prior_frequency")
        if not isinstance(prior_freq_raw, (int, float)):
            continue
        prior_freq: float = float(prior_freq_raw)

        player_range = session_context.player_ranges.get(seat)
        if player_range is None:
            continue

        posterior_freq = player_range.total_frequency()
        if prior_freq <= _HERO_ADJUST_LOW_MASS_THRESHOLD:
            continue
        if posterior_freq <= _HERO_ADJUST_LOW_MASS_THRESHOLD:
            continue

        raw_ratio = posterior_freq / prior_freq

        player_id: str = ""
        if seat < len(observed_state.players):
            player_id = observed_state.players[seat].player_id

        dampened_ratio = raw_ratio**_DAMPING_EXPONENT

        details.append(
            {
                "seat": seat,
                "player_id": player_id,
                "prior_freq": prior_freq,
                "posterior_freq": posterior_freq,
                "ratio": raw_ratio,
                "dampened_ratio": dampened_ratio,
                "source_kind": summary.get("source_kind", ""),
                "prior_action_distribution": summary.get(
                    "prior_action_distribution", {}
                ),
                "stats_action_distribution": summary.get(
                    "stats_action_distribution", {}
                ),
            }
        )

        combined_ratio *= dampened_ratio

    clamped = max(_AGGRESSION_RATIO_MIN, min(combined_ratio, _AGGRESSION_RATIO_MAX))
    LOGGER.debug(
        "hero 激进度调整系数: raw=%.4f, clamped=%.4f",
        combined_ratio,
        clamped,
    )
    return clamped, details


def _adjust_hero_policy(
    *,
    policy: GtoPriorPolicy,
    aggression_ratio: float,
) -> GtoPriorPolicy:
    """根据对手激进度比值调整 hero 策略.

    激进动作 (R*) 的频率乘以 aggression_ratio, 被动动作 (F/C) 按剩余份额
    等比重分配. 同时对激进动作的 belief_range 做 EV-ranked 重分配.

    Args:
        policy: 原始 GTO 先验策略 (frozen).
        aggression_ratio: 激进度调整系数.

    Returns:
        调整后的新 GtoPriorPolicy.
    """
    if math.isclose(aggression_ratio, 1.0, rel_tol=1e-6):
        return policy

    aggressive_actions: list[GtoPriorAction] = []
    passive_actions: list[GtoPriorAction] = []
    for action in policy.actions:
        if _is_aggressive_action(action.action_name):
            aggressive_actions.append(action)
        else:
            passive_actions.append(action)

    if not aggressive_actions or not passive_actions:
        return policy

    total_aggressive_freq = sum(a.blended_frequency for a in aggressive_actions)
    total_passive_freq = sum(a.blended_frequency for a in passive_actions)
    if total_aggressive_freq <= _HERO_ADJUST_LOW_MASS_THRESHOLD:
        return policy

    new_aggressive_total = min(
        total_aggressive_freq * aggression_ratio,
        1.0 - _HERO_ADJUST_LOW_MASS_THRESHOLD,
    )
    new_aggressive_total = max(new_aggressive_total, 0.0)
    new_passive_total = 1.0 - new_aggressive_total

    agg_scale = (
        new_aggressive_total / total_aggressive_freq
        if total_aggressive_freq > _HERO_ADJUST_LOW_MASS_THRESHOLD
        else 1.0
    )
    pass_scale = (
        new_passive_total / total_passive_freq
        if total_passive_freq > _HERO_ADJUST_LOW_MASS_THRESHOLD
        else 1.0
    )

    adjusted_actions: list[GtoPriorAction] = []
    for action in policy.actions:
        if _is_aggressive_action(action.action_name):
            new_freq = action.blended_frequency * agg_scale
            new_belief = None
            if action.belief_range is not None:
                old_total = action.belief_range.total_frequency()
                new_target = old_total * agg_scale
                new_target = min(max(new_target, 0.0), 1.0)
                new_belief = adjust_belief_range(
                    belief_range=action.belief_range,
                    target_frequency=new_target,
                    low_mass_threshold=_HERO_ADJUST_LOW_MASS_THRESHOLD,
                )
            adjusted_actions.append(
                GtoPriorAction(
                    action_name=action.action_name,
                    blended_frequency=new_freq,
                    source_id=action.source_id,
                    node_id=action.node_id,
                    action_type=action.action_type,
                    bet_size_bb=action.bet_size_bb,
                    is_all_in=action.is_all_in,
                    next_position=action.next_position,
                    belief_range=new_belief
                    if new_belief is not None
                    else action.belief_range,
                    total_ev=action.total_ev,
                    total_combos=action.total_combos,
                )
            )
        else:
            new_freq = action.blended_frequency * pass_scale
            new_belief = action.belief_range
            if _is_call_action(action.action_name) and action.belief_range is not None:
                old_total = action.belief_range.total_frequency()
                call_target = old_total * aggression_ratio
                call_target = min(max(call_target, 0.0), 1.0)
                new_belief = adjust_belief_range(
                    belief_range=action.belief_range,
                    target_frequency=call_target,
                    low_mass_threshold=_HERO_ADJUST_LOW_MASS_THRESHOLD,
                )
            adjusted_actions.append(
                GtoPriorAction(
                    action_name=action.action_name,
                    blended_frequency=new_freq,
                    source_id=action.source_id,
                    node_id=action.node_id,
                    action_type=action.action_type,
                    bet_size_bb=action.bet_size_bb,
                    is_all_in=action.is_all_in,
                    next_position=action.next_position,
                    belief_range=new_belief,
                    total_ev=action.total_ev,
                    total_combos=action.total_combos,
                )
            )

    normalized_actions = _normalize_adjusted_action_belief_ranges(
        adjusted_actions=adjusted_actions,
    )

    return GtoPriorPolicy(
        action_names=policy.action_names,
        actions=normalized_actions,
        price_adjustment_applied=policy.price_adjustment_applied,
        price_adjustment_factor=policy.price_adjustment_factor,
        synthetic_template_kind=policy.synthetic_template_kind,
    )


def _normalize_adjusted_action_belief_ranges(
    *,
    adjusted_actions: list[GtoPriorAction],
) -> tuple[GtoPriorAction, ...]:
    """将调整后的动作 belief_range 归一化为跨动作互斥分配.

    当前 hero 调整链路会对 raise 与 call/check 的 belief_range 分别做
    EV-ranked 重分配。为了让导出的 action-level range 可直接解释为单一动作
    策略矩阵, 需要在每个手牌维度上保证各动作总频率不超过 1.0。

    约束策略:
    - `F` 的 belief_range 视为受保护质量, 不参与缩放。
    - `C/X` 与激进动作 (`R*`/`RAI`) 视为可调整质量, 当总和超出剩余容量时
      按比例统一压缩。

    Args:
        adjusted_actions: `_adjust_hero_policy` 已计算出的动作列表。

    Returns:
        belief_range 已归一化后的动作元组。
    """
    normalized_strategies: list[list[float] | None] = []
    evs_by_action: list[list[float] | None] = []
    adjustable_flags: list[bool] = []

    for action in adjusted_actions:
        if action.belief_range is None:
            normalized_strategies.append(None)
            evs_by_action.append(None)
            adjustable_flags.append(False)
            continue
        normalized_strategies.append(list(action.belief_range.strategy))
        evs_by_action.append(list(action.belief_range.evs))
        adjustable_flags.append(
            _is_aggressive_action(action.action_name) or _is_call_action(action.action_name)
        )

    for index in range(RANGE_169_LENGTH):
        protected_total = 0.0
        adjustable_total = 0.0

        for strategy, is_adjustable in zip(
            normalized_strategies,
            adjustable_flags,
            strict=True,
        ):
            if strategy is None:
                continue
            value = strategy[index]
            if is_adjustable:
                adjustable_total += value
            else:
                protected_total += value

        remaining_capacity = max(0.0, 1.0 - protected_total)
        if adjustable_total <= remaining_capacity + _HERO_ADJUST_LOW_MASS_THRESHOLD:
            continue
        if adjustable_total <= _HERO_ADJUST_LOW_MASS_THRESHOLD:
            continue

        scale = remaining_capacity / adjustable_total
        for strategy, is_adjustable in zip(
            normalized_strategies,
            adjustable_flags,
            strict=True,
        ):
            if strategy is None or not is_adjustable:
                continue
            strategy[index] *= scale

    normalized_actions: list[GtoPriorAction] = []
    for action, strategy, evs, is_adjustable in zip(
        adjusted_actions,
        normalized_strategies,
        evs_by_action,
        adjustable_flags,
        strict=True,
    ):
        if not is_adjustable:
            normalized_actions.append(action)
            continue
        if strategy is None or evs is None:
            normalized_actions.append(action)
            continue
        normalized_actions.append(
            GtoPriorAction(
                action_name=action.action_name,
                blended_frequency=action.blended_frequency,
                source_id=action.source_id,
                node_id=action.node_id,
                action_type=action.action_type,
                bet_size_bb=action.bet_size_bb,
                is_all_in=action.is_all_in,
                next_position=action.next_position,
                belief_range=PreflopRange(strategy=strategy, evs=evs),
                total_ev=action.total_ev,
                total_combos=action.total_combos,
            )
        )

    return tuple(normalized_actions)
