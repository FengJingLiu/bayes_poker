"""翻前策略 sqlite 序列化工具。"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.range import PreflopRange


def encode_preflop_range(preflop_range: PreflopRange) -> tuple[bytes, bytes]:
    """将翻前范围编码为 sqlite 友好的二进制表示。

    Args:
        preflop_range: 待编码的翻前范围对象。

    Returns:
        `(strategy_blob, ev_blob)` 二元组。
    """
    return preflop_range.strategy.astype(np.float32).tobytes(), preflop_range.evs.astype(np.float32).tobytes()


def decode_preflop_range(strategy_blob: bytes, ev_blob: bytes) -> PreflopRange:
    """从 sqlite 二进制字段恢复翻前范围对象。

    Args:
        strategy_blob: 13x13 策略矩阵的二进制表示。
        ev_blob: 13x13 EV 矩阵的二进制表示。

    Returns:
        还原后的 `PreflopRange`。

    Raises:
        ValueError: 当任一 BLOB 长度非法时抛出。
    """
    strategy_array = np.frombuffer(strategy_blob, dtype=np.float32).reshape(13, 13)
    evs_array = np.frombuffer(ev_blob, dtype=np.float32).reshape(13, 13)

    if strategy_array.shape != (13, 13):
        msg = f"strategy 形状必须为 (13, 13)，实际为 {strategy_array.shape}"
        raise ValueError(msg)
    if evs_array.shape != (13, 13):
        msg = f"evs 形状必须为 (13, 13)，实际为 {evs_array.shape}"
        raise ValueError(msg)

    return PreflopRange(strategy=strategy_array, evs=evs_array)

