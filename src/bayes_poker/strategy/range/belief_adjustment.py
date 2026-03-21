"""EV-ranked belief range 重分配算法.

提供基于 EV 排序的约束式信念重分配纯函数, 供多个策略模块共享使用。
"""

from __future__ import annotations

from bayes_poker.strategy.range.mappings import (
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    combos_per_hand,
)
from bayes_poker.strategy.range.models import PreflopRange

_DEFAULT_LOW_MASS_THRESHOLD = 1e-9


def combo_weight(index: int) -> float:
    """返回某 169 手牌在总频率中的组合权重.

    Args:
        index: 169 维手牌索引。

    Returns:
        该手牌的组合数占 1326 总组合数的比例。
    """
    return combos_per_hand(RANGE_169_ORDER[index]) / RANGE_1326_LENGTH


def adjust_belief_range(
    *,
    belief_range: PreflopRange,
    target_frequency: float,
    low_mass_threshold: float = _DEFAULT_LOW_MASS_THRESHOLD,
) -> PreflopRange:
    """按目标频率与 EV 排序做约束式信念重分配.

    当目标频率高于当前频率时, 优先向高 EV 手牌增加质量。
    当目标频率低于当前频率时, 优先从低 EV 手牌移除质量。

    Args:
        belief_range: 原始 belief range, 使用 169 维策略向量表示。
        target_frequency: 目标总频率。
        low_mass_threshold: 极小质量阈值, 差异不超过该值时直接返回。

    Returns:
        调整后的新 PreflopRange。
    """
    adjusted_strategy = [min(max(value, 0.0), 1.0) for value in belief_range.strategy]
    evs = list(belief_range.evs)
    weights = [combo_weight(index) for index in range(RANGE_169_LENGTH)]

    current_frequency = sum(
        probability * weight
        for probability, weight in zip(adjusted_strategy, weights, strict=True)
    )
    delta = target_frequency - current_frequency
    if abs(delta) <= low_mass_threshold:
        return PreflopRange(strategy=adjusted_strategy, evs=evs)

    if delta > 0.0:
        sorted_indices = sorted(
            range(RANGE_169_LENGTH),
            key=lambda index: evs[index],
            reverse=True,
        )
        for index in sorted_indices:
            if delta <= low_mass_threshold:
                break
            weight = weights[index]
            if weight <= 0.0:
                continue
            available_probability = 1.0 - adjusted_strategy[index]
            if available_probability <= low_mass_threshold:
                continue
            max_mass = available_probability * weight
            mass_to_add = min(delta, max_mass)
            adjusted_strategy[index] += mass_to_add / weight
            delta -= mass_to_add
    else:
        remaining = -delta
        sorted_indices = sorted(
            range(RANGE_169_LENGTH),
            key=lambda index: evs[index],
        )
        for index in sorted_indices:
            if remaining <= low_mass_threshold:
                break
            weight = weights[index]
            if weight <= 0.0:
                continue
            available_probability = adjusted_strategy[index]
            if available_probability <= low_mass_threshold:
                continue
            max_mass = available_probability * weight
            mass_to_remove = min(remaining, max_mass)
            adjusted_strategy[index] -= mass_to_remove / weight
            remaining -= mass_to_remove

    return PreflopRange(strategy=adjusted_strategy, evs=evs)
