"""Gauss 核平滑直方图分布，支持贝叶斯更新和高斯拟合。

移植自 G5.Logic (C#) 的 PriorDistribution.cs::HistDistribution。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gaussian_distribution import GaussianDistribution

__all__ = ["HistDistribution"]

_SAMPLE_SIGMA = 0.03


def _gauss(x: float, x0: float, sigma: float) -> float:
    """计算单点高斯核密度值。"""
    a = 1.0 / (sigma * math.sqrt(2 * math.pi))
    return a * math.exp(-0.5 * ((x - x0) / sigma) ** 2)


class HistDistribution:
    """Gauss 核平滑直方图分布。

    内部维护等宽分桶的概率质量数组，每个分桶宽度为 1/n。
    桶 i 的中心坐标为 (i + 0.5) / n，覆盖 [0, 1) 范围。
    """

    __slots__ = ("_dist",)

    def __init__(self, n: int) -> None:
        """初始化 n 个等宽分桶，初始质量为 0。

        Args:
            n: 分桶数量，构造后固定不变，必须大于 0。

        Raises:
            ValueError: 当 n <= 0 时。
        """
        if n <= 0:
            raise ValueError("n 必须大于 0")
        self._dist: list[float] = [0.0] * n

    @classmethod
    def copy_from(cls, other: HistDistribution) -> HistDistribution:
        """深拷贝另一个 HistDistribution。

        Args:
            other: 源分布。

        Returns:
            与 other 内容相同的独立副本。
        """
        inst = cls.__new__(cls)
        inst._dist = list(other._dist)
        return inst

    def __len__(self) -> int:
        return len(self._dist)

    def add_sample(self, value: float) -> None:
        """向直方图叠加一个 Gauss 核（σ=0.03）。

        仅更新 [value ± 3σ] 范围内的分桶，超出 [0,1) 边界的自动截断。

        Args:
            value: 样本值，应在 [0, 1) 范围内。
        """
        n = len(self._dist)
        step = 1.0 / n
        left = max(0, int((value - 3 * _SAMPLE_SIGMA) * n))
        right = min(n - 1, int((value + 3 * _SAMPLE_SIGMA) * n))
        for i in range(left, right + 1):
            x = (i + 0.5) * step
            self._dist[i] += _gauss(x, value, _SAMPLE_SIGMA)

    def update(self, positive: bool) -> None:
        """贝叶斯似然乘法更新，然后归一化。

        正样本（positive=True）：每桶质量乘以该桶中心坐标 x，
        偏向高概率区间的桶。
        负样本（positive=False）：每桶质量乘以 (1 - x)，
        偏向低概率区间的桶。

        Args:
            positive: True 表示正样本（行动发生），False 表示负样本（未发生）。
        """
        n = len(self._dist)
        step = 1.0 / n
        for i in range(n):
            x = (i + 0.5) * step
            self._dist[i] *= x if positive else (1.0 - x)
        self.normalize()

    def normalize(self) -> None:
        """归一化分布，使所有分桶质量之和为 1。

        若总质量接近零，则重置为均匀分布。
        """
        s = sum(self._dist)
        n = len(self._dist)
        if s > 1e-15:
            self._dist = [v / s for v in self._dist]
        else:
            self._dist = [1.0 / n] * n

    def expected_value(self) -> float:
        """计算分布的期望值（加权均值）。

        Returns:
            期望值，范围约为 [0, 1]。
        """
        n = len(self._dist)
        step = 1.0 / n
        return sum(self._dist[i] * (i + 0.5) * step for i in range(n))

    def standard_deviation(self) -> float:
        """计算分布的标准差。

        Returns:
            标准差，非负数。
        """
        exp = self.expected_value()
        n = len(self._dist)
        step = 1.0 / n
        variance = sum(self._dist[i] * ((i + 0.5) * step - exp) ** 2 for i in range(n))
        return math.sqrt(variance)

    def fit_gaussian(self) -> GaussianDistribution:
        """将直方图拟合为高斯分布（均值 + 标准差）。

        Returns:
            拟合得到的 GaussianDistribution。
        """
        from .gaussian_distribution import GaussianDistribution

        return GaussianDistribution(mean=self.expected_value(), sigma=self.standard_deviation())

    def difference_scalar(self, val2: float, val1: float) -> float:
        """标量差异度：用本分布的 4σ 归一化两个标量之差。

        Args:
            val2: 第一个标量值。
            val1: 第二个标量值。

        Returns:
            归一化差异度，值越小表示越相似。
        """
        sigma = self.standard_deviation()
        if sigma == 0.0:
            return 0.0
        return abs(val2 - val1) / (4.0 * sigma)

    def difference_gaussian(
        self,
        val2: GaussianDistribution,
        val1: GaussianDistribution,
    ) -> GaussianDistribution:
        """用本分布的 4σ 归一化两个 GaussianDistribution 之差。

        结果均值为 |val2.mean - val1.mean| / (4σ)，
        结果 sigma 为合并不确定度 / (4σ)。

        Args:
            val2: 第一个高斯分布。
            val1: 第二个高斯分布。

        Returns:
            归一化后的差分高斯分布。
        """
        sigma = self.standard_deviation()
        if sigma == 0.0:
            from .gaussian_distribution import GaussianDistribution

            return GaussianDistribution(mean=0.0, sigma=0.0)
        return val2.abs_sub(val1).scale(1.0 / (4.0 * sigma))
