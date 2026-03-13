"""strategy_engine v2 的 hero GTO resolver。"""

from __future__ import annotations

from collections.abc import Sequence

from bayes_poker.domain.table import Player
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
from bayes_poker.table.observed_state import ObservedTableState

_HEURISTIC_EPSILON = 1e-9
_HEURISTIC_MAX_SHIFT = 0.20


class HeroGtoResolver:
    """根据当前 hero 节点返回 GTO 推荐。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        source_id: int | Sequence[int],
    ) -> None:
        """初始化 hero resolver.

        Args:
            repository_adapter: 策略仓库适配器.
            source_id: 策略源 ID 或 ID 序列.
        """

        self._repository_adapter = repository_adapter
        self._source_id = source_id

    def resolve(
        self,
        *,
        observed_state: ObservedTableState,
        session_context: StrategySessionContext,
    ) -> StrategyDecision:
        """解析当前 hero 节点的 GTO 推荐。"""

        try:
            node_context = build_player_node_context(observed_state)
            hero_player = _find_player(observed_state, observed_state.hero_seat)
            if hero_player is None:
                raise ValueError("找不到 hero 玩家信息。")
            stack_bb = max(
                1, int(round(hero_player.get_stack_bb(observed_state.big_blind)))
            )
            resolved_stack = self._repository_adapter.resolve_stack_bb(
                source_id=self._source_id,
                requested_stack_bb=stack_bb,
            )
            mapped_context = StrategyNodeMapper(
                repository_adapter=self._repository_adapter,
                source_id=self._source_id,
                stack_bb=resolved_stack,
            ).map_node_context(node_context.node_context)
            policy = GtoPriorBuilder(
                repository_adapter=self._repository_adapter,
            ).build_policy(mapped_context)
            adjusted_frequencies, heuristic_note = (
                _build_prior_only_heuristic_frequencies(
                    policy=policy,
                    session_context=session_context,
                )
            )
            best_action = _select_best_action(
                policy,
                action_frequencies=adjusted_frequencies,
            )
            best_confidence = _get_action_frequency(
                best_action,
                adjusted_frequencies,
            )
            notes = f"hero_posterior_deferred_v1; matched_history={mapped_context.matched_history}"
            if heuristic_note is not None:
                notes = f"{notes}; {heuristic_note}"
            return RecommendationDecision(
                state_version=observed_state.state_version,
                action_code=best_action.action_name,
                amount=_extract_amount(best_action.action_name),
                confidence=best_confidence,
                ev=None,
                notes=notes,
                action_evs={
                    action.action_name: action.total_ev
                    for action in policy.actions
                    if action.total_ev is not None
                },
                range_breakdown={
                    f"seat_{seat}": player_range.total_frequency()
                    for seat, player_range in session_context.player_ranges.items()
                },
            )
        except ValueError as exc:
            return UnsupportedScenarioDecision(
                state_version=observed_state.state_version,
                reason=str(exc),
            )
        except Exception as exc:
            return SafeFallbackDecision(
                state_version=observed_state.state_version,
                error_code="hero_resolver_error",
                notes=str(exc),
            )


def _find_player(observed_state: ObservedTableState, seat_index: int) -> Player | None:
    for player in observed_state.players:
        if player.seat_index == seat_index:
            return player
    return None


def _select_best_action(
    policy: GtoPriorPolicy,
    *,
    action_frequencies: dict[str, float] | None = None,
):
    best_action = policy.actions[0]
    for action in policy.actions[1:]:
        if _get_action_frequency(action, action_frequencies) > _get_action_frequency(
            best_action,
            action_frequencies,
        ):
            best_action = action
    return best_action


def _get_action_frequency(
    action: GtoPriorAction,
    action_frequencies: dict[str, float] | None,
) -> float:
    """读取动作当前用于决策的频率。

    Args:
        action: 待读取动作。
        action_frequencies: 可选的动作频率覆盖字典。

    Returns:
        用于比较的动作频率。
    """

    if action_frequencies is None:
        return float(action.blended_frequency)
    frequency = action_frequencies.get(action.action_name)
    if frequency is None:
        return float(action.blended_frequency)
    return float(frequency)


def _build_prior_only_heuristic_frequencies(
    *,
    policy: GtoPriorPolicy,
    session_context: StrategySessionContext,
) -> tuple[dict[str, float], str | None]:
    """基于未行动对手摘要构建 Hero 启发式动作频率。

    Args:
        policy: Hero 当前节点的先验策略。
        session_context: 当前会话上下文。

    Returns:
        `(action_frequencies, note)`，其中 `action_frequencies` 为归一化后的动作频率。
    """

    normalized_frequencies = _normalize_action_frequencies(policy)
    prior_only_summaries = [
        summary
        for summary in session_context.player_summaries.values()
        if summary.get("status") == "prior_only"
    ]
    if not prior_only_summaries:
        return (normalized_frequencies, None)

    aggressive_actions = [
        action.action_name
        for action in policy.actions
        if _is_aggressive_prior_action(action.action_name, action.action_type)
    ]
    if not aggressive_actions:
        return (normalized_frequencies, None)

    non_aggressive_actions = [
        action.action_name
        for action in policy.actions
        if action.action_name not in aggressive_actions
    ]
    if not non_aggressive_actions:
        return (normalized_frequencies, None)

    aggressive_excess_values: list[float] = []
    call_deficit_values: list[float] = []
    for summary in prior_only_summaries:
        raise_delta_probability = _read_summary_float(
            summary,
            key="raise_delta_probability",
        )
        if raise_delta_probability is not None and raise_delta_probability > 0.0:
            aggressive_excess_values.append(raise_delta_probability)

        gto_call_probability = _read_summary_float(
            summary,
            key="gto_call_probability",
        )
        stats_call_probability = _read_summary_float(
            summary,
            key="stats_call_probability",
        )
        if (
            gto_call_probability is not None
            and stats_call_probability is not None
            and gto_call_probability > stats_call_probability
        ):
            call_deficit_values.append(gto_call_probability - stats_call_probability)

    aggressive_pressure = _average(aggressive_excess_values)
    call_deficit = _average(call_deficit_values)
    net_shift = _clamp(
        0.60 * call_deficit - 0.90 * aggressive_pressure,
        -_HEURISTIC_MAX_SHIFT,
        _HEURISTIC_MAX_SHIFT,
    )
    if abs(net_shift) <= _HEURISTIC_EPSILON:
        return (normalized_frequencies, None)

    current_aggressive_mass = sum(
        normalized_frequencies[action_name] for action_name in aggressive_actions
    )
    current_non_aggressive_mass = 1.0 - current_aggressive_mass
    if (
        current_aggressive_mass <= _HEURISTIC_EPSILON
        or current_non_aggressive_mass <= _HEURISTIC_EPSILON
    ):
        return (normalized_frequencies, None)

    target_aggressive_mass = _clamp(
        current_aggressive_mass + net_shift,
        0.0,
        1.0,
    )
    if abs(target_aggressive_mass - current_aggressive_mass) <= _HEURISTIC_EPSILON:
        return (normalized_frequencies, None)

    adjusted_frequencies = dict(normalized_frequencies)
    aggressive_scale = target_aggressive_mass / current_aggressive_mass
    non_aggressive_scale = (1.0 - target_aggressive_mass) / current_non_aggressive_mass
    for action_name in aggressive_actions:
        adjusted_frequencies[action_name] = (
            normalized_frequencies[action_name] * aggressive_scale
        )
    for action_name in non_aggressive_actions:
        adjusted_frequencies[action_name] = (
            normalized_frequencies[action_name] * non_aggressive_scale
        )

    note = (
        "prior_only_heuristic_applied"
        f"; shift={net_shift:.3f}"
        f"; aggressive_pressure={aggressive_pressure:.3f}"
        f"; call_deficit={call_deficit:.3f}"
    )
    return (adjusted_frequencies, note)


def _normalize_action_frequencies(policy: GtoPriorPolicy) -> dict[str, float]:
    """将先验动作频率归一化为概率分布。

    Args:
        policy: GTO 先验策略。

    Returns:
        动作名到归一化频率的映射。
    """

    frequencies = {
        action.action_name: max(action.blended_frequency, 0.0)
        for action in policy.actions
    }
    total_frequency = sum(frequencies.values())
    if total_frequency <= _HEURISTIC_EPSILON:
        return frequencies
    return {
        action_name: frequency / total_frequency
        for action_name, frequency in frequencies.items()
    }


def _is_aggressive_prior_action(action_name: str, action_type: str | None) -> bool:
    """判断先验动作是否属于激进行动。

    Args:
        action_name: 动作编码。
        action_type: 动作类型。

    Returns:
        是否为激进行动。
    """

    normalized_type = "" if action_type is None else action_type.upper()
    if normalized_type in {"RAISE", "BET", "ALL_IN"}:
        return True
    normalized_name = action_name.upper()
    return normalized_name == "RAI" or normalized_name.startswith("R")


def _read_summary_float(
    summary: dict[str, str | float | int],
    *,
    key: str,
) -> float | None:
    """读取玩家摘要中的浮点值。

    Args:
        summary: 玩家摘要字典。
        key: 目标字段名。

    Returns:
        字段对应的浮点值；缺失或不可解析时返回 None。
    """

    value = summary.get(key)
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    normalized_value = value.strip()
    if not normalized_value:
        return None
    try:
        return float(normalized_value)
    except ValueError:
        return None


def _average(values: list[float]) -> float:
    """计算列表均值。"""

    if not values:
        return 0.0
    return sum(values) / len(values)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """裁剪数值到指定区间。"""

    return max(minimum, min(value, maximum))


def _extract_amount(action_name: str) -> float | None:
    normalized = action_name.upper()
    if normalized == "RAI":
        return 0.0
    if normalized.startswith("R"):
        try:
            return float(normalized[1:])
        except ValueError:
            return 0.0
    return 0.0
