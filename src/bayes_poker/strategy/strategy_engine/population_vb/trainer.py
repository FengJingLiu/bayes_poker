"""population 阶段 MFVB 训练器。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bayes_poker.strategy.range import RANGE_169_LENGTH

from .contracts import (
    GtoFamilyPrior,
    PopulationBucketObservation,
    PopulationPosteriorBucket,
)
from .dataset import compute_unexposed_by_action
from .exposure_features import build_exposure_features
from .exposure_logit_vb import ExposureLogitVB, LogisticVbPosterior
from .holdcards import combo_weights_169
from .local_vb import LocalVbResult, fit_local_bucket_vb


def build_exposure_probability_matrix(
    *,
    param_index: int,
    raise_score: np.ndarray,
    beta_posterior: LogisticVbPosterior | None,
) -> np.ndarray:
    """构建 `[169, 3]` 暴露概率矩阵。

    Args:
        param_index: 翻前参数索引。
        raise_score: 形状 `[169]` 的 raise 打分。
        beta_posterior: 可选 logistic 后验参数。

    Returns:
        暴露概率矩阵, 列顺序为 `F/C/R`。
    """

    matrix = np.zeros((RANGE_169_LENGTH, 3), dtype=np.float32)
    if raise_score.shape != (RANGE_169_LENGTH,):
        raise ValueError(f"raise_score 形状非法: {raise_score.shape}")
    if beta_posterior is None:
        matrix[:, 1] = 0.5
        matrix[:, 2] = 0.5
        return matrix

    model = ExposureLogitVB()
    for action_family_index in (1, 2):
        features = np.stack(
            [
                build_exposure_features(
                    param_index=param_index,
                    hand_class=hand_class,
                    action_family_index=action_family_index,
                    raise_score=float(raise_score[hand_class]),
                )
                for hand_class in range(RANGE_169_LENGTH)
            ],
            axis=0,
        )
        matrix[:, action_family_index] = model.predict_prob(features, beta_posterior)

    matrix[:, 0] = 0.0
    matrix[:, 1:] = np.clip(matrix[:, 1:], 0.0, 1.0)
    return matrix


@dataclass
class PopulationTrainer:
    """population 后验训练器。"""

    lambda_gto: float = 20.0
    eps: float = 1e-3
    max_outer_iter: int = 8
    max_local_iter: int = 50
    tol: float = 1e-6

    def __post_init__(self) -> None:
        """初始化内部对象。"""

        self._combo_prior = combo_weights_169().astype(np.float32)
        self._combo_prior = self._combo_prior / np.sum(self._combo_prior)
        self._exposure_model = ExposureLogitVB(max_iter=100, tol=self.tol)

    def fit(
        self,
        observations: list[PopulationBucketObservation],
        priors: dict[int, GtoFamilyPrior],
    ) -> list[PopulationPosteriorBucket]:
        """拟合 population bucket 后验。

        Args:
            observations: bucket 观测数据列表。
            priors: `param_index -> GTO prior`。

        Returns:
            后验 bucket 列表。
        """

        if not observations:
            return []

        current_beta: LogisticVbPosterior | None = None
        local_results: dict[tuple[int, int], LocalVbResult] = {}

        for outer_index in range(self.max_outer_iter):
            next_local_results: dict[tuple[int, int], LocalVbResult] = {}
            max_delta = 0.0

            for observation in observations:
                prior = priors.get(observation.param_index)
                prior_probs = (
                    prior.probs_fcr
                    if prior is not None
                    else np.tile(
                        np.array([1.0, 0.0, 0.0], dtype=np.float32),
                        (RANGE_169_LENGTH, 1),
                    )
                )
                raise_score = (
                    prior.raise_score
                    if prior is not None
                    else np.zeros(RANGE_169_LENGTH, dtype=np.float32)
                )
                alpha0 = self.eps + self.lambda_gto * prior_probs
                exposure_prob = build_exposure_probability_matrix(
                    param_index=observation.param_index,
                    raise_score=raise_score,
                    beta_posterior=current_beta,
                )
                local = fit_local_bucket_vb(
                    alpha0=alpha0.astype(np.float32),
                    exposed_counts=observation.exposed_counts.astype(np.float32),
                    unexposed_by_action=compute_unexposed_by_action(observation),
                    combo_prior=self._combo_prior,
                    exposure_prob=exposure_prob,
                    max_iter=self.max_local_iter,
                    tol=self.tol,
                )
                key = (observation.table_type, observation.param_index)
                next_local_results[key] = local
                previous = local_results.get(key)
                if previous is not None:
                    delta = float(np.max(np.abs(local.alpha - previous.alpha)))
                    max_delta = max(max_delta, delta)

            features, success, total = self._build_exposure_training_data(
                observations=observations,
                priors=priors,
                local_results=next_local_results,
            )
            if features.shape[0] > 0:
                current_beta = self._exposure_model.fit(
                    x=features,
                    success=success,
                    total=total,
                    init=current_beta,
                )
            local_results = next_local_results
            if outer_index > 0 and max_delta <= self.tol:
                break

        return self._build_posterior_buckets(
            observations=observations,
            priors=priors,
            local_results=local_results,
        )

    def _build_exposure_training_data(
        self,
        *,
        observations: list[PopulationBucketObservation],
        priors: dict[int, GtoFamilyPrior],
        local_results: dict[tuple[int, int], LocalVbResult],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """构建 logistic 训练数据。"""

        features: list[np.ndarray] = []
        success: list[float] = []
        total: list[float] = []

        for observation in observations:
            key = (observation.table_type, observation.param_index)
            local = local_results.get(key)
            if local is None:
                continue
            prior = priors.get(observation.param_index)
            raise_score = (
                prior.raise_score
                if prior is not None
                else np.zeros(RANGE_169_LENGTH, dtype=np.float32)
            )

            for action_family_index in (1, 2):
                observed = observation.exposed_counts[:, action_family_index]
                latent = local.soft_counts[:, action_family_index]
                total_by_hand = observed + latent
                for hand_class in range(RANGE_169_LENGTH):
                    total_count = float(total_by_hand[hand_class])
                    if total_count <= 0.0:
                        continue
                    features.append(
                        build_exposure_features(
                            param_index=observation.param_index,
                            hand_class=hand_class,
                            action_family_index=action_family_index,
                            raise_score=float(raise_score[hand_class]),
                        )
                    )
                    success.append(float(observed[hand_class]))
                    total.append(total_count)

        if not features:
            return (
                np.zeros((0, 10), dtype=np.float32),
                np.zeros(0, dtype=np.float32),
                np.zeros(0, dtype=np.float32),
            )
        return (
            np.stack(features, axis=0).astype(np.float32),
            np.array(success, dtype=np.float32),
            np.array(total, dtype=np.float32),
        )

    def _build_posterior_buckets(
        self,
        *,
        observations: list[PopulationBucketObservation],
        priors: dict[int, GtoFamilyPrior],
        local_results: dict[tuple[int, int], LocalVbResult],
    ) -> list[PopulationPosteriorBucket]:
        """把局部结果转换为最终输出 bucket。"""

        buckets: list[PopulationPosteriorBucket] = []
        for observation in observations:
            key = (observation.table_type, observation.param_index)
            local = local_results.get(key)
            if local is None:
                continue
            prior = priors.get(observation.param_index)
            prior_kind = prior.prior_kind if prior is not None else "direct_gto"
            buckets.append(
                PopulationPosteriorBucket(
                    table_type=observation.table_type,
                    param_index=observation.param_index,
                    alpha_fcr=local.alpha.astype(np.float32),
                    mean_fcr=local.mean.astype(np.float32),
                    ess_by_hand=np.sum(local.alpha, axis=1).astype(np.float32),
                    prior_kind=prior_kind,
                    exposure_model_meta={
                        "model": "logit_vb",
                        "feature_dim": 10,
                    },
                )
            )
        return buckets
