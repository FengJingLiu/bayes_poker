"""GaussianDistribution 单元测试。"""

from __future__ import annotations

import math

import pytest

from bayes_poker.player_metrics.gaussian_distribution import GaussianDistribution


class TestGaussianDistributionFromCounts:
    def test_from_counts_correct_mean(self) -> None:
        g = GaussianDistribution.from_counts(10, 100)
        assert abs(g.mean - 0.1) < 1e-10

    def test_from_counts_zero_total_returns_defaults(self) -> None:
        g = GaussianDistribution.from_counts(0, 0)
        assert g.mean == 0.0
        assert g.sigma == 0.5

    def test_from_counts_sigma_binomial(self) -> None:
        p, n = 0.5, 400
        g = GaussianDistribution.from_counts(int(p * n), n)
        expected_sigma = math.sqrt(p * (1 - p) / n)
        assert abs(g.sigma - expected_sigma) < 1e-10


class TestGaussianDistributionScale:
    def test_scale_doubles_mean_and_sigma(self) -> None:
        g = GaussianDistribution(mean=0.3, sigma=0.1)
        scaled = g.scale(2.0)
        assert abs(scaled.mean - 0.6) < 1e-10
        assert abs(scaled.sigma - 0.2) < 1e-10

    def test_scale_zero_gives_zero(self) -> None:
        g = GaussianDistribution(mean=0.5, sigma=0.2)
        scaled = g.scale(0.0)
        assert scaled.mean == 0.0
        assert scaled.sigma == 0.0

    def test_original_unchanged_after_scale(self) -> None:
        g = GaussianDistribution(mean=0.3, sigma=0.1)
        _ = g.scale(3.0)
        assert g.mean == 0.3
        assert g.sigma == 0.1


class TestGaussianDistributionAbsSub:
    def test_abs_sub_mean_is_absolute_difference(self) -> None:
        g1 = GaussianDistribution(mean=0.6, sigma=0.1)
        g2 = GaussianDistribution(mean=0.2, sigma=0.1)
        result = g1.abs_sub(g2)
        assert abs(result.mean - 0.4) < 1e-10

    def test_abs_sub_sigma_is_quadrature_sum(self) -> None:
        g1 = GaussianDistribution(mean=0.6, sigma=0.3)
        g2 = GaussianDistribution(mean=0.2, sigma=0.4)
        result = g1.abs_sub(g2)
        expected_sigma = math.sqrt(0.3**2 + 0.4**2)
        assert abs(result.sigma - expected_sigma) < 1e-10

    def test_abs_sub_nonnegative_mean(self) -> None:
        g1 = GaussianDistribution(mean=0.1, sigma=0.05)
        g2 = GaussianDistribution(mean=0.9, sigma=0.05)
        result = g1.abs_sub(g2)
        assert result.mean >= 0.0


class TestGaussianDistributionAdd:
    def test_add_means(self) -> None:
        g1 = GaussianDistribution(mean=0.3, sigma=0.1)
        g2 = GaussianDistribution(mean=0.2, sigma=0.1)
        result = g1.add(g2)
        assert abs(result.mean - 0.5) < 1e-10

    def test_add_sigma_quadrature(self) -> None:
        g1 = GaussianDistribution(mean=0.3, sigma=0.3)
        g2 = GaussianDistribution(mean=0.2, sigma=0.4)
        result = g1.add(g2)
        expected = math.sqrt(0.3**2 + 0.4**2)
        assert abs(result.sigma - expected) < 1e-10


class TestGaussianDistributionImmutability:
    def test_frozen_dataclass_cannot_be_mutated(self) -> None:
        g = GaussianDistribution(mean=0.5, sigma=0.1)
        with pytest.raises((AttributeError, TypeError)):
            g.mean = 0.9  # type: ignore[misc]
