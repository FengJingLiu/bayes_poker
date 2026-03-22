"""EV-ranked belief range 重分配算法.

提供基于 EV 排序的约束式信念重分配纯函数, 供多个策略模块共享使用。
"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.range.mappings import (
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    combos_per_hand,
)
from bayes_poker.strategy.range.models import PreflopRange, extract_by_169_order, scatter_by_169_order

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
    """按目标频率与 EV 排序做约束式信念重分配."""
    strategy_169 = extract_by_169_order(belief_range.strategy)
    evs_169 = extract_by_169_order(belief_range.evs)
    adjusted_strategy = np.clip(strategy_169, 0.0, 1.0)
    weights = np.array([combo_weight(i) for i in range(RANGE_169_LENGTH)])

    current_frequency = np.sum(adjusted_strategy * weights)
    delta = target_frequency - current_frequency
    if abs(delta) <= low_mass_threshold:
        return PreflopRange(strategy=scatter_by_169_order(adjusted_strategy), evs=belief_range.evs.copy())

    if delta > 0.0:
        sorted_indices = np.argsort(evs_169)[::-1]
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
        sorted_indices = np.argsort(evs_169)
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

    return PreflopRange(strategy=scatter_by_169_order(adjusted_strategy), evs=belief_range.evs.copy())
