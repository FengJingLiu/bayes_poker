"""翻前 solver 先验候选读取器."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bayes_poker.strategy.preflop_engine.mapper import MappedSolverContext
from bayes_poker.strategy.preflop_parse.models import PreflopStrategy, StrategyAction


@dataclass(frozen=True, slots=True)
class SolverPriorAction:
    """聚合后的单个动作先验.

    Attributes:
        action_name: 动作名称.
        blended_frequency: 候选节点加权后的动作频率.
    """

    action_name: str
    blended_frequency: float


@dataclass(frozen=True, slots=True)
class SolverPriorPolicy:
    """聚合后的 solver 先验策略.

    Attributes:
        action_names: 聚合后的动作名称序列.
        actions: 每个动作的聚合结果.
    """

    action_names: tuple[str, ...]
    actions: tuple[SolverPriorAction, ...]


class SolverPriorBuilder:
    """根据映射结果读取并合成 solver 先验."""

    def __init__(
        self,
        *,
        strategy: PreflopStrategy,
        stack_bb: int,
        distance_tau: float = 1.0,
    ) -> None:
        """初始化先验构建器.

        Args:
            strategy: 可查询的翻前策略.
            stack_bb: 使用的筹码深度.
            distance_tau: 距离衰减温度参数.

        Raises:
            ValueError: 当温度参数不为正时抛出.
        """

        if distance_tau <= 0:
            raise ValueError("distance_tau 必须大于 0.")

        self._strategy = strategy
        self._stack_bb = stack_bb
        self._distance_tau = distance_tau

    def build_policy(self, context: MappedSolverContext) -> SolverPriorPolicy:
        """根据映射结果合成先验策略.

        当前最小实现使用 `candidate_distances` 做指数衰减权重.

        Args:
            context: 节点映射结果.

        Returns:
            聚合后的先验策略.

        Raises:
            ValueError: 当上下文中的候选节点都不可用, 或距离信息不完整时抛出.
        """

        if context.synthetic_template_name is not None:
            return _build_synthetic_template(context.synthetic_template_name)

        if len(context.candidate_histories) != len(context.candidate_distances):
            raise ValueError("候选历史与距离数量不一致.")

        action_weights: dict[str, float] = {}

        for history, distance in zip(
            context.candidate_histories,
            context.candidate_distances,
            strict=True,
        ):
            node = self._strategy.get_node(self._stack_bb, history)
            if node is None:
                continue

            candidate_weight = math.exp(-distance / self._distance_tau)
            for action in node.actions:
                action_weights[action.action_code] = action_weights.get(
                    action.action_code,
                    0.0,
                ) + candidate_weight * _action_frequency(action)

        if not action_weights:
            raise ValueError("映射结果中没有可用的 solver 候选节点.")

        action_names = tuple(sorted(action_weights, key=_action_sort_key))
        actions = tuple(
            SolverPriorAction(
                action_name=action_name,
                blended_frequency=_apply_price_adjustment(
                    action_name=action_name,
                    blended_frequency=action_weights[action_name],
                    price_adjustment_applied=context.price_adjustment_applied,
                    price_adjustment_factor=context.price_adjustment_factor,
                ),
            )
            for action_name in action_names
        )
        return SolverPriorPolicy(
            action_names=action_names,
            actions=actions,
        )


def _action_frequency(action: StrategyAction) -> float:
    """读取动作频率.

    Args:
        action: 单个策略动作.

    Returns:
        当前动作的总体频率.
    """

    return action.total_frequency


def _action_sort_key(action_name: str) -> tuple[int, float, str]:
    """返回动作排序键.

    Args:
        action_name: 动作名称.

    Returns:
        用于稳定排序的键.
    """

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


def _apply_price_adjustment(
    *,
    action_name: str,
    blended_frequency: float,
    price_adjustment_applied: bool,
    price_adjustment_factor: float,
) -> float:
    """将最小价格修正应用到动作频率.

    Args:
        action_name: 动作名称.
        blended_frequency: 原始聚合频率.
        price_adjustment_applied: 是否触发价格修正.
        price_adjustment_factor: 价格修正因子.

    Returns:
        应用价格修正后的动作频率.
    """

    if not price_adjustment_applied:
        return blended_frequency
    if not _is_aggressive_action_name(action_name):
        return blended_frequency
    return blended_frequency * price_adjustment_factor


def _is_aggressive_action_name(action_name: str) -> bool:
    """判断动作名是否为激进行动.

    Args:
        action_name: 动作名称.

    Returns:
        如果动作属于 raise / jam 类则返回 True.
    """

    normalized_name = action_name.upper()
    return normalized_name == "RAI" or normalized_name.startswith("R")


def _build_synthetic_template(template_name: str) -> SolverPriorPolicy:
    """构造 synthetic template 对应的最小先验策略.

    Args:
        template_name: 模板名称.

    Returns:
        synthetic template 对应的先验策略.

    Raises:
        ValueError: 当模板名称未知时抛出.
    """

    if template_name != "limp_family_level_3":
        raise ValueError(f"未知的 synthetic template: {template_name}")

    actions = (
        SolverPriorAction(action_name="F", blended_frequency=0.25),
        SolverPriorAction(action_name="C", blended_frequency=0.50),
        SolverPriorAction(action_name="R4", blended_frequency=0.25),
    )
    return SolverPriorPolicy(
        action_names=tuple(action.action_name for action in actions),
        actions=actions,
    )


__all__ = [
    "SolverPriorAction",
    "SolverPriorBuilder",
    "SolverPriorPolicy",
]
