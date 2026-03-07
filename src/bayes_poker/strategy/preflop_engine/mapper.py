"""翻前 solver 节点映射器。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from bayes_poker.storage.preflop_strategy_repository import (
    PreflopStrategyRepository,
    SolverNodeRecord,
)
from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    PreflopDecisionState,
)
from bayes_poker.table.layout.base import Position as TablePosition


class SyntheticTemplateKind(str, Enum):
    """结构化 synthetic template 类型。"""

    LIMP_FAMILY_LEVEL_3 = "limp_family_level_3"


@dataclass(frozen=True, slots=True)
class MappedSolverContext:
    """映射后的 solver 上下文。"""

    matched_level: int
    matched_node_id: int | None
    matched_history: str
    distance_score: float
    candidate_node_ids: tuple[int, ...]
    candidate_histories: tuple[str, ...]
    candidate_distances: tuple[float, ...]
    price_adjustment_applied: bool = False
    price_adjustment_factor: float = 1.0
    synthetic_template_kind: SyntheticTemplateKind | None = None


class PreflopNodeMapper:
    """将真实翻前状态映射到最接近的 solver 节点。"""

    def __init__(
        self,
        *,
        repository: PreflopStrategyRepository,
        source_id: int,
        stack_bb: int,
        max_candidates: int = 2,
    ) -> None:
        """初始化映射器。

        Args:
            repository: sqlite 仓库。
            source_id: 当前策略源 ID。
            stack_bb: 使用的筹码深度。
            max_candidates: 返回候选数量上限。
        """

        self._repository = repository
        self._source_id = source_id
        self._stack_bb = stack_bb
        self._max_candidates = max_candidates

    def map_state(self, state: PreflopDecisionState) -> MappedSolverContext:
        """映射真实翻前状态。

        Args:
            state: 待映射的共享决策状态。

        Returns:
            命中的 solver 上下文。
        """

        return self._map_by_distance(state)

    def _map_by_distance(self, state: PreflopDecisionState) -> MappedSolverContext:
        """按可解释距离选择最近候选。"""

        candidates = self._repository.list_candidates(
            source_id=self._source_id,
            stack_bb=self._stack_bb,
            action_family=state.action_family,
            actor_position=state.actor_position,
        )
        if not candidates:
            if state.action_family == ActionFamily.LIMP:
                return _build_synthetic_context(
                    template_kind=SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3,
                )
            raise ValueError("当前 stack 下没有同动作族的 solver 节点.")

        scored_candidates = [
            (_calculate_distance(state=state, candidate=candidate), candidate)
            for candidate in candidates
        ]
        scored_candidates.sort(
            key=lambda item: (
                item[0],
                item[1].history_full.count("-"),
                item[1].history_full,
            )
        )

        selected = scored_candidates[: self._max_candidates]
        best_distance, best_candidate = selected[0]
        price_adjustment_applied, price_adjustment_factor = _apply_price_adjustment(
            actual_size_bb=state.raise_size_bb,
            reference_size_bb=best_candidate.raise_size_bb,
        )

        return MappedSolverContext(
            matched_level=2,
            matched_node_id=best_candidate.node_id,
            matched_history=best_candidate.history_full,
            distance_score=best_distance,
            candidate_node_ids=tuple(candidate.node_id for _, candidate in selected),
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
    """构造 synthetic template 回退上下文。"""

    return MappedSolverContext(
        matched_level=3,
        matched_node_id=None,
        matched_history="",
        distance_score=0.0,
        candidate_node_ids=(),
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
    """计算最小价格修正结果。"""

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
    state: PreflopDecisionState,
    candidate: SolverNodeRecord,
) -> float:
    """计算真实状态与候选节点的可解释距离。"""

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
        state_is_in_position = _is_in_position(
            actor_position=state.actor_position,
            aggressor_position=state.aggressor_position,
        )
        if (
            candidate.is_in_position is not None
            and state_is_in_position != candidate.is_in_position
        ):
            distance += 100.0

    return distance


def _calculate_raise_size_distance(
    *,
    state_raise_size_bb: float | None,
    candidate_raise_size_bb: float | None,
) -> float:
    """计算加注尺度距离。"""

    if state_raise_size_bb is None and candidate_raise_size_bb is None:
        return 0.0
    if state_raise_size_bb is None or candidate_raise_size_bb is None:
        return 5.0
    if state_raise_size_bb <= 0 or candidate_raise_size_bb <= 0:
        return 5.0
    return abs(math.log(state_raise_size_bb / candidate_raise_size_bb)) * 10.0


def _is_in_position(
    *,
    actor_position: TablePosition,
    aggressor_position: TablePosition,
) -> bool:
    """判断当前行动方相对 aggressor 是否处于位置优势。"""

    postflop_position_order: tuple[TablePosition, ...] = (
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
    actor_index = postflop_position_order.index(actor_position)
    aggressor_index = postflop_position_order.index(aggressor_position)
    return actor_index > aggressor_index


__all__ = [
    "MappedSolverContext",
    "PreflopNodeMapper",
    "SyntheticTemplateKind",
]
