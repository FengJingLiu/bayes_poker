"""belief_adjustment 模块单元测试."""

from __future__ import annotations

import pytest

from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH
from bayes_poker.strategy.range.belief_adjustment import (
    adjust_belief_range,
    combo_weight,
)


class TestComboWeight:
    """combo_weight 返回 169 手牌在 1326 总组合中的权重."""

    def test_pair_weight(self) -> None:
        """对子(index=0, '22')权重应为 6/1326."""
        weight = combo_weight(0)
        assert weight == pytest.approx(6 / 1326, rel=1e-6)

    def test_suited_weight(self) -> None:
        """同花(index=2, '32s')权重应为 4/1326."""
        weight = combo_weight(2)
        assert weight == pytest.approx(4 / 1326, rel=1e-6)

    def test_offsuit_weight(self) -> None:
        """非同花(index=1, '32o')权重应为 12/1326."""
        weight = combo_weight(1)
        assert weight == pytest.approx(12 / 1326, rel=1e-6)


class TestAdjustBeliefRange:
    """adjust_belief_range 按目标频率与 EV 排序做约束式信念重分配."""

    def test_target_equals_current_no_change(self) -> None:
        """目标频率与当前频率相同时不调整."""
        belief_range = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        current_frequency = belief_range.total_frequency()

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=current_frequency,
        )

        for index in range(RANGE_169_LENGTH):
            assert result.strategy[index] == pytest.approx(0.5, abs=1e-6)

    def test_increase_target_adds_to_high_ev(self) -> None:
        """目标频率增大时优先向高 EV 手牌增加频率."""
        belief_range = PreflopRange(
            strategy=[0.3] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        current_frequency = belief_range.total_frequency()
        target_frequency = current_frequency + 0.05

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=target_frequency,
        )

        assert result.strategy[168] > 0.3
        assert result.total_frequency() == pytest.approx(target_frequency, abs=1e-4)

    def test_decrease_target_removes_from_low_ev(self) -> None:
        """目标频率减小时优先从低 EV 手牌削减频率."""
        belief_range = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        current_frequency = belief_range.total_frequency()
        target_frequency = current_frequency - 0.05

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=target_frequency,
        )

        assert result.strategy[0] < 0.5
        assert result.total_frequency() == pytest.approx(target_frequency, abs=1e-4)

    def test_all_zeros_stays_zero(self) -> None:
        """全零策略且目标为零时保持不变."""
        belief_range = PreflopRange.zeros()

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=0.0,
        )

        assert all(value == 0.0 for value in result.strategy)

    def test_strategy_clamped_to_zero_one(self) -> None:
        """策略值应始终落在 [0, 1] 范围内."""
        belief_range = PreflopRange(
            strategy=[0.9] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=1.0,
        )

        assert all(0.0 <= value <= 1.0 + 1e-9 for value in result.strategy)

    def test_custom_threshold(self) -> None:
        """可通过 low_mass_threshold 阻止极小幅度调整."""
        belief_range = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        current_frequency = belief_range.total_frequency()

        result = adjust_belief_range(
            belief_range=belief_range,
            target_frequency=current_frequency + 1e-6,
            low_mass_threshold=1e-3,
        )

        for index in range(RANGE_169_LENGTH):
            assert result.strategy[index] == pytest.approx(0.5, abs=1e-6)
