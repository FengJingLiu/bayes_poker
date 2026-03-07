"""翻前贝叶斯范围引擎测试."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from bayes_poker.strategy.preflop_engine.policy_calibrator import (
    ActionPolicy,
    ActionPolicyAction,
)
from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
    get_hand_key_to_169_index,
)

_HAND_KEY_TO_169_INDEX = get_hand_key_to_169_index()


def _load_range_engine_module() -> ModuleType:
    """加载范围引擎模块.

    Returns:
        范围引擎模块对象.
    """

    return importlib.import_module("bayes_poker.strategy.preflop_engine.range_engine")


def _build_range(
    *,
    default_frequency: float,
    overrides: dict[str, float] | None = None,
) -> PreflopRange:
    """构造覆盖全部 169 手牌的测试范围.

    Args:
        default_frequency: 默认动作频率.
        overrides: 指定手牌的频率覆盖.

    Returns:
        测试用 PreflopRange.
    """

    strategy = [default_frequency] * RANGE_169_LENGTH
    for hand_key, frequency in (overrides or {}).items():
        strategy[_HAND_KEY_TO_169_INDEX[hand_key]] = frequency
    return PreflopRange(strategy=strategy, evs=[0.0] * RANGE_169_LENGTH)


def _build_action_policy(
    *,
    action_name: str,
    default_frequency: float,
    overrides: dict[str, float],
) -> ActionPolicy:
    """构造单动作测试策略.

    Args:
        action_name: 动作名称.
        default_frequency: 默认动作频率.
        overrides: 指定手牌的频率覆盖.

    Returns:
        测试用 ActionPolicy.
    """

    action_range = _build_range(
        default_frequency=default_frequency,
        overrides=overrides,
    )
    return ActionPolicy(
        actions=(
            ActionPolicyAction(
                action_name=action_name,
                range=action_range,
            ),
        )
    )


def test_range_engine_builds_tight_utg_open_posterior() -> None:
    """测试范围引擎会构造更紧的 UTG open 后验.

    Returns:
        None.
    """

    range_engine_module = _load_range_engine_module()
    range_engine = range_engine_module.RangeEngine()
    calibrated_policy = _build_action_policy(
        action_name="OPEN",
        default_frequency=0.02,
        overrides={
            "AQo": 0.55,
            "KQo": 0.08,
        },
    )

    posterior = range_engine.observe_action(
        prior=PreflopRange.ones(),
        calibrated_policy=calibrated_policy,
        action_name="OPEN",
    )

    assert posterior.total_frequency() == pytest.approx(1.0)
    assert posterior["KQo"] < posterior["AQo"]


def test_range_engine_builds_condensed_mp_cold_call_range() -> None:
    """测试范围引擎会构造更 condensed 的 MP cold call 后验.

    Returns:
        None.
    """

    range_engine_module = _load_range_engine_module()
    range_engine = range_engine_module.RangeEngine()
    calibrated_policy = _build_action_policy(
        action_name="CALL",
        default_frequency=0.03,
        overrides={
            "AJs": 0.42,
            "AKs": 0.07,
        },
    )

    posterior = range_engine.observe_action(
        prior=PreflopRange.ones(),
        calibrated_policy=calibrated_policy,
        action_name="CALL",
    )

    assert posterior.total_frequency() == pytest.approx(1.0)
    assert posterior["AJs"] > posterior["AKs"]


def test_range_engine_posterior_respects_non_uniform_prior() -> None:
    """测试后验会受到非均匀先验影响.

    Returns:
        None.
    """

    range_engine_module = _load_range_engine_module()
    range_engine = range_engine_module.RangeEngine()
    calibrated_policy = _build_action_policy(
        action_name="OPEN",
        default_frequency=0.05,
        overrides={
            "AQo": 0.30,
            "KQo": 0.30,
        },
    )
    prior = _build_range(
        default_frequency=0.01,
        overrides={
            "AQo": 0.10,
            "KQo": 0.60,
        },
    )

    posterior = range_engine.observe_action(
        prior=prior,
        calibrated_policy=calibrated_policy,
        action_name="OPEN",
    )

    assert posterior.total_frequency() == pytest.approx(1.0)
    assert posterior["KQo"] > posterior["AQo"]


def test_range_belief_hides_mutable_posterior_range() -> None:
    """测试后验包装器不会公开可变范围对象.

    Returns:
        None.
    """

    range_engine_module = _load_range_engine_module()
    range_engine = range_engine_module.RangeEngine()
    calibrated_policy = _build_action_policy(
        action_name="OPEN",
        default_frequency=0.05,
        overrides={
            "AQo": 0.30,
        },
    )

    posterior = range_engine.observe_action(
        prior=PreflopRange.ones(),
        calibrated_policy=calibrated_policy,
        action_name="OPEN",
    )

    with pytest.raises(AttributeError):
        _ = posterior.posterior_range
