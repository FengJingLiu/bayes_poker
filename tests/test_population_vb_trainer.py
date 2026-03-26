"""population_vb 训练核心测试。"""

from __future__ import annotations

import numpy as np

from bayes_poker.strategy.strategy_engine.population_vb.contracts import (
    GtoFamilyPrior,
    PopulationBucketObservation,
)
from bayes_poker.strategy.strategy_engine.population_vb.exposure_logit_vb import (
    ExposureLogitVB,
)
from bayes_poker.strategy.strategy_engine.population_vb.holdcards import (
    combo_weights_169,
)
from bayes_poker.strategy.strategy_engine.population_vb.local_vb import (
    fit_local_bucket_vb,
)
from bayes_poker.strategy.strategy_engine.population_vb.trainer import (
    PopulationTrainer,
    build_exposure_probability_matrix,
)


def _make_prior(
    param_index: int,
    probs_fcr: np.ndarray,
    prior_kind: str,
) -> GtoFamilyPrior:
    """构造测试用先验。

    Args:
        param_index: 翻前参数索引。
        probs_fcr: 形状 `[169, 3]` 的先验概率。
        prior_kind: 先验类型字符串。

    Returns:
        `GtoFamilyPrior` 实例。
    """

    return GtoFamilyPrior(
        table_type=6,
        param_index=param_index,
        probs_fcr=probs_fcr.astype(np.float32),
        raise_score=np.linspace(-1.0, 1.0, 169, dtype=np.float32),
        prior_kind=prior_kind,  # type: ignore[arg-type]
    )


def test_local_vb_alpha_positive_and_row_normalized() -> None:
    """local VB 的 alpha 应为正且 mean 行归一化。"""
    alpha0 = np.full((169, 3), 0.5, dtype=np.float32)
    exposed_counts = np.zeros((169, 3), dtype=np.float32)
    exposed_counts[10, 0] = 2.0
    exposed_counts[80, 1] = 4.0
    exposed_counts[120, 2] = 3.0
    unexposed_by_action = np.array([50.0, 30.0, 20.0], dtype=np.float32)
    combo_prior = combo_weights_169().astype(np.float32)
    combo_prior = combo_prior / combo_prior.sum()
    exposure_prob = np.zeros((169, 3), dtype=np.float32)

    result = fit_local_bucket_vb(
        alpha0=alpha0,
        exposed_counts=exposed_counts,
        unexposed_by_action=unexposed_by_action,
        combo_prior=combo_prior,
        exposure_prob=exposure_prob,
    )

    assert np.all(result.alpha > 0.0)
    assert np.allclose(result.mean.sum(axis=1), 1.0, atol=1e-6)
    assert np.allclose(result.soft_counts.sum(axis=0), unexposed_by_action, atol=1e-4)


def test_fold_exposure_probability_is_zero() -> None:
    """曝光模型应强制 fold 通道概率为 0。"""
    matrix = build_exposure_probability_matrix(
        param_index=30,
        raise_score=np.linspace(-2.0, 2.0, 169, dtype=np.float32),
        beta_posterior=None,
    )
    assert matrix.shape == (169, 3)
    assert np.allclose(matrix[:, 0], 0.0)
    assert np.all((matrix[:, 1] >= 0.0) & (matrix[:, 1] <= 1.0))
    assert np.all((matrix[:, 2] >= 0.0) & (matrix[:, 2] <= 1.0))


def test_logit_vb_converges_on_synthetic_binomial_data() -> None:
    """logit VB 在合成二项数据上应学到可用概率。"""
    rng = np.random.default_rng(42)
    x = rng.normal(size=(300, 3)).astype(np.float32)
    true_beta = np.array([0.35, -1.10, 0.90], dtype=np.float32)
    logits = x @ true_beta
    true_prob = 1.0 / (1.0 + np.exp(-logits))
    total = np.full(300, 20.0, dtype=np.float32)
    success = rng.binomial(total.astype(np.int32), true_prob).astype(np.float32)

    model = ExposureLogitVB(prior_var=4.0, max_iter=200, tol=1e-7)
    posterior = model.fit(x=x, success=success, total=total)
    pred_prob = model.predict_prob(x, posterior)

    mae = float(np.mean(np.abs(pred_prob - true_prob)))
    corr = float(np.corrcoef(pred_prob, true_prob)[0, 1])
    assert mae < 0.15
    assert corr > 0.80


def test_population_trainer_keeps_gto_prior_when_no_data() -> None:
    """无观测数据时后验应接近 GTO 先验。"""
    prior_probs = np.zeros((169, 3), dtype=np.float32)
    prior_probs[:, 0] = 0.7
    prior_probs[:, 1] = 0.2
    prior_probs[:, 2] = 0.1
    priors = {30: _make_prior(30, prior_probs, "direct_gto")}
    observation = PopulationBucketObservation(
        table_type=6,
        param_index=30,
        action_totals=np.zeros(3, dtype=np.float32),
        exposed_counts=np.zeros((169, 3), dtype=np.float32),
    )
    trainer = PopulationTrainer(max_outer_iter=2, max_local_iter=20, tol=1e-7)
    buckets = trainer.fit(observations=[observation], priors=priors)

    assert len(buckets) == 1
    bucket = buckets[0]
    assert np.allclose(bucket.mean_fcr, prior_probs, atol=2e-2)


def test_population_trainer_moves_away_from_gto_when_data_strong() -> None:
    """强观测数据应推动后验偏离先验。"""
    prior_probs = np.zeros((169, 3), dtype=np.float32)
    prior_probs[:, 0] = 0.8
    prior_probs[:, 1] = 0.1
    prior_probs[:, 2] = 0.1
    priors = {30: _make_prior(30, prior_probs, "direct_gto")}
    observation = PopulationBucketObservation(
        table_type=6,
        param_index=30,
        action_totals=np.array([0.0, 0.0, 5000.0], dtype=np.float32),
        exposed_counts=np.zeros((169, 3), dtype=np.float32),
    )
    trainer = PopulationTrainer(max_outer_iter=3, max_local_iter=40, tol=1e-7)
    buckets = trainer.fit(observations=[observation], priors=priors)

    assert len(buckets) == 1
    bucket = buckets[0]
    assert float(np.mean(bucket.mean_fcr[:, 2])) > 0.30
