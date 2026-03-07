"""翻前策略 sqlite 序列化测试。"""

from __future__ import annotations

import pytest

from bayes_poker.strategy.preflop_parse.serialization import (
    decode_preflop_range,
    encode_preflop_range,
)
from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
)


def test_encode_and_decode_preflop_range_round_trip() -> None:
    """验证 PreflopRange 可以稳定往返序列化。"""

    preflop_range = PreflopRange(
        strategy=[0.25] * RANGE_169_LENGTH,
        evs=[1.5] * RANGE_169_LENGTH,
    )

    strategy_blob, ev_blob = encode_preflop_range(preflop_range)
    decoded = decode_preflop_range(strategy_blob, ev_blob)

    assert decoded.strategy[0] == pytest.approx(0.25, abs=1e-6)
    assert decoded.strategy[-1] == pytest.approx(0.25, abs=1e-6)
    assert decoded.evs[0] == pytest.approx(1.5, abs=1e-6)
    assert decoded.evs[-1] == pytest.approx(1.5, abs=1e-6)


def test_decode_preflop_range_rejects_invalid_blob_length() -> None:
    """验证错误长度的 BLOB 会被显式拒绝。"""

    with pytest.raises(ValueError):
        decode_preflop_range(b"bad", b"bad")
