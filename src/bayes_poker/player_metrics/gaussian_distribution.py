"""不可变高斯分布数据结构。

移植自 G5.Logic (C#) 的 GaussianDistribution.cs。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["GaussianDistribution"]


@dataclass(frozen=True, slots=True)
class GaussianDistribution:
    """不可变高斯分布（均值 + 标准差）。

    所有运算均返回新实例，不修改自身。
    """

    mean: float
    sigma: float

    @classmethod
    def from_counts(cls, positive: int, total: int) -> GaussianDistribution:
        """从正/总计数构建（频率估计 + 二项式标准差）。

        Args:
            positive: 正样本数，不能为负且不能大于 total。
            total: 总样本数，不能为负。

        Returns:
            对应的高斯分布估计。

        Raises:
            ValueError: 当 positive 或 total 为负，或 positive > total 时。
        """
        if positive < 0 or total < 0:
            raise ValueError("positive 和 total 不能为负数")
        if positive > total:
            raise ValueError("positive 不能大于 total")
        if total <= 0:
            return cls(mean=0.0, sigma=0.5)
        m = positive / total
        s = math.sqrt(m * (1.0 - m) / total)
        return cls(mean=m, sigma=s)

    def scale(self, factor: float) -> GaussianDistribution:
        """缩放均值和标准差。

        Args:
            factor: 缩放因子。

        Returns:
            缩放后的新分布。
        """
        return GaussianDistribution(mean=self.mean * factor, sigma=self.sigma * factor)

    def add(self, other: GaussianDistribution) -> GaussianDistribution:
        """两个独立高斯分布相加。

        Args:
            other: 另一个分布。

        Returns:
            均值相加、标准差按均方根合并的新分布。
        """
        return GaussianDistribution(
            mean=self.mean + other.mean,
            sigma=math.sqrt(self.sigma**2 + other.sigma**2),
        )

    def sub(self, other: GaussianDistribution) -> GaussianDistribution:
        """两个独立高斯分布相减（均值差，sigma 按均方根合并）。

        Args:
            other: 另一个分布。

        Returns:
            均值相减、标准差按均方根合并的新分布。
        """
        return GaussianDistribution(
            mean=self.mean - other.mean,
            sigma=math.sqrt(self.sigma**2 + other.sigma**2),
        )

    def abs_sub(self, other: GaussianDistribution) -> GaussianDistribution:
        """两个独立高斯分布均值之差的绝对值（sigma 按均方根合并）。

        Args:
            other: 另一个分布。

        Returns:
            |self.mean - other.mean| 与合并 sigma 构成的新分布。
        """
        return GaussianDistribution(
            mean=abs(self.mean - other.mean),
            sigma=math.sqrt(self.sigma**2 + other.sigma**2),
        )

    def __str__(self) -> str:
        return f"{self.mean:.4f} ± {self.sigma:.4f}"
