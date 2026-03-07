"""翻前 solver 节点映射器."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    PreflopDecisionState,
)
from bayes_poker.strategy.preflop_parse.models import PreflopStrategy, StrategyNode
from bayes_poker.table.layout.base import Position as TablePosition

_PREFLOP_ACTION_ORDER_6MAX: tuple[TablePosition, ...] = (
    TablePosition.UTG,
    TablePosition.MP,
    TablePosition.CO,
    TablePosition.BTN,
    TablePosition.SB,
    TablePosition.BB,
)
_PREFLOP_ACTION_ORDER_9MAX: tuple[TablePosition, ...] = (
    TablePosition.UTG,
    TablePosition.UTG1,
    TablePosition.MP,
    TablePosition.MP1,
    TablePosition.HJ,
    TablePosition.CO,
    TablePosition.BTN,
    TablePosition.SB,
    TablePosition.BB,
)
_POSTFLOP_POSITION_ORDER: tuple[TablePosition, ...] = (
    TablePosition.SB,
    TablePosition.BB,
    TablePosition.UTG,
    TablePosition.UTG1,
    TablePosition.MP,
    TablePosition.MP1,
    TablePosition.HJ,
    TablePosition.CO,
    TablePosition.BTN,
)


class SyntheticTemplateKind(str, Enum):
    """结构化 synthetic template 类型."""

    LIMP_FAMILY_LEVEL_3 = "limp_family_level_3"


@dataclass(frozen=True, slots=True)
class MappedSolverContext:
    """映射后的 solver 上下文.

    Attributes:
        matched_level: 命中的回退层级.
        matched_history: 最优候选节点历史.
        distance_score: 最优候选与目标状态的距离.
        candidate_histories: 按距离升序排列的候选历史.
        candidate_distances: 与候选历史一一对应的距离分值.
        price_adjustment_applied: 是否触发最小价格修正.
        price_adjustment_factor: 作用到 solver 先验上的最小价格修正因子.
        synthetic_template_kind: 结构化 synthetic template 类型; 无模板时为 None.
    """

    matched_level: int
    matched_history: str
    distance_score: float
    candidate_histories: tuple[str, ...]
    candidate_distances: tuple[float, ...]
    price_adjustment_applied: bool = False
    price_adjustment_factor: float = 1.0
    synthetic_template_kind: SyntheticTemplateKind | None = None


@dataclass(frozen=True, slots=True)
class _CandidateNodeState:
    """可参与比较的候选节点状态.

    Attributes:
        history_full: 节点完整历史.
        action_family: 节点动作族.
        actor_position: 当前行动位置.
        aggressor_position: 首个激进行动位置.
        call_count: 激进行动后的跟注人数.
        limp_count: 激进行动前的 limp 人数.
        raise_size_bb: 首个激进行动的总尺度.
        is_in_position: 相对 aggressor 是否处于位置优势.
    """

    history_full: str
    action_family: ActionFamily
    actor_position: TablePosition
    aggressor_position: TablePosition | None
    call_count: int
    limp_count: int
    raise_size_bb: float | None
    is_in_position: bool | None


class PreflopNodeMapper:
    """将真实翻前状态映射到最接近的 solver 节点."""

    def __init__(
        self,
        *,
        strategy: PreflopStrategy,
        stack_bb: int,
        max_candidates: int = 2,
    ) -> None:
        """初始化映射器.

        Args:
            strategy: 可查询的翻前策略.
            stack_bb: 使用的筹码深度.
            max_candidates: 返回的候选历史数量上限.
        """

        self._strategy = strategy
        self._stack_bb = stack_bb
        self._max_candidates = max_candidates

    def map_state(self, state: PreflopDecisionState) -> MappedSolverContext:
        """映射真实翻前状态.

        Args:
            state: 待映射的共享决策状态.

        Returns:
            受限最小实现下的 solver 映射结果.
        """

        return self._map_by_distance(state)

    def _map_by_distance(self, state: PreflopDecisionState) -> MappedSolverContext:
        """按可解释距离选择最近的候选节点.

        Args:
            state: 待映射的共享决策状态.

        Returns:
            命中的上下文信息.

        Raises:
            ValueError: 当当前 stack 下没有可映射节点时抛出.
        """

        stack_nodes = self._strategy.nodes_by_stack.get(self._stack_bb, {})
        candidates: list[tuple[float, _CandidateNodeState]] = []

        for node in stack_nodes.values():
            candidate_state = _build_candidate_state(node)
            if candidate_state is None:
                continue
            if candidate_state.action_family != state.action_family:
                continue
            distance = _calculate_distance(state=state, candidate=candidate_state)
            candidates.append((distance, candidate_state))

        if not candidates:
            if state.action_family == ActionFamily.LIMP:
                return _build_synthetic_context(
                    template_kind=SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3,
                )
            raise ValueError("当前 stack 下没有同动作族的 solver 节点.")

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1].history_full.count("-"),
                item[1].history_full,
            )
        )

        selected = candidates[: self._max_candidates]
        best_distance, best_candidate = selected[0]
        price_adjustment_applied, price_adjustment_factor = _apply_price_adjustment(
            actual_size_bb=state.raise_size_bb,
            reference_size_bb=best_candidate.raise_size_bb,
        )

        return MappedSolverContext(
            matched_level=2,
            matched_history=best_candidate.history_full,
            distance_score=best_distance,
            candidate_histories=tuple(
                candidate.history_full for _, candidate in selected
            ),
            candidate_distances=tuple(distance for distance, _ in selected),
            price_adjustment_applied=price_adjustment_applied,
            price_adjustment_factor=price_adjustment_factor,
            synthetic_template_kind=None,
        )


def _build_synthetic_context(
    *,
    template_kind: SyntheticTemplateKind,
) -> MappedSolverContext:
    """构造 synthetic template 回退上下文.

    Args:
        template_kind: 结构化模板类型.

    Returns:
        指向 synthetic template 的最小映射结果.
    """

    return MappedSolverContext(
        matched_level=3,
        matched_history="",
        distance_score=0.0,
        candidate_histories=(),
        candidate_distances=(),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=template_kind,
    )


def _apply_price_adjustment(
    *,
    actual_size_bb: float | None,
    reference_size_bb: float | None,
) -> tuple[bool, float]:
    """计算最小价格修正结果.

    Args:
        actual_size_bb: 真实状态中的加注尺度.
        reference_size_bb: 参考 solver 节点的加注尺度.

    Returns:
        `(是否应用价格修正, 价格修正因子)`.
    """

    if actual_size_bb is None or reference_size_bb is None:
        return (False, 1.0)
    if actual_size_bb <= 0 or reference_size_bb <= 0:
        return (False, 1.0)
    if math.isclose(actual_size_bb, reference_size_bb):
        return (False, 1.0)
    if actual_size_bb > reference_size_bb:
        return (True, 0.75)
    return (True, 1.10)


def _build_candidate_state(node: StrategyNode) -> _CandidateNodeState | None:
    """从策略节点提取最小候选状态.

    Args:
        node: 策略节点.

    Returns:
        可参与距离计算的候选状态; 如果当前节点超出 Task 2 范围则返回 None.
    """

    actor_position = _resolve_position(node.acting_position)
    if actor_position is None:
        return None

    tokens = _split_history(node.history_full)
    action_positions = _resolve_action_positions(
        actor_position=actor_position,
        token_count=len(tokens),
    )
    if action_positions is None:
        return None

    aggressor_position: TablePosition | None = None
    call_count = 0
    limp_count = 0
    raise_size_bb: float | None = None

    for position, token in zip(action_positions, tokens):
        normalized_token = token.upper()
        if normalized_token in {"F", "CHECK", "X"}:
            continue

        if normalized_token == "C":
            if aggressor_position is None:
                limp_count += 1
            else:
                call_count += 1
            continue

        if _is_aggressive_token(normalized_token):
            if aggressor_position is not None:
                return None
            aggressor_position = position
            raise_size_bb = _extract_raise_size(normalized_token)
            continue

        return None

    if aggressor_position is None:
        if limp_count > 0:
            action_family = ActionFamily.LIMP
        else:
            action_family = ActionFamily.OPEN
        is_in_position: bool | None = None
    else:
        if limp_count > 0:
            return None
        action_family = ActionFamily.CALL_VS_OPEN
        is_in_position = _is_in_position(
            actor_position=actor_position,
            aggressor_position=aggressor_position,
        )

    return _CandidateNodeState(
        history_full=node.history_full,
        action_family=action_family,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_size_bb=raise_size_bb,
        is_in_position=is_in_position,
    )


def _split_history(history_full: str) -> tuple[str, ...]:
    """拆分历史字符串.

    Args:
        history_full: 完整历史字符串.

    Returns:
        去空白后的 token 序列.
    """

    if not history_full:
        return ()
    return tuple(token.strip() for token in history_full.split("-") if token.strip())


def _resolve_position(position_name: str) -> TablePosition | None:
    """将字符串位置转换为枚举.

    Args:
        position_name: 位置字符串.

    Returns:
        对应的位置枚举; 如果无法识别则返回 None.
    """

    for position in TablePosition:
        if position.value == position_name:
            return position
    return None


def _resolve_action_positions(
    *,
    actor_position: TablePosition,
    token_count: int,
) -> tuple[TablePosition, ...] | None:
    """解析历史 token 对应的行动位置序列.

    Args:
        actor_position: 当前行动位置.
        token_count: 历史 token 数量.

    Returns:
        与历史一一对应的行动位置序列; 如果无法确定则返回 None.
    """

    for action_order in (_PREFLOP_ACTION_ORDER_6MAX, _PREFLOP_ACTION_ORDER_9MAX):
        if actor_position not in action_order:
            continue
        actor_index = action_order.index(actor_position)
        if actor_index != token_count:
            continue
        return action_order[:actor_index]
    return None


def _is_aggressive_token(token: str) -> bool:
    """判断历史 token 是否表示激进行动.

    Args:
        token: 单个历史 token.

    Returns:
        是否为 raise / jam 类动作.
    """

    return token == "RAI" or (token.startswith("R") and len(token) > 1)


def _extract_raise_size(token: str) -> float | None:
    """从加注 token 中解析尺度.

    Args:
        token: 单个历史 token.

    Returns:
        解析出的总尺度. 无法解析时返回 None.
    """

    if token == "RAI":
        return 1000.0
    if not token.startswith("R") or len(token) <= 1:
        return None
    try:
        return float(token[1:])
    except ValueError:
        return None


def _is_in_position(
    *,
    actor_position: TablePosition,
    aggressor_position: TablePosition,
) -> bool:
    """判断当前行动方相对 aggressor 是否处于位置优势.

    Args:
        actor_position: 当前行动位置.
        aggressor_position: 首个激进行动位置.

    Returns:
        如果 actor 在翻后位置更靠后则返回 True.
    """

    actor_index = _POSTFLOP_POSITION_ORDER.index(actor_position)
    aggressor_index = _POSTFLOP_POSITION_ORDER.index(aggressor_position)
    return actor_index > aggressor_index


def _calculate_distance(
    *,
    state: PreflopDecisionState,
    candidate: _CandidateNodeState,
) -> float:
    """计算真实状态与候选节点的最小可解释距离.

    Args:
        state: 真实共享状态.
        candidate: 候选节点状态.

    Returns:
        距离分值, 越小越接近.
    """

    distance = 0.0
    if state.action_family != candidate.action_family:
        distance += 1000.0

    if state.actor_position != candidate.actor_position:
        distance += 40.0

    if state.aggressor_position != candidate.aggressor_position:
        distance += 30.0

    distance += abs(state.call_count - candidate.call_count) * 20.0
    distance += abs(state.limp_count - candidate.limp_count) * 20.0
    distance += _calculate_raise_size_distance(
        state_raise_size_bb=state.raise_size_bb,
        candidate_raise_size_bb=candidate.raise_size_bb,
    )

    if state.aggressor_position is not None and candidate.aggressor_position is not None:
        state_in_position = _is_in_position(
            actor_position=state.actor_position,
            aggressor_position=state.aggressor_position,
        )
        if state_in_position != candidate.is_in_position:
            distance += 100.0

    return distance


def _calculate_raise_size_distance(
    *,
    state_raise_size_bb: float | None,
    candidate_raise_size_bb: float | None,
) -> float:
    """计算加注尺度距离.

    Args:
        state_raise_size_bb: 真实状态中的加注尺度.
        candidate_raise_size_bb: 候选节点中的加注尺度.

    Returns:
        尺度距离分值, 越小越接近.
    """

    if state_raise_size_bb is None and candidate_raise_size_bb is None:
        return 0.0
    if state_raise_size_bb is None or candidate_raise_size_bb is None:
        return 5.0
    if state_raise_size_bb <= 0 or candidate_raise_size_bb <= 0:
        return 5.0
    return abs(math.log(state_raise_size_bb / candidate_raise_size_bb)) * 10.0


__all__ = [
    "MappedSolverContext",
    "PreflopNodeMapper",
    "SyntheticTemplateKind",
]
