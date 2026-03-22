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

    posterior_strategy = prior.strategy * action_likelihood.strategy
    posterior = PreflopRange(strategy=posterior_strategy, evs=action_likelihood.evs)

    total_mass = posterior.total_frequency()
    if total_mass <= _LOW_MASS_THRESHOLD:
        return PosteriorUpdate(
            posterior_range=PreflopRange(strategy=prior.strategy.copy(), evs=prior.evs.copy()),
            notes=("posterior_mass_too_small_keep_prior",),
        )
    posterior.normalize()
    return PosteriorUpdate(posterior_range=posterior)
