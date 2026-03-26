"""曝光概率的 Logistic 变分近似实现。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class LogisticVbPosterior:
    """Logistic 参数后验。

    Attributes:
        mean: 后验均值向量, 形状 `[D]`。
        cov: 后验协方差矩阵, 形状 `[D, D]`。
    """

    mean: np.ndarray
    cov: np.ndarray


class ExposureLogitVB:
    """带高斯先验的二项 Logistic 近似求解器。"""

    def __init__(
        self,
        prior_var: float = 4.0,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> None:
        """初始化模型。

        Args:
            prior_var: 高斯先验方差。
            max_iter: 最大迭代次数。
            tol: 迭代收敛阈值。
        """

        self._prior_var = float(prior_var)
        self._max_iter = int(max_iter)
        self._tol = float(tol)

    def fit(
        self,
        x: np.ndarray,
        success: np.ndarray,
        total: np.ndarray,
        init: LogisticVbPosterior | None = None,
    ) -> LogisticVbPosterior:
        """拟合带二项观测的 Logistic 模型。

        Args:
            x: 设计矩阵, 形状 `[J, D]`。
            success: 每行成功数, 形状 `[J]`。
            total: 每行总数, 形状 `[J]`。
            init: 可选初始化后验。

        Returns:
            近似后验参数。
        """

        if x.ndim != 2:
            raise ValueError(f"x 维度非法: {x.shape}")
        if success.shape != (x.shape[0],):
            raise ValueError(f"success 形状非法: {success.shape}, 期望 {(x.shape[0],)}")
        if total.shape != (x.shape[0],):
            raise ValueError(f"total 形状非法: {total.shape}, 期望 {(x.shape[0],)}")
        if x.shape[0] == 0:
            dim = x.shape[1]
            return LogisticVbPosterior(
                mean=np.zeros(dim, dtype=np.float32),
                cov=np.eye(dim, dtype=np.float32) * self._prior_var,
            )

        design = np.asarray(x, dtype=np.float64)
        success_f = np.clip(np.asarray(success, dtype=np.float64), 0.0, None)
        total_f = np.clip(np.asarray(total, dtype=np.float64), 0.0, None)
        total_f = np.maximum(total_f, success_f)

        dim = design.shape[1]
        beta = (
            np.asarray(init.mean, dtype=np.float64).copy()
            if init is not None
            else np.zeros(dim, dtype=np.float64)
        )
        prior_precision = np.eye(dim, dtype=np.float64) / max(self._prior_var, 1e-8)
        hessian = prior_precision.copy()

        for _ in range(self._max_iter):
            logits = design @ beta
            probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
            weights = total_f * probs * (1.0 - probs)
            weighted_x = design * weights[:, None]
            hessian = design.T @ weighted_x + prior_precision
            gradient = design.T @ (success_f - total_f * probs) - prior_precision @ beta
            try:
                delta = np.linalg.solve(hessian, gradient)
            except np.linalg.LinAlgError:
                delta = np.linalg.pinv(hessian) @ gradient
            beta = beta + delta
            if np.max(np.abs(delta)) <= self._tol:
                break

        try:
            cov = np.linalg.inv(hessian)
        except np.linalg.LinAlgError:
            cov = np.linalg.pinv(hessian)
        return LogisticVbPosterior(
            mean=beta.astype(np.float32),
            cov=cov.astype(np.float32),
        )

    def predict_prob(
        self,
        x: np.ndarray,
        posterior: LogisticVbPosterior,
    ) -> np.ndarray:
        """预测曝光概率。

        Args:
            x: 设计矩阵, 形状 `[J, D]`。
            posterior: 后验参数。

        Returns:
            形状 `[J]` 的概率向量。
        """

        logits = np.asarray(x, dtype=np.float64) @ np.asarray(
            posterior.mean, dtype=np.float64
        )
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
        return probs.astype(np.float32)
