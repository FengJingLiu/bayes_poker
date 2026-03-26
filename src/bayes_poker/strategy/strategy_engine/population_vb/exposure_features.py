"""曝光模型特征构建。"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.range import RANGE_169_LENGTH


def build_exposure_features(
    *,
    param_index: int,
    hand_class: int,
    action_family_index: int,
    raise_score: float,
) -> np.ndarray:
    """构建 `(param, hand, action)` 的曝光模型特征。

    Args:
        param_index: 翻前参数索引。
        hand_class: 0-168 的 hand class 索引。
        action_family_index: 动作族索引, 仅支持 `1=C` 与 `2=R`。
        raise_score: 当前 hand class 的 raise 打分。

    Returns:
        固定维度的特征向量。

    Raises:
        ValueError: 当输入索引超出范围时抛出。
    """

    if hand_class < 0 or hand_class >= RANGE_169_LENGTH:
        msg = f"hand_class 超出范围: {hand_class}"
        raise ValueError(msg)
    if action_family_index not in (1, 2):
        msg = f"action_family_index 仅支持 C/R 两类, 当前值为 {action_family_index}。"
        raise ValueError(msg)

    hand_percentile = hand_class / float(RANGE_169_LENGTH - 1)
    centered_hand = hand_percentile - 0.5
    action_is_call = 1.0 if action_family_index == 1 else 0.0
    action_is_raise = 1.0 if action_family_index == 2 else 0.0
    param_scaled = param_index / 200.0
    raise_score = float(raise_score)

    return np.array(
        [
            1.0,
            action_is_call,
            action_is_raise,
            param_scaled,
            hand_percentile,
            centered_hand,
            raise_score,
            raise_score * raise_score,
            action_is_call * raise_score,
            action_is_raise * raise_score,
        ],
        dtype=np.float32,
    )
