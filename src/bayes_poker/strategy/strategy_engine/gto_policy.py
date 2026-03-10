"""strategy_engine v2 的 GTO 先验构建器。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from bayes_poker.strategy.strategy_engine.node_mapper import (
    MappedNodeContext,
    SyntheticTemplateKind,
)
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyActionOption,
    StrategyRepositoryAdapter,
)


@dataclass(frozen=True, slots=True)
class GtoPriorAction:
    """聚合后的单个 GTO 先验动作。"""

    action_name: str
    blended_frequency: float


@dataclass(frozen=True, slots=True)
class GtoPriorPolicy:
    """聚合后的 GTO 先验策略。"""

    action_names: tuple[str, ...]
    actions: tuple[GtoPriorAction, ...]
    price_adjustment_applied: bool = False
    price_adjustment_factor: float = 1.0
    synthetic_template_kind: SyntheticTemplateKind | None = None


class GtoPriorBuilder:
    """根据最近节点匹配结果构建 GTO 先验。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        distance_tau: float = 1.0,
    ) -> None:
        """初始化 GTO 先验构建器。

        Args:
            repository_adapter: sqlite 读取适配器。
            distance_tau: 距离衰减温度。
        """

        if distance_tau <= 0:
            raise ValueError("distance_tau 必须大于 0。")
        self._repository_adapter = repository_adapter
        self._distance_tau = distance_tau

    def build_policy(self, mapped_context: MappedNodeContext) -> GtoPriorPolicy:
        """根据最近节点匹配结果构建先验策略。"""

        if mapped_context.synthetic_template_kind is not None:
            return _build_synthetic_template(
                template_kind=mapped_context.synthetic_template_kind,
                price_adjustment_applied=mapped_context.price_adjustment_applied,
                price_adjustment_factor=mapped_context.price_adjustment_factor,
            )
        if len(mapped_context.candidate_node_ids) != len(
            mapped_context.candidate_distances
        ):
            raise ValueError("候选节点与距离数量不一致。")

        actions_by_node = self._repository_adapter.load_actions(
            mapped_context.candidate_node_ids,
        )
        action_weights: dict[str, float] = {}
        for node_id, distance in zip(
            mapped_context.candidate_node_ids,
            mapped_context.candidate_distances,
            strict=True,
        ):
            actions = actions_by_node.get(node_id, ())
            if not actions:
                continue
            candidate_weight = math.exp(-distance / self._distance_tau)
            for action in actions:
                action_weights[action.action_code] = action_weights.get(
                    action.action_code,
                    0.0,
                ) + candidate_weight * _action_frequency(action)
        if not action_weights:
            raise ValueError("映射结果中没有可用的 solver 候选节点。")

        action_names = tuple(sorted(action_weights, key=_action_sort_key))
        actions = tuple(
            GtoPriorAction(
                action_name=action_name,
                blended_frequency=action_weights[action_name],
            )
            for action_name in action_names
        )
        return GtoPriorPolicy(
            action_names=action_names,
            actions=actions,
            price_adjustment_applied=mapped_context.price_adjustment_applied,
            price_adjustment_factor=mapped_context.price_adjustment_factor,
        )


def _action_frequency(action: StrategyActionOption) -> float:
    return action.total_frequency


def _action_sort_key(action_name: str) -> tuple[int, float, str]:
    normalized_name = action_name.upper()
    if normalized_name == "F":
        return (0, 0.0, action_name)
    if normalized_name == "C":
        return (1, 0.0, action_name)
    if normalized_name == "RAI":
        return (2, 1000.0, action_name)
    if normalized_name.startswith("R"):
        try:
            return (2, float(normalized_name[1:]), action_name)
        except ValueError:
            return (3, 0.0, action_name)
    return (3, 0.0, action_name)


def _build_synthetic_template(
    *,
    template_kind: SyntheticTemplateKind,
    price_adjustment_applied: bool,
    price_adjustment_factor: float,
) -> GtoPriorPolicy:
    if template_kind is not SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3:
        raise ValueError(f"未知的 synthetic template: {template_kind}")
    actions = (
        GtoPriorAction(action_name="F", blended_frequency=0.25),
        GtoPriorAction(action_name="C", blended_frequency=0.50),
        GtoPriorAction(action_name="R4", blended_frequency=0.25),
    )
    return GtoPriorPolicy(
        action_names=tuple(action.action_name for action in actions),
        actions=actions,
        price_adjustment_applied=price_adjustment_applied,
        price_adjustment_factor=price_adjustment_factor,
        synthetic_template_kind=template_kind,
    )
