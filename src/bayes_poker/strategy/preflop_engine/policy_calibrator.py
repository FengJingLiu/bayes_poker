"""翻前策略校准器."""

from __future__ import annotations

import math
from dataclasses import dataclass

from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    combos_per_hand,
)

_EPSILON = 1e-9
_MAX_SHIFT = 40.0
_DEFAULT_TOLERANCE = 1e-6
_DEFAULT_MAX_ITERATIONS = 200


@dataclass(frozen=True, slots=True)
class ActionPolicyAction:
    """单个动作的按手牌策略分布.

    Attributes:
        action_name: 动作名称.
        range: 当前动作对应的 169 维范围.
        rank_scores: 用于保序排序的可选分值向量.
    """

    action_name: str
    range: PreflopRange
    rank_scores: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    """按动作组织的翻前策略.

    Attributes:
        actions: 动作及其对应的范围.
    """

    actions: tuple[ActionPolicyAction, ...]

    def __post_init__(self) -> None:
        """校验最小策略结构."""

        if not self.actions:
            raise ValueError("ActionPolicy 至少需要一个动作.")

        action_names = [action.action_name for action in self.actions]
        if len(set(action_names)) != len(action_names):
            raise ValueError("ActionPolicy 中的动作名称不能重复.")
        for action in self.actions:
            if action.rank_scores is not None and len(action.rank_scores) != RANGE_169_LENGTH:
                raise ValueError("rank_scores 长度必须与 169 手牌空间一致.")

    @property
    def action_names(self) -> tuple[str, ...]:
        """返回动作名称序列.

        Returns:
            按原始顺序排列的动作名称.
        """

        return tuple(action.action_name for action in self.actions)

    def for_action(self, action_name: str) -> PreflopRange:
        """读取指定动作的范围.

        Args:
            action_name: 动作名称.

        Returns:
            对应动作的 169 维范围.

        Raises:
            KeyError: 当动作不存在时抛出.
        """

        for action in self.actions:
            if action.action_name == action_name:
                return action.range
        raise KeyError(f"未知动作: {action_name}")

    def total_frequency(self, action_name: str) -> float:
        """返回指定动作的组合加权总频率.

        Args:
            action_name: 动作名称.

        Returns:
            基于 1326 组合加权的总频率.
        """

        return self.for_action(action_name).total_frequency()

    def rank_for(self, action_name: str) -> tuple[str, ...]:
        """按保序分值返回动作的手牌排序.

        Args:
            action_name: 动作名称.

        Returns:
            按保序分值降序、EV 降序、原始顺序升序排列的手牌序列.
        """

        action = self._get_action(action_name)
        action_range = action.range
        rank_scores = action.rank_scores or tuple(action_range.strategy)
        ranked_indices = sorted(
            range(RANGE_169_LENGTH),
            key=lambda index: (
                -rank_scores[index],
                -action_range.evs[index],
                index,
            ),
        )
        return tuple(RANGE_169_ORDER[index] for index in ranked_indices)

    def _get_action(self, action_name: str) -> ActionPolicyAction:
        """读取指定动作的完整对象.

        Args:
            action_name: 动作名称.

        Returns:
            对应的动作对象.

        Raises:
            KeyError: 当动作不存在时抛出.
        """

        for action in self.actions:
            if action.action_name == action_name:
                return action
        raise KeyError(f"未知动作: {action_name}")


