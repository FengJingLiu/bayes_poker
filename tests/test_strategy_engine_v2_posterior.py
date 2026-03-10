from __future__ import annotations

import pytest

from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
    get_hand_key_to_169_index,
)
from bayes_poker.strategy.strategy_engine.calibrator import (
    ActionPolicy,
    ActionPolicyAction,
    calibrate_binary_policy,
    calibrate_multinomial_policy,
    redistribute_aggressive_mass,
)
from bayes_poker.strategy.strategy_engine.posterior import update_posterior

_HAND_KEY_TO_INDEX = get_hand_key_to_169_index()


def _build_range(
    *,
    default_frequency: float,
    overrides: dict[str, float] | None = None,
) -> PreflopRange:
    strategy = [default_frequency] * RANGE_169_LENGTH
    for hand_key, frequency in (overrides or {}).items():
        strategy[_HAND_KEY_TO_INDEX[hand_key]] = frequency
    return PreflopRange(strategy=strategy, evs=[0.0] * RANGE_169_LENGTH)


def test_binary_calibration_matches_target_frequency() -> None:
    open_range = _build_range(
        default_frequency=0.08,
        overrides={"AJs": 0.35, "KQo": 0.25, "22": 0.18},
    )
    fold_range = PreflopRange(
        strategy=[1.0 - frequency for frequency in open_range.strategy],
        evs=[0.0] * RANGE_169_LENGTH,
    )
    policy = ActionPolicy(
        actions=(
            ActionPolicyAction(action_name="FOLD", range=fold_range),
            ActionPolicyAction(action_name="OPEN", range=open_range),
        )
    )

    calibrated = calibrate_binary_policy(policy, target_frequency=0.10)

    assert calibrated.total_frequency("OPEN") == pytest.approx(0.10, abs=1e-3)


def test_multinomial_calibration_matches_target_mix() -> None:
    policy = ActionPolicy(
        actions=(
            ActionPolicyAction(
                action_name="FOLD",
                range=_build_range(default_frequency=0.90, overrides={"AJs": 0.15}),
            ),
            ActionPolicyAction(
                action_name="CALL",
                range=_build_range(default_frequency=0.08, overrides={"AJs": 0.65}),
            ),
            ActionPolicyAction(
                action_name="RAISE",
                range=_build_range(default_frequency=0.02, overrides={"AJs": 0.20}),
            ),
        )
    )

    calibrated = calibrate_multinomial_policy(
        policy,
        target_mix={"FOLD": 0.84, "CALL": 0.11, "RAISE": 0.05},
    )

    assert calibrated.total_frequency("CALL") == pytest.approx(0.11, abs=1e-3)
    assert calibrated.total_frequency("RAISE") == pytest.approx(0.05, abs=1e-3)


def test_posterior_normalize() -> None:
    policy = ActionPolicy(
        actions=(
            ActionPolicyAction(
                action_name="OPEN",
                range=_build_range(
                    default_frequency=0.02, overrides={"AQo": 0.55, "KQo": 0.08}
                ),
            ),
        )
    )

    result = update_posterior(
        prior=PreflopRange.ones(),
        calibrated_policy=policy,
        action_name="OPEN",
    )

    assert result.posterior_range.total_frequency() == pytest.approx(1.0)
    assert (
        result.posterior_range.strategy[_HAND_KEY_TO_INDEX["AQo"]]
        > result.posterior_range.strategy[_HAND_KEY_TO_INDEX["KQo"]]
    )


def test_low_mass_keeps_prior() -> None:
    policy = ActionPolicy(
        actions=(
            ActionPolicyAction(
                action_name="OPEN",
                range=PreflopRange.zeros(),
            ),
        )
    )
    prior = _build_range(default_frequency=0.01, overrides={"AQo": 0.10})

    result = update_posterior(
        prior=prior,
        calibrated_policy=policy,
        action_name="OPEN",
    )

    assert result.notes == ("posterior_mass_too_small_keep_prior",)
    assert result.posterior_range.strategy == prior.strategy


def test_size_signal_redistributes_raise_mass() -> None:
    policy = ActionPolicy(
        actions=(
            ActionPolicyAction(
                action_name="F", range=_build_range(default_frequency=0.20)
            ),
            ActionPolicyAction(
                action_name="C", range=_build_range(default_frequency=0.30)
            ),
            ActionPolicyAction(
                action_name="R2.5", range=_build_range(default_frequency=0.10)
            ),
            ActionPolicyAction(
                action_name="R6", range=_build_range(default_frequency=0.40)
            ),
        )
    )

    redistributed = redistribute_aggressive_mass(
        policy,
        size_weights={"R2.5": 0.8, "R6": 0.2},
    )

    original_raise_mass = policy.total_frequency("R2.5") + policy.total_frequency("R6")
    redistributed_raise_mass = redistributed.total_frequency(
        "R2.5"
    ) + redistributed.total_frequency("R6")

    assert redistributed_raise_mass == pytest.approx(original_raise_mass)
    assert redistributed.total_frequency("R2.5") > redistributed.total_frequency("R6")
