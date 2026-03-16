"""strategy_engine v2 的 hero GTO resolver。"""

from __future__ import annotations

from collections.abc import Sequence
import math
import random

from bayes_poker.domain.poker import ActionType, Street
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
            action_distribution = _build_action_distribution(policy)
            random_value = self._random.random()
            sampled_action = _sample_action(
                policy=policy,
                action_distribution=action_distribution,
                random_value=random_value,
            )
            return RecommendationDecision(
                state_version=observed_state.state_version,
                action_code=sampled_action.action_name,
                amount=_extract_amount(sampled_action.action_name),
                confidence=action_distribution[sampled_action.action_name],
                ev=None,
                notes=(
                    f"hero_posterior_deferred_v1; matched_history={mapped_context.matched_history}"
                ),
                action_evs={
                    action.action_name: action.total_ev
                    for action in policy.actions
                    if action.total_ev is not None
                },
                action_distribution=action_distribution,
                selected_node_id=mapped_context.matched_node_id,
                selected_source_id=mapped_context.matched_source_id,
                sampling_random=random_value,
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
    """收集 hero 首次行动前已行动且仍在局中的对手座位。

    Args:
        observed_state: 当前观测状态.

    Returns:
        以行动顺序去重后的对手座位元组.
    """

    hero_seat = observed_state.hero_seat
    live_seats = {
        player.seat_index
        for player in observed_state.players
        if player.seat_index != hero_seat and not player.is_folded
    }

    acted_live_seats: list[int] = []
    seen_seats: set[int] = set()
    for action in observed_state.action_history:
        if action.player_index == hero_seat:
            break
        current_seat = action.player_index
        if current_seat not in live_seats or current_seat in seen_seats:
            continue
        acted_live_seats.append(current_seat)
        seen_seats.add(current_seat)
    return tuple(acted_live_seats)


def _build_acted_history_actions(observed_state: ObservedTableState) -> str:
    """构建 hero 首次行动前的行动线签名。

    Args:
        observed_state: 当前观测状态。

    Returns:
        以 `-` 拼接的行动线签名, 例如 `R-C`。
    """

    history_tokens: list[str] = []
    for action in observed_state.action_history:
        if action.player_index == observed_state.hero_seat:
            break
        if action.street != Street.PREFLOP:
            continue
        history_tokens.append(
            _normalize_action_type_to_history_token(action.action_type)
        )
    return "-".join(history_tokens)


def _normalize_action_type_to_history_token(action_type: ActionType) -> str:
    """把动作类型归一为历史签名 token。

    Args:
        action_type: 动作类型。

    Returns:
        归一化后的 token, 取值为 `F`、`C`、`R`。
    """

    if action_type == ActionType.FOLD:
        return "F"
    if action_type in {ActionType.CALL, ActionType.CHECK}:
        return "C"
    return "R"


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