def calibrate_binary_policy(
    policy: ActionPolicy,
    *,
    target_frequency: float,
    action_name: str | None = None,
    tolerance: float = _DEFAULT_TOLERANCE,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> ActionPolicy:
    """校准二元动作策略.

    Args:
        policy: 基础策略.
        target_frequency: 目标动作的组合加权总频率.
        action_name: 需要校准的动作名称; 为 `None` 时自动推断.
        tolerance: 二分搜索终止阈值.
        max_iterations: 最大迭代次数.

    Returns:
        校准后的策略.

    Raises:
        ValueError: 当输入策略不满足二元校准前提时抛出.
    """

    _validate_target_frequency(target_frequency)
    _validate_solver_settings(tolerance=tolerance, max_iterations=max_iterations)

    if len(policy.actions) != 2:
        raise ValueError("二元校准要求策略恰好包含两个动作.")

    _validate_policy_simplex(policy)

    calibrated_action_name = _infer_binary_action_name(policy, action_name)
    other_action_name = next(
        action.action_name
        for action in policy.actions
        if action.action_name != calibrated_action_name
    )

    shift = _solve_logit_shift(
        base_range=policy.for_action(calibrated_action_name),
        target_frequency=target_frequency,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )

    calibrated_target_strategy = [
        _sigmoid(_safe_logit(probability) + shift)
        for probability in policy.for_action(calibrated_action_name).strategy
    ]
    calibrated_other_strategy = [
        1.0 - probability
        for probability in calibrated_target_strategy
    ]

    calibrated_ranges = {
        calibrated_action_name: PreflopRange(
            strategy=calibrated_target_strategy,
            evs=list(policy.for_action(calibrated_action_name).evs),
        ),
        other_action_name: PreflopRange(
            strategy=calibrated_other_strategy,
            evs=list(policy.for_action(other_action_name).evs),
        ),
    }
    return _rebuild_policy(policy=policy, action_ranges=calibrated_ranges)


def calibrate_multinomial_policy(
    policy: ActionPolicy,
    *,
    target_mix: dict[str, float],
    tolerance: float = _DEFAULT_TOLERANCE,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> ActionPolicy:
    """校准多动作混合策略.

    Args:
        policy: 基础策略.
        target_mix: 每个动作的目标总频率.
        tolerance: 迭代终止阈值.
        max_iterations: 最大迭代次数.

    Returns:
        校准后的策略.

    Raises:
        ValueError: 当目标混合或求解参数非法时抛出.
    """

    _validate_solver_settings(tolerance=tolerance, max_iterations=max_iterations)
    _validate_target_mix(policy=policy, target_mix=target_mix)
    _validate_policy_simplex(policy)

    biases = {action_name: 0.0 for action_name in policy.action_names}
    calibrated_policy = policy

    for _ in range(max_iterations):
        calibrated_policy = _apply_softmax_bias(policy=policy, biases=biases)
        max_error = max(
            abs(calibrated_policy.total_frequency(action_name) - target_mix[action_name])
            for action_name in policy.action_names
        )
        if max_error <= tolerance:
            return calibrated_policy

        for action_name in policy.action_names:
            current_frequency = calibrated_policy.total_frequency(action_name)
            target_frequency = target_mix[action_name]
            biases[action_name] = _clamp_bias(
                biases[action_name]
                + math.log(_clamp_probability(target_frequency))
                - math.log(_clamp_probability(current_frequency))
            )

    return _apply_softmax_bias(policy=policy, biases=biases)


def _validate_target_frequency(target_frequency: float) -> None:
    """校验目标频率输入.

    Args:
        target_frequency: 目标总频率.

    Raises:
        ValueError: 当目标频率超出 `[0.0, 1.0]` 时抛出.
    """

    if not 0.0 <= target_frequency <= 1.0:
        raise ValueError("target_frequency 必须位于 [0.0, 1.0] 区间内.")


def _validate_solver_settings(*, tolerance: float, max_iterations: int) -> None:
    """校验求解器配置.

    Args:
        tolerance: 收敛阈值.
        max_iterations: 最大迭代次数.

    Raises:
        ValueError: 当配置非法时抛出.
    """

    if tolerance <= 0.0:
        raise ValueError("tolerance 必须大于 0.")
    if max_iterations <= 0:
        raise ValueError("max_iterations 必须大于 0.")


def _validate_target_mix(
    *,
    policy: ActionPolicy,
    target_mix: dict[str, float],
) -> None:
    """校验多动作目标混合.

    Args:
        policy: 基础策略.
        target_mix: 目标混合频率.

    Raises:
        ValueError: 当动作集合或目标频率非法时抛出.
    """

    policy_action_names = set(policy.action_names)
    target_action_names = set(target_mix)
    if target_action_names != policy_action_names:
        raise ValueError("target_mix 必须与策略动作集合完全一致.")

    total_target_frequency = 0.0
    for action_name, target_frequency in target_mix.items():
        _validate_target_frequency(target_frequency)
        total_target_frequency += target_frequency

    if not math.isclose(total_target_frequency, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("target_mix 的频率总和必须为 1.0.")


def _infer_binary_action_name(
    policy: ActionPolicy,
    action_name: str | None,
) -> str:
    """推断二元校准的目标动作名称.

    Args:
        policy: 基础策略.
        action_name: 可选的显式动作名称.

    Returns:
        需要校准的动作名称.

    Raises:
        ValueError: 当无法可靠推断目标动作时抛出.
    """

    if action_name is not None:
        if action_name not in policy.action_names:
            raise ValueError(f"未知动作: {action_name}")
        return action_name

    non_fold_actions = [
        current_action_name
        for current_action_name in policy.action_names
        if current_action_name.upper() not in {"F", "FOLD"}
    ]
    if len(non_fold_actions) == 1:
        return non_fold_actions[0]

    if len(policy.action_names) == 2:
        return policy.action_names[-1]

    raise ValueError("无法自动推断二元校准的目标动作名称.")


def _validate_policy_simplex(policy: ActionPolicy) -> None:
    """校验每手牌在动作维度上构成概率单纯形.

    Args:
        policy: 待校验的策略.

    Raises:
        ValueError: 当任一手牌的动作概率不在 `[0, 1]` 或总和不接近 1 时抛出.
    """

    for action in policy.actions:
        for probability in action.range.strategy:
            if not 0.0 <= probability <= 1.0:
                raise ValueError("动作概率必须位于 [0.0, 1.0] 区间内.")

    for index in range(RANGE_169_LENGTH):
        probability_sum = sum(
            action.range.strategy[index]
            for action in policy.actions
        )
        if not math.isclose(probability_sum, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError("每手牌在动作维度上的概率总和必须为 1.0.")


def _solve_logit_shift(
    *,
    base_range: PreflopRange,
    target_frequency: float,
    tolerance: float,
    max_iterations: int,
) -> float:
    """求解二元校准所需的全局 logit 偏移.

    Args:
        base_range: 目标动作的基础范围.
        target_frequency: 目标总频率.
        tolerance: 收敛阈值.
        max_iterations: 最大迭代次数.

    Returns:
        使总频率逼近目标值的偏移量.
    """

    lower_bound = -_MAX_SHIFT
    upper_bound = _MAX_SHIFT

    for _ in range(max_iterations):
        middle = (lower_bound + upper_bound) / 2.0
        current_frequency = _binary_total_frequency(base_range=base_range, shift=middle)
        if abs(current_frequency - target_frequency) <= tolerance:
            return middle
        if current_frequency < target_frequency:
            lower_bound = middle
        else:
            upper_bound = middle

    return (lower_bound + upper_bound) / 2.0


def _binary_total_frequency(*, base_range: PreflopRange, shift: float) -> float:
    """计算指定偏移下的二元动作总频率.

    Args:
        base_range: 目标动作的基础范围.
        shift: 当前偏移量.

    Returns:
        对应的组合加权总频率.
    """

    weighted_total = 0.0
    for hand_key, probability in zip(RANGE_169_ORDER, base_range.strategy, strict=True):
        adjusted_probability = _sigmoid(_safe_logit(probability) + shift)
        weighted_total += adjusted_probability * combos_per_hand(hand_key)
    return weighted_total / float(RANGE_1326_LENGTH)


def _apply_softmax_bias(
    *,
    policy: ActionPolicy,
    biases: dict[str, float],
) -> ActionPolicy:
    """对多动作策略施加全局 softmax 偏置.

    Args:
        policy: 基础策略.
        biases: 每个动作的全局偏置.

    Returns:
        偏置后的新策略.
    """

    action_names = policy.action_names
    action_ranges = {
        action_name: [0.0] * RANGE_169_LENGTH
        for action_name in action_names
    }

    for index in range(RANGE_169_LENGTH):
        logits = [
            math.log(
                _clamp_probability(policy.for_action(action_name).strategy[index])
            ) + biases[action_name]
            for action_name in action_names
        ]
        max_logit = max(logits)
        exponentials = [math.exp(logit - max_logit) for logit in logits]
        denominator = sum(exponentials)

        for action_name, exponential in zip(action_names, exponentials, strict=True):
            action_ranges[action_name][index] = exponential / denominator

    rebuilt_action_ranges = {
        action_name: PreflopRange(
            strategy=strategy,
            evs=list(policy.for_action(action_name).evs),
        )
        for action_name, strategy in action_ranges.items()
    }
    return _rebuild_policy(policy=policy, action_ranges=rebuilt_action_ranges)


def _rebuild_policy(
    *,
    policy: ActionPolicy,
    action_ranges: dict[str, PreflopRange],
) -> ActionPolicy:
    """按原动作顺序重建策略对象.

    Args:
        policy: 参考策略.
        action_ranges: 新的动作范围映射.

    Returns:
        重建后的策略.
    """

    return ActionPolicy(
        actions=tuple(
            ActionPolicyAction(
                action_name=action.action_name,
                range=action_ranges[action.action_name],
                rank_scores=action.rank_scores or tuple(action.range.strategy),
            )
            for action in policy.actions
        )
    )


def _safe_logit(probability: float) -> float:
    """对概率执行带钳位的 logit 变换.

    Args:
        probability: 原始概率.

    Returns:
        钳位后的 logit 值.
    """

    clipped_probability = _clamp_probability(probability)
    return math.log(clipped_probability / (1.0 - clipped_probability))


def _sigmoid(value: float) -> float:
    """返回数值的 sigmoid 结果.

    Args:
        value: 输入值.

    Returns:
        对应的 sigmoid 概率.
    """

    return 1.0 / (1.0 + math.exp(-value))


def _clamp_probability(probability: float) -> float:
    """将概率钳位到安全区间.

    Args:
        probability: 原始概率.

    Returns:
        钳位后的概率.
    """

    return min(max(probability, _EPSILON), 1.0 - _EPSILON)


def _clamp_bias(bias: float) -> float:
    """限制 softmax 偏置的数值范围.

    Args:
        bias: 原始偏置值.

    Returns:
        钳位后的偏置值.
    """

    return min(max(bias, -_MAX_SHIFT), _MAX_SHIFT)


__all__ = [
    "ActionPolicy",
    "ActionPolicyAction",
    "calibrate_binary_policy",
    "calibrate_multinomial_policy",
]
