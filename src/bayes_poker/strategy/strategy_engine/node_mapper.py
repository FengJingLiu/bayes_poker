"""strategy_engine v2 的最近节点匹配器。"""

from __future__ import annotations

from collections.abc import Sequence
import math
from dataclasses import dataclass
from enum import Enum

from bayes_poker.domain.table import Position
from bayes_poker.strategy.strategy_engine.core_types import NodeContext
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyNodeCandidate,
    StrategyRepositoryAdapter,
)


class SyntheticTemplateKind(str, Enum):
    """支持的 synthetic template 类型。"""

    LIMP_FAMILY_LEVEL_3 = "limp_family_level_3"


@dataclass(frozen=True, slots=True)
class MappedNodeContext:
    """最近节点匹配结果。"""

    matched_level: int
    matched_source_id: int | None
    matched_node_id: int | None
    matched_history: str
    distance_score: float
    candidate_node_ids: tuple[int, ...]
    candidate_source_ids: tuple[int, ...]
    candidate_histories: tuple[str, ...]
    candidate_distances: tuple[float, ...]
    price_adjustment_applied: bool = False
    price_adjustment_factor: float = 1.0
    synthetic_template_kind: SyntheticTemplateKind | None = None


class StrategyNodeMapper:
    """将中性节点上下文映射到最近的 solver 节点。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        source_id: int | Sequence[int],
        stack_bb: int,
        max_candidates: int = 30,
    ) -> None:
        """初始化节点匹配器.

        Args:
            repository_adapter: sqlite 读取适配器.
            source_id: 当前策略源 ID 或 ID 序列.
            stack_bb: 当前使用的筹码深度.
            max_candidates: 返回候选上限.
        """

        self._repository_adapter = repository_adapter
        self._source_ids = _normalize_source_id_selector(source_id)
        self._source_rank_by_id = _build_source_rank_by_id(self._source_ids)
        self._stack_bb = stack_bb
        self._max_candidates = max_candidates

    def map_node_context(
        self,
        node_context: NodeContext,
        *,
        preferred_history_actions: str | None = None,
    ) -> MappedNodeContext:
        """映射中性节点上下文。

        Args:
            node_context: 待映射节点上下文。
            preferred_history_actions: 可选的行动线签名, 例如 `R-C`。

        Returns:
            最近节点匹配结果。
        """

        if _is_limp_family_context(node_context):
            candidates = self._repository_adapter.load_limp_candidates(
                source_id=self._source_ids,
                stack_bb=self._stack_bb,
                actor_position=node_context.actor_position,
                pot_size=node_context.pot_size,
            )
        else:
            candidates = self._repository_adapter.load_candidates(
                source_id=self._source_ids,
                stack_bb=self._stack_bb,
                node_context=node_context,
            )
        if not candidates:
            if _is_limp_family_context(node_context):
                return MappedNodeContext(
                    matched_level=3,
                    matched_source_id=None,
                    matched_node_id=None,
                    matched_history="synthetic:limp_family_level_3",
                    distance_score=0.0,
                    candidate_node_ids=(),
                    candidate_source_ids=(),
                    candidate_histories=(),
                    candidate_distances=(),
                    synthetic_template_kind=SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3,
                )
            raise ValueError("当前 stack 下没有可匹配的 solver 节点。")

        scored_candidates = [
            (
                _calculate_distance(node_context=node_context, candidate=candidate),
                candidate,
            )
            for candidate in candidates
        ]
        scored_candidates.sort(
            key=lambda item: (
                _history_action_mismatch_priority(
                    candidate_history_actions=item[1].history_actions,
                    preferred_history_actions=preferred_history_actions,
                ),
                self._source_rank_by_id.get(item[1].source_id, len(self._source_ids)),
                item[0],
                item[1].history_token_count,
            )
        )
        selected = scored_candidates[: self._max_candidates]
        best_distance, best_candidate = selected[0]
        price_adjustment_applied, price_adjustment_factor = _apply_price_adjustment(
            actual_size_bb=node_context.raise_size_bb,
            reference_size_bb=best_candidate.raise_size_bb,
        )
        return MappedNodeContext(
            matched_level=2,
            matched_source_id=best_candidate.source_id,
            matched_node_id=best_candidate.node_id,
            matched_history=best_candidate.history_full,
            distance_score=best_distance,
            candidate_node_ids=tuple(candidate.node_id for _, candidate in selected),
            candidate_source_ids=tuple(
                candidate.source_id for _, candidate in selected
            ),
            candidate_histories=tuple(
                candidate.history_full for _, candidate in selected
            ),
            candidate_distances=tuple(distance for distance, _ in selected),
            price_adjustment_applied=price_adjustment_applied,
            price_adjustment_factor=price_adjustment_factor,
        )


def _normalize_source_id_selector(source_id: int | Sequence[int]) -> tuple[int, ...]:
    """规范化策略源 ID 选择器.

    Args:
        source_id: 输入的策略源 ID 或 ID 序列.

    Returns:
        规范化后的策略源 ID 元组.

    Raises:
        ValueError: 当传入空序列或包含非 int 值时抛出.
    """

    if isinstance(source_id, int):
        return (source_id,)

    normalized = tuple(source_id)
    if not normalized:
        raise ValueError("source_id 不能为空。")
    if any(not isinstance(current_source_id, int) for current_source_id in normalized):
        raise ValueError("source_id 必须为 int 或 int 序列。")
    return normalized


def _build_source_rank_by_id(source_ids: tuple[int, ...]) -> dict[int, int]:
    """构建策略源优先级索引。

    Args:
        source_ids: 策略源优先级序列。

    Returns:
        `source_id -> rank` 映射, rank 越小优先级越高。
    """

    return {source_id: rank for rank, source_id in enumerate(source_ids)}


def _history_action_mismatch_priority(
    *,
    candidate_history_actions: str,
    preferred_history_actions: str | None,
) -> int:
    """计算行动线匹配优先级。

    Args:
        candidate_history_actions: 候选节点的行动线签名。
        preferred_history_actions: 当前状态推导的目标行动线签名。

    Returns:
        匹配时返回 `0`, 不匹配时返回 `1`。
    """

    if preferred_history_actions is None:
        return 0
    if candidate_history_actions == preferred_history_actions:
        return 0
    return 1


def _apply_price_adjustment(
    *,
    actual_size_bb: float | None,
    reference_size_bb: float | None,
) -> tuple[bool, float]:
    if actual_size_bb is None or reference_size_bb is None:
        return (False, 1.0)
    if actual_size_bb <= 0 or reference_size_bb <= 0:
        return (False, 1.0)
    if math.isclose(actual_size_bb, reference_size_bb):
        return (False, 1.0)
    if actual_size_bb > reference_size_bb:
        return (True, 0.75)
    return (True, 1.10)


def _calculate_distance(
    *,
    node_context: NodeContext,
    candidate: StrategyNodeCandidate,
) -> float:
    distance = 0.0
    if node_context.actor_position.value != candidate.actor_position:
        distance += 40.0
    if _position_value(node_context.aggressor_position) != candidate.aggressor_position:
        distance += 30.0
    distance += abs(node_context.call_count - candidate.call_count) * 20.0
    distance += abs(node_context.limp_count - candidate.limp_count) * 20.0
    distance += abs(node_context.raise_time - candidate.raise_time) * 25.0
    distance += _calculate_pot_size_distance(
        actual_pot_size=node_context.pot_size,
        candidate_pot_size=candidate.pot_size,
    )
    distance += _calculate_raise_size_distance(
        actual_size_bb=node_context.raise_size_bb,
        candidate_size_bb=candidate.raise_size_bb,
    )
    if (
        node_context.aggressor_position is not None
        and candidate.aggressor_position is not None
        and candidate.is_in_position is not None
    ):
        state_is_in_position = _is_in_position(
            actor_position=node_context.actor_position,
            aggressor_position=node_context.aggressor_position,
        )
        if state_is_in_position != candidate.is_in_position:
            distance += 100.0
    return distance


def _calculate_raise_size_distance(
    *,
    actual_size_bb: float | None,
    candidate_size_bb: float | None,
) -> float:
    if actual_size_bb is None and candidate_size_bb is None:
        return 0.0
    if actual_size_bb is None or candidate_size_bb is None:
        return 5.0
    if actual_size_bb <= 0 or candidate_size_bb <= 0:
        return 5.0
    return abs(math.log(actual_size_bb / candidate_size_bb)) * 10.0


def _calculate_pot_size_distance(
    *,
    actual_pot_size: float,
    candidate_pot_size: float,
) -> float:
    if actual_pot_size <= 0 or candidate_pot_size <= 0:
        return 0.0
    return abs(math.log(actual_pot_size / candidate_pot_size)) * 8.0


def _is_in_position(*, actor_position: Position, aggressor_position: Position) -> bool:
    if actor_position == aggressor_position:
        return False
    if {actor_position, aggressor_position} <= {Position.SB, Position.BB}:
        return actor_position == Position.SB and aggressor_position == Position.BB

    order = (
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.MP,
        Position.MP1,
        Position.HJ,
        Position.CO,
        Position.BTN,
    )
    return order.index(actor_position) > order.index(aggressor_position)


def _position_value(position: Position | None) -> str | None:
    return position.value if position is not None else None


def _is_limp_family_context(node_context: NodeContext) -> bool:
    return (
        node_context.raise_time == 0
        and node_context.limp_count > 0
        and node_context.aggressor_position is None
        and node_context.call_count == 0
    )
