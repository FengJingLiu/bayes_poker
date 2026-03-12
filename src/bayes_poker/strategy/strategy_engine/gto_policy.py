"""strategy_engine v2 的 GTO 先验构建器。"""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.strategy.range import PreflopRange
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
    source_id: int | None = None
    node_id: int | None = None
    action_type: str | None = None
    bet_size_bb: float | None = None
    is_all_in: bool = False
    next_position: str | None = None
    belief_range: PreflopRange | None = None
    total_ev: float | None = None
    total_combos: float | None = None


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
    ) -> None:
        """初始化 GTO 先验构建器。

        Args:
            repository_adapter: sqlite 读取适配器。
        """

        self._repository_adapter = repository_adapter

    def build_policy(self, mapped_context: MappedNodeContext) -> GtoPriorPolicy:
        """根据最近节点匹配结果构建先验策略。"""

        if mapped_context.synthetic_template_kind is not None:
            return _build_synthetic_template(
                template_kind=mapped_context.synthetic_template_kind,
                price_adjustment_applied=mapped_context.price_adjustment_applied,
                price_adjustment_factor=mapped_context.price_adjustment_factor,
            )
        if mapped_context.matched_node_id is None:
            raise ValueError("映射结果缺少最近节点 ID。")
        if mapped_context.matched_source_id is None:
            raise ValueError("映射结果缺少最近节点 source_id。")

        actions_by_node = self._repository_adapter.load_actions(
            (mapped_context.matched_node_id,),
        )
        action_options = actions_by_node.get(mapped_context.matched_node_id, ())
        if not action_options:
            raise ValueError("映射结果中没有可用的 solver 候选节点。")

        grouped_action_options: dict[str, StrategyActionOption] = {}
        for action_option in action_options:
            if action_option.action_code in grouped_action_options:
                raise ValueError(
                    f"同一节点存在重复动作编码: {action_option.action_code}"
                )
            grouped_action_options[action_option.action_code] = action_option

        action_names = tuple(sorted(grouped_action_options, key=_action_sort_key))
        prior_actions_list: list[GtoPriorAction] = []
        for action_name in action_names:
            action_option = grouped_action_options[action_name]
            prior_actions_list.append(
                GtoPriorAction(
                    action_name=action_name,
                    blended_frequency=action_option.total_frequency,
                    source_id=mapped_context.matched_source_id,
                    node_id=action_option.node_id,
                    action_type=action_option.action_type,
                    bet_size_bb=action_option.bet_size_bb,
                    is_all_in=action_option.is_all_in,
                    next_position=action_option.next_position,
                    belief_range=_clone_preflop_range(action_option.preflop_range),
                    total_ev=action_option.total_ev,
                    total_combos=action_option.total_combos,
                )
            )
        prior_actions = tuple(prior_actions_list)
        return GtoPriorPolicy(
            action_names=action_names,
            actions=prior_actions,
            price_adjustment_applied=mapped_context.price_adjustment_applied,
            price_adjustment_factor=mapped_context.price_adjustment_factor,
        )


def _clone_preflop_range(preflop_range: PreflopRange) -> PreflopRange:
    """复制 `PreflopRange`，避免可变对象引用外泄。"""

    return PreflopRange(
        strategy=list(preflop_range.strategy),
        evs=list(preflop_range.evs),
    )


def _action_sort_key(action_name: str) -> tuple[int, float, str]:
    normalized_name = action_name.upper()
    if normalized_name == "F":
        return (0, 0.0, action_name)
    if normalized_name == "C":
        return (1, 0.0, action_name)
    if normalized_name == "RAI":
        return (2, 100.0, action_name)
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
