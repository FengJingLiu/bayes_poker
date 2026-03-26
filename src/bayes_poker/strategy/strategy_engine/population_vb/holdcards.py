"""holdcard 映射与组合权重工具。"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    combos_per_hand,
    get_range_1326_to_169,
)

_RANGE_1326_TO_169 = np.array(get_range_1326_to_169(), dtype=np.int16)
_COMBO_WEIGHTS_169 = np.array(
    [combos_per_hand(hand_key) for hand_key in RANGE_169_ORDER],
    dtype=np.float32,
)


def combo_weights_169() -> np.ndarray:
    """返回 169 hand class 的组合数权重。

    Returns:
        169 维组合权重向量, 元素取值为 4/6/12。
    """

    return _COMBO_WEIGHTS_169.copy()


def holdcard_to_hand_class_169(holdcard_index: int) -> int:
    """把 1326 组合索引转换为 169 hand class 索引。

    Args:
        holdcard_index: 0-1325 的组合索引。

    Returns:
        0-168 的 hand class 索引。

    Raises:
        ValueError: 当索引超出 `[0, 1325]` 时抛出。
    """

    if holdcard_index < 0 or holdcard_index >= RANGE_1326_LENGTH:
        msg = (
            f"holdcard_index 超出范围: {holdcard_index}, "
            f"期望区间为 [0, {RANGE_1326_LENGTH - 1}]。"
        )
        raise ValueError(msg)
    mapped = int(_RANGE_1326_TO_169[holdcard_index])
    if mapped < 0 or mapped >= RANGE_169_LENGTH:
        msg = f"映射结果非法: holdcard_index={holdcard_index}, mapped={mapped}"
        raise ValueError(msg)
    return mapped
