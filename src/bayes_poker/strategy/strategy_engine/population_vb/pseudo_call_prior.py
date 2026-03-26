"""基于 raise EV 构造 pseudo-call prior。"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.range import RANGE_169_LENGTH


def compute_raise_score_from_actions(
    raise_evs: np.ndarray,
    raise_freqs: np.ndarray,
) -> np.ndarray:
    """按 raise 动作频率加权聚合 EV 打分。

    Args:
        raise_evs: 形状为 `[n_raise_actions, 169]` 的 EV 矩阵。
        raise_freqs: 形状为 `[n_raise_actions]` 的动作权重。

    Returns:
        形状为 `[169]` 的 raise 打分向量。
    """

    if raise_evs.size == 0 or raise_freqs.size == 0:
        return np.zeros(RANGE_169_LENGTH, dtype=np.float32)
    if raise_evs.ndim != 2 or raise_evs.shape[1] != RANGE_169_LENGTH:
        msg = (
            "raise_evs 形状非法, "
            f"期望 `[n, {RANGE_169_LENGTH}]`, 实际为 {raise_evs.shape}。"
        )
        raise ValueError(msg)
    if raise_freqs.ndim != 1 or raise_freqs.shape[0] != raise_evs.shape[0]:
        msg = (
            "raise_freqs 形状非法, "
            f"期望 `[n]` 且 n={raise_evs.shape[0]}, 实际为 {raise_freqs.shape}。"
        )
        raise ValueError(msg)

    clipped_weights = np.clip(raise_freqs.astype(np.float64), 1e-8, None)
    normalized_weights = clipped_weights / np.sum(clipped_weights)
    score = np.sum(raise_evs.astype(np.float64) * normalized_weights[:, None], axis=0)
    return score.astype(np.float32)


def _combo_mass_percentile(
    raise_score: np.ndarray,
    combo_weights: np.ndarray,
) -> np.ndarray:
    """计算按组合权重排序后的累计分位。"""

    order = np.argsort(raise_score)
    ordered_weights = combo_weights[order]
    cumulative = np.cumsum(ordered_weights)
    total = float(cumulative[-1]) if cumulative.size > 0 else 0.0
    if total <= 0.0:
        return np.linspace(0.0, 1.0, raise_score.shape[0], dtype=np.float32)
    percentile = np.zeros_like(raise_score, dtype=np.float64)
    percentile[order] = (cumulative - 0.5 * ordered_weights) / total
    return np.clip(percentile, 0.0, 1.0).astype(np.float32)


def build_pseudo_call_prior_from_raise_ev(
    raise_score: np.ndarray,
    combo_weights: np.ndarray,
    empirical_mix_fcr: np.ndarray,
    solver_raise_share: float,
    prior_strength: float = 20.0,
    tau: float = 0.025,
    eps: float = 1e-6,
) -> np.ndarray:
    """从 raise EV 构造 `F/C/R` hand-level 先验。

    Args:
        raise_score: 形状为 `[169]` 的 raise 打分向量。
        combo_weights: 形状为 `[169]` 的组合权重向量。
        empirical_mix_fcr: 经验动作占比 `[F, C, R]`。
        solver_raise_share: solver 的总 raise 占比。
        prior_strength: 对 base mix 的收缩强度。
        tau: 控制分位平滑宽度。
        eps: 数值稳定项。

    Returns:
        形状为 `[169, 3]` 的先验概率矩阵, 列顺序为 `F/C/R`。
    """

    if raise_score.shape != (RANGE_169_LENGTH,):
        msg = (
            "raise_score 形状非法, "
            f"期望 `[{RANGE_169_LENGTH}]`, 实际为 {raise_score.shape}。"
        )
        raise ValueError(msg)
    if combo_weights.shape != (RANGE_169_LENGTH,):
        msg = (
            "combo_weights 形状非法, "
            f"期望 `[{RANGE_169_LENGTH}]`, 实际为 {combo_weights.shape}。"
        )
        raise ValueError(msg)
    if empirical_mix_fcr.shape != (3,):
        msg = (
            "empirical_mix_fcr 形状非法, "
            f"期望 `[3]`, 实际为 {empirical_mix_fcr.shape}。"
        )
        raise ValueError(msg)

    solver_raise_share = float(np.clip(solver_raise_share, 0.0, 1.0))
    base_mix = np.array(
        [1.0 - solver_raise_share, 0.0, solver_raise_share], dtype=np.float64
    )

    empirical = np.clip(empirical_mix_fcr.astype(np.float64), 0.0, None)
    empirical_sum = float(np.sum(empirical))
    if empirical_sum <= 0.0:
        empirical = base_mix.copy()
    else:
        empirical = empirical / empirical_sum

    shrunk_mix = (empirical + prior_strength * base_mix) / (1.0 + prior_strength)
    shrunk_mix = np.clip(shrunk_mix, 0.0, None)
    shrunk_mix_sum = float(np.sum(shrunk_mix))
    if shrunk_mix_sum <= 0.0:
        shrunk_mix = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    else:
        shrunk_mix = shrunk_mix / shrunk_mix_sum

    percentile = _combo_mass_percentile(
        raise_score=raise_score.astype(np.float32),
        combo_weights=np.clip(combo_weights.astype(np.float32), eps, None),
    )
    tau = max(float(tau), eps)

    fold_affinity = np.clip(1.0 - percentile, eps, 1.0)
    raise_affinity = np.clip(percentile, eps, 1.0)
    call_affinity = np.exp(-0.5 * np.square((percentile - 0.5) / tau)).astype(
        np.float64
    )

    fold_component = shrunk_mix[0] * fold_affinity
    call_component = shrunk_mix[1] * call_affinity
    raise_component = shrunk_mix[2] * raise_affinity
    if shrunk_mix[1] <= eps:
        call_component = np.zeros_like(call_component)

    stacked = np.stack(
        [
            fold_component,
            call_component,
            raise_component,
        ],
        axis=1,
    ).astype(np.float64)
    row_sums = np.sum(stacked, axis=1, keepdims=True)
    zero_mask = row_sums[:, 0] <= eps
    if np.any(zero_mask):
        stacked[zero_mask, :] = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        row_sums = np.sum(stacked, axis=1, keepdims=True)
    normalized = stacked / row_sums
    return normalized.astype(np.float32)
