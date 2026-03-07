"""翻前策略 sqlite 序列化工具。"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
)

_FLOAT32_VECTOR_STRUCT = struct.Struct(f"<{RANGE_169_LENGTH}f")
_EXPECTED_BLOB_LENGTH = _FLOAT32_VECTOR_STRUCT.size


def _encode_float32_vector(values: Sequence[float]) -> bytes:
    """将浮点向量编码为 little-endian float32 BLOB。

    Args:
        values: 待编码的浮点向量。

    Returns:
        编码后的二进制 BLOB。

    Raises:
        ValueError: 当向量长度不是 169 时抛出。
    """

    if len(values) != RANGE_169_LENGTH:
        msg = f"向量长度必须为 {RANGE_169_LENGTH}，实际为 {len(values)}"
        raise ValueError(msg)
    return _FLOAT32_VECTOR_STRUCT.pack(*values)


def _decode_float32_vector(blob: bytes) -> list[float]:
    """将 little-endian float32 BLOB 解码为浮点向量。

    Args:
        blob: 待解码的二进制 BLOB。

    Returns:
        解码后的浮点向量。

    Raises:
        ValueError: 当 BLOB 长度不符合 169 维 float32 向量时抛出。
    """

    if len(blob) != _EXPECTED_BLOB_LENGTH:
        msg = (
            f"BLOB 长度必须为 {_EXPECTED_BLOB_LENGTH} 字节，"
            f"实际为 {len(blob)} 字节"
        )
        raise ValueError(msg)
    return list(_FLOAT32_VECTOR_STRUCT.unpack(blob))


def encode_preflop_range(preflop_range: PreflopRange) -> tuple[bytes, bytes]:
    """将翻前范围编码为 sqlite 友好的二进制表示。

    Args:
        preflop_range: 待编码的翻前范围对象。

    Returns:
        `(strategy_blob, ev_blob)` 二元组。
    """

    return (
        _encode_float32_vector(preflop_range.strategy),
        _encode_float32_vector(preflop_range.evs),
    )


def decode_preflop_range(strategy_blob: bytes, ev_blob: bytes) -> PreflopRange:
    """从 sqlite 二进制字段恢复翻前范围对象。

    Args:
        strategy_blob: 169 维策略频率的二进制表示。
        ev_blob: 169 维 EV 的二进制表示。

    Returns:
        还原后的 `PreflopRange`。

    Raises:
        ValueError: 当任一 BLOB 长度非法时抛出。
    """

    return PreflopRange(
        strategy=_decode_float32_vector(strategy_blob),
        evs=_decode_float32_vector(ev_blob),
    )
