"""strategy_engine v2 的动作频率校准器。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from bayes_poker.strategy.range import RANGE_169_LENGTH, PreflopRange

_EPSILON = 1e-9
_MAX_SHIFT = 40.0
_DEFAULT_TOLERANCE = 1e-6
_DEFAULT_MAX_ITERATIONS = 200


@dataclass(frozen=True, slots=True)
class ActionPolicyAction:
    """单个动作的 169 维策略分布。"""

    action_name: str
    range: PreflopRange
    rank_scores: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    """按动作组织的策略视图。"""

    actions: tuple[ActionPolicyAction, ...]

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError("ActionPolicy 至少需要一个动作。")
        action_names = [action.action_name for action in self.actions]
        if len(set(action_names)) != len(action_names):
            raise ValueError("ActionPolicy 中的动作名称不能重复。")
        for action in self.actions:
            if action.range.strategy.shape != (13, 13):
                raise ValueError("策略形状必须为 (13, 13)。")

    @property
    def action_names(self) -> tuple[str, ...]:
        """返回动作名称序列。"""

        return tuple(action.action_name for action in self.actions)

    def for_action(self, action_name: str) -> PreflopRange:
        """读取指定动作的范围。"""

        for action in self.actions:
            if action.action_name == action_name:
                return action.range
        raise KeyError(f"未知动作: {action_name}")

    def total_frequency(self, action_name: str) -> float:
        """读取指定动作的组合加权总频率。"""

        return self.for_action(action_name).total_frequency()


def calibrate_multinomial_policy(
    policy: ActionPolicy,
    *,
    target_mix: dict[str, float],
    tolerance: float = _DEFAULT_TOLERANCE,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> ActionPolicy:
    """校准多动作混合策略。"""

    _validate_solver_settings(tolerance=tolerance, max_iterations=max_iterations)
    if set(target_mix) != set(policy.action_names):
        raise ValueError("target_mix 必须覆盖策略中的全部动作。")

    biases = {action_name: 0.0 for action_name in policy.action_names}
    calibrated = policy
    for _ in range(max_iterations):
        calibrated = _apply_softmax_bias(policy=policy, biases=biases)
        max_error = max(
            abs(calibrated.total_frequency(action_name) - target_mix[action_name])
            for action_name in policy.action_names
        )
        if max_error <= tolerance:
            return calibrated
        for action_name in policy.action_names:
            current_frequency = calibrated.total_frequency(action_name)
            biases[action_name] += math.log(
                _clamp_probability(target_mix[action_name])
            ) - math.log(_clamp_probability(current_frequency))
            biases[action_name] = _clamp_bias(biases[action_name])
    return calibrated


def redistribute_aggressive_mass(
    policy: ActionPolicy,
    *,
    size_weights: dict[str, float] | None,
) -> ActionPolicy:
    """按尺寸证据在激进行动之间重新分配总质量。"""

    if not size_weights:
        return policy
    aggressive_action_names = tuple(
        action_name
        for action_name in policy.action_names
        if action_name.upper().startswith("R")
    )
    if len(aggressive_action_names) <= 1:
        return policy

    normalized_weights = {
        action_name: max(size_weights.get(action_name, 0.0), 0.0)
        for action_name in aggressive_action_names
    }
    total_weight = sum(normalized_weights.values())
    if total_weight <= 0:
        return policy

    total_aggressive_strategy = [0.0] * RANGE_169_LENGTH
    total_aggressive_evs = [0.0] * RANGE_169_LENGTH
    for action_name in aggressive_action_names:
        action_range = policy.for_action(action_name)
        total_aggressive_strategy = [
            current + value
            for current, value in zip(
                total_aggressive_strategy, action_range.strategy, strict=True
            )
        ]
        total_aggressive_evs = [
            max(current, value)
            for current, value in zip(
                total_aggressive_evs, action_range.evs, strict=True
            )
        ]

    rebuilt_actions: list[ActionPolicyAction] = []
    for action in policy.actions:
        if action.action_name in aggressive_action_names:
            weight = normalized_weights[action.action_name] / total_weight
            rebuilt_actions.append(
                ActionPolicyAction(
                    action_name=action.action_name,
                    range=PreflopRange(
                        strategy=[
                            value * weight for value in total_aggressive_strategy
                        ],
                        evs=list(total_aggressive_evs),
                    ),
                    rank_scores=action.rank_scores,
                )
            )
        else:
            rebuilt_actions.append(action)
    return ActionPolicy(actions=tuple(rebuilt_actions))


def _replace_action_range(
    action: ActionPolicyAction, strategy: np.ndarray, evs: np.ndarray
) -> ActionPolicyAction:
    return ActionPolicyAction(
        action_name=action.action_name,
        range=PreflopRange(strategy=strategy, evs=evs),
        rank_scores=action.rank_scores,
    )


def _apply_softmax_bias(
    *,
    policy: ActionPolicy,
    biases: dict[str, float],
) -> ActionPolicy:
    adjusted_actions: list[ActionPolicyAction] = []
    for action in policy.actions:
        strategy, evs = action.range.to_list()
        adjusted_actions.append(
            ActionPolicyAction(
                action_name=action.action_name,
                range=PreflopRange.from_list(strategy, evs),
                rank_scores=action.rank_scores,
            )
        )

    for index in range(RANGE_169_LENGTH):
        logits = [
            _safe_logit(action.range[index]) + biases[action.action_name]
            for action in adjusted_actions
        ]
        max_logit = max(logits)
        exp_values = [math.exp(value - max_logit) for value in logits]
        total_exp = sum(exp_values)
        for action, exp_value in zip(adjusted_actions, exp_values, strict=True):
            action.range[index] = exp_value / total_exp
    return ActionPolicy(actions=tuple(adjusted_actions))


def _safe_logit(probability: float) -> float:
    probability = _clamp_probability(probability)
    return math.log(probability / (1.0 - probability))


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _clamp_probability(value: float) -> float:
    return min(max(value, _EPSILON), 1.0 - _EPSILON)


def _clamp_bias(value: float) -> float:
    return min(max(value, -_MAX_SHIFT), _MAX_SHIFT)


def _validate_target_frequency(target_frequency: float) -> None:
    if not 0.0 <= target_frequency <= 1.0:
        raise ValueError("target_frequency 必须位于 [0, 1] 区间。")


def _validate_solver_settings(*, tolerance: float, max_iterations: int) -> None:
    if tolerance <= 0:
        raise ValueError("tolerance 必须大于 0。")
    if max_iterations <= 0:
        raise ValueError("max_iterations 必须大于 0。")
