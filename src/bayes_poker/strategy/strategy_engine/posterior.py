"""strategy_engine v2 的最小 posterior 更新。"""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.calibrator import ActionPolicy

_LOW_MASS_THRESHOLD = 1e-9


@dataclass(frozen=True, slots=True)
class PosteriorUpdate:
    """posterior 更新结果。"""

    posterior_range: PreflopRange
    notes: tuple[str, ...] = ()


def update_posterior(
    *,
    prior: PreflopRange,
    calibrated_policy: ActionPolicy,
    action_name: str,
) -> PosteriorUpdate:
    """根据观测动作执行 posterior 更新。"""

    action_likelihood = calibrated_policy.for_action(action_name)
    posterior = PreflopRange(
        strategy=[
            prior_probability * likelihood_probability
            for prior_probability, likelihood_probability in zip(
                prior.strategy,
                action_likelihood.strategy,
                strict=True,
            )
        ],
        evs=list(action_likelihood.evs),
    )
    total_mass = posterior.total_frequency()
    if total_mass <= _LOW_MASS_THRESHOLD:
        return PosteriorUpdate(
            posterior_range=PreflopRange(
                strategy=list(prior.strategy),
                evs=list(prior.evs),
            ),
            notes=("posterior_mass_too_small_keep_prior",),
        )
    posterior.normalize()
    return PosteriorUpdate(posterior_range=posterior)
