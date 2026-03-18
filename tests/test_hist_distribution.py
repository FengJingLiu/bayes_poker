"""HistDistribution 单元测试。"""

from __future__ import annotations

import math

import pytest

from bayes_poker.player_metrics.hist_distribution import HistDistribution


class TestHistDistributionAddSample:
    def test_add_single_sample_at_midpoint(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.5)
        dist.normalize()
        ev = dist.expected_value()
        assert abs(ev - 0.5) < 0.05, f"期望期望值约为 0.5，实际 {ev}"

    def test_add_sample_shifts_mass_toward_value(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.2)
        dist.normalize()
        ev_low = dist.expected_value()

        dist2 = HistDistribution(100)
        dist2.add_sample(0.8)
        dist2.normalize()
        ev_high = dist2.expected_value()

        assert ev_low < 0.5
        assert ev_high > 0.5


class TestHistDistributionUpdate:
    def test_positive_update_increases_expected_value(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.5)
        dist.normalize()
        ev_before = dist.expected_value()

        dist.update(True)
        ev_after = dist.expected_value()

        assert ev_after > ev_before, "正样本更新应使期望值升高"

    def test_negative_update_decreases_expected_value(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.5)
        dist.normalize()
        ev_before = dist.expected_value()

        dist.update(False)
        ev_after = dist.expected_value()

        assert ev_after < ev_before, "负样本更新应使期望值降低"


class TestHistDistributionNormalize:
    def test_normalize_sums_to_one(self) -> None:
        dist = HistDistribution(50)
        dist.add_sample(0.3)
        dist.add_sample(0.7)
        dist.normalize()
        total = sum(dist._dist)
        assert abs(total - 1.0) < 1e-10

    def test_normalize_zero_distribution_gives_uniform(self) -> None:
        dist = HistDistribution(10)
        dist.normalize()
        for v in dist._dist:
            assert abs(v - 0.1) < 1e-10


class TestHistDistributionFitGaussian:
    def test_fit_gaussian_returns_gaussian_distribution(self) -> None:
        from bayes_poker.player_metrics.gaussian_distribution import GaussianDistribution

        dist = HistDistribution(100)
        dist.add_sample(0.4)
        dist.normalize()
        gauss = dist.fit_gaussian()
        assert isinstance(gauss, GaussianDistribution)
        assert 0.0 <= gauss.mean <= 1.0
        assert gauss.sigma >= 0.0

    def test_fit_gaussian_mean_near_sample(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.3)
        dist.normalize()
        gauss = dist.fit_gaussian()
        assert abs(gauss.mean - 0.3) < 0.1


class TestHistDistributionCopyFrom:
    def test_copy_is_independent(self) -> None:
        original = HistDistribution(20)
        original.add_sample(0.5)
        original.normalize()

        copy = HistDistribution.copy_from(original)
        copy.update(True)

        assert original.expected_value() != copy.expected_value(), "副本更新不应影响原始分布"

    def test_copy_has_same_values(self) -> None:
        original = HistDistribution(20)
        original.add_sample(0.5)
        original.normalize()

        copy = HistDistribution.copy_from(original)
        assert original._dist == copy._dist


class TestHistDistributionStandardDeviation:
    def test_standard_deviation_nonnegative(self) -> None:
        dist = HistDistribution(100)
        dist.add_sample(0.5)
        dist.normalize()
        assert dist.standard_deviation() >= 0.0

    def test_concentrated_distribution_has_small_std(self) -> None:
        dist = HistDistribution(1000)
        for _ in range(50):
            dist.add_sample(0.5)
        dist.normalize()
        std = dist.standard_deviation()
        assert std < 0.1, f"集中分布标准差应较小，实际 {std}"


class TestHistDistributionInvalidInput:
    def test_zero_bins_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="n 必须大于 0"):
            HistDistribution(0)

    def test_negative_bins_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="n 必须大于 0"):
            HistDistribution(-5)
