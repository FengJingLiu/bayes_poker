"""bucket 级局部 MFVB 更新。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import digamma, logsumexp

from bayes_poker.strategy.range import RANGE_169_LENGTH


@dataclass
class LocalVbResult:
    """局部 VB 输出结果。

    Attributes:
        alpha: 后验 Dirichlet 参数, 形状 `[169, 3]`。
        mean: 后验均值, 形状 `[169, 3]`。
        soft_counts: 未暴露样本的软分配计数, 形状 `[169, 3]`。
    """

    alpha: np.ndarray
    mean: np.ndarray
    soft_counts: np.ndarray


def fit_local_bucket_vb(
    *,
    alpha0: np.ndarray,
    exposed_counts: np.ndarray,
    unexposed_by_action: np.ndarray,
    combo_prior: np.ndarray,
    exposure_prob: np.ndarray,
    max_iter: int = 50,
    tol: float = 1e-6,
) -> LocalVbResult:
    """执行单个 bucket 的局部 CAVI 更新。

    Args:
        alpha0: 先验 Dirichlet 参数, 形状 `[169, 3]`。
        exposed_counts: 已暴露计数, 形状 `[169, 3]`。
        unexposed_by_action: 未暴露总量, 形状 `[3]`。
        combo_prior: 到达先验, 形状 `[169]`。
        exposure_prob: 暴露概率矩阵, 形状 `[169, 3]`。
        max_iter: 最大迭代次数。
        tol: 收敛阈值。

    Returns:
        局部 VB 拟合结果。
    """

    if alpha0.shape != (RANGE_169_LENGTH, 3):
        raise ValueError(f"alpha0 形状非法: {alpha0.shape}")
    if exposed_counts.shape != (RANGE_169_LENGTH, 3):
        raise ValueError(f"exposed_counts 形状非法: {exposed_counts.shape}")
    if unexposed_by_action.shape != (3,):
        raise ValueError(f"unexposed_by_action 形状非法: {unexposed_by_action.shape}")
    if combo_prior.shape != (RANGE_169_LENGTH,):
        raise ValueError(f"combo_prior 形状非法: {combo_prior.shape}")
    if exposure_prob.shape != (RANGE_169_LENGTH, 3):
        raise ValueError(f"exposure_prob 形状非法: {exposure_prob.shape}")

    alpha = np.asarray(alpha0, dtype=np.float64) + np.asarray(
        exposed_counts, dtype=np.float64
    )
    combo_prior_safe = np.clip(np.asarray(combo_prior, dtype=np.float64), 1e-12, None)
    unexposed = np.clip(np.asarray(unexposed_by_action, dtype=np.float64), 0.0, None)
    exposure = np.clip(np.asarray(exposure_prob, dtype=np.float64), 0.0, 1.0)
    soft_counts = np.zeros((RANGE_169_LENGTH, 3), dtype=np.float64)

    for _ in range(max_iter):
        expected_log_theta = digamma(alpha) - digamma(
            np.sum(alpha, axis=1, keepdims=True)
        )
        log_gamma = (
            np.log(combo_prior_safe)[:, None]
            + expected_log_theta
            + np.log(np.clip(1.0 - exposure, 1e-12, 1.0))
        )
        log_gamma = log_gamma - logsumexp(log_gamma, axis=0, keepdims=True)
        gamma = np.exp(log_gamma)
        soft_counts = gamma * unexposed[None, :]

        next_alpha = (
            np.asarray(alpha0, dtype=np.float64)
            + np.asarray(exposed_counts, dtype=np.float64)
            + soft_counts
        )
        delta = float(np.max(np.abs(next_alpha - alpha)))
        alpha = next_alpha
        if delta <= tol:
            break

    alpha_sum = np.sum(alpha, axis=1, keepdims=True)
    mean = alpha / np.clip(alpha_sum, 1e-12, None)
    return LocalVbResult(
        alpha=alpha.astype(np.float32),
        mean=mean.astype(np.float32),
        soft_counts=soft_counts.astype(np.float32),
    )
