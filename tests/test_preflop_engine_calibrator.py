"""翻前策略校准器测试."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from bayes_poker.strategy.range import (
    PreflopRange,
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    get_hand_key_to_169_index,
)

_HAND_KEY_TO_169_INDEX = get_hand_key_to_169_index()


def _load_policy_calibrator_module() -> ModuleType:
    """加载翻前策略校准器模块.

    Returns:
        翻前策略校准器模块对象.
    """

    return importlib.import_module(
        "bayes_poker.strategy.preflop_engine.policy_calibrator"
    )


def _build_range(
    *,
    default_frequency: float,
    overrides: dict[str, float] | None = None,
    ev_overrides: dict[str, float] | None = None,
) -> PreflopRange:
    """构造覆盖全部 169 手牌的测试范围.

    Args:
        default_frequency: 默认动作频率.
        overrides: 指定手牌的频率覆盖.
        ev_overrides: 指定手牌的 EV 覆盖.

    Returns:
        测试用 PreflopRange.
    """

    strategy = [default_frequency] * RANGE_169_LENGTH
    evs = [0.0] * RANGE_169_LENGTH

    for hand_key, frequency in (overrides or {}).items():
        strategy[_HAND_KEY_TO_169_INDEX[hand_key]] = frequency

    for hand_key, ev in (ev_overrides or {}).items():
        evs[_HAND_KEY_TO_169_INDEX[hand_key]] = ev

    return PreflopRange(strategy=strategy, evs=evs)


def _build_binary_policy() -> object:
    """构造二元校准测试策略.

    Returns:
        测试用 ActionPolicy.
    """

    calibrator_module = _load_policy_calibrator_module()
    action_policy_action_cls = calibrator_module.ActionPolicyAction
    action_policy_cls = calibrator_module.ActionPolicy

    open_overrides = {
        "AJs": 0.35,
        "KQo": 0.25,
        "22": 0.18,
    }
    open_range = _build_range(default_frequency=0.08, overrides=open_overrides)
    fold_strategy = [1.0 - frequency for frequency in open_range.strategy]
    fold_range = PreflopRange(strategy=fold_strategy, evs=[0.0] * RANGE_169_LENGTH)

    return action_policy_cls(
        actions=(
            action_policy_action_cls(action_name="FOLD", range=fold_range),
            action_policy_action_cls(action_name="OPEN", range=open_range),
        )
    )


def _build_multinomial_policy() -> tuple[object, dict[str, float]]:
    """构造多动作校准测试策略.

    Returns:
        基础策略与目标混合频率.
    """

    calibrator_module = _load_policy_calibrator_module()
    action_policy_action_cls = calibrator_module.ActionPolicyAction
    action_policy_cls = calibrator_module.ActionPolicy

    fold_range = _build_range(
        default_frequency=0.90,
        overrides={
            "AJs": 0.15,
            "22": 0.45,
            "KQo": 0.55,
        },
    )
    call_range = _build_range(
        default_frequency=0.08,
        overrides={
            "AJs": 0.65,
            "22": 0.40,
            "KQo": 0.30,
        },
        ev_overrides={
            "AJs": 3.0,
            "22": 2.0,
            "KQo": 1.5,
        },
    )
    raise_range = _build_range(
        default_frequency=0.02,
        overrides={
            "AJs": 0.20,
            "22": 0.15,
            "KQo": 0.15,
        },
    )

    policy = action_policy_cls(
        actions=(
            action_policy_action_cls(action_name="FOLD", range=fold_range),
            action_policy_action_cls(action_name="CALL", range=call_range),
            action_policy_action_cls(action_name="RAISE", range=raise_range),
        )
    )
    return policy, {"FOLD": 0.84, "CALL": 0.11, "RAISE": 0.05}


def test_action_policy_accessors_return_range_and_rank_tuple() -> None:
    """测试策略访问器暴露最小范围接口.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    policy = _build_binary_policy()

    open_range = policy.for_action("OPEN")

    assert isinstance(open_range, PreflopRange)
    assert policy.total_frequency("OPEN") == pytest.approx(open_range.total_frequency())
    assert isinstance(policy.rank_for("OPEN"), tuple)


def test_binary_calibrator_matches_target_open_frequency() -> None:
    """测试二元校准器会对齐目标 open 频率.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    base_policy = _build_binary_policy()

    calibrated = calibrator_module.calibrate_binary_policy(
        base_policy,
        target_frequency=0.10,
    )

    assert calibrated.total_frequency("OPEN") == pytest.approx(0.10, abs=1e-3)


def test_multinomial_calibrator_preserves_relative_hand_order() -> None:
    """测试多动作校准保持 call 排序并逼近目标混合.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    base_policy, target_mix = _build_multinomial_policy()

    calibrated = calibrator_module.calibrate_multinomial_policy(
        base_policy,
        target_mix=target_mix,
    )

    assert calibrated.rank_for("CALL") == base_policy.rank_for("CALL")
    assert calibrated.rank_for("CALL")[0] == "AJs"
    assert calibrated.total_frequency("CALL") == pytest.approx(0.11, abs=1e-3)
    assert calibrated.total_frequency("RAISE") == pytest.approx(0.05, abs=1e-3)


def test_rank_for_uses_strategy_then_ev_then_original_order() -> None:
    """测试排序键依次使用频率、EV 和原始顺序.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    action_policy_action_cls = calibrator_module.ActionPolicyAction
    action_policy_cls = calibrator_module.ActionPolicy

    strategy = [0.0] * RANGE_169_LENGTH
    evs = [0.0] * RANGE_169_LENGTH

    for hand_key, frequency, ev in (
        ("AJs", 0.40, 1.0),
        ("KQs", 0.40, 0.5),
        ("AQs", 0.40, 0.5),
    ):
        index = _HAND_KEY_TO_169_INDEX[hand_key]
        strategy[index] = frequency
        evs[index] = ev

    policy = action_policy_cls(
        actions=(
            action_policy_action_cls(
                action_name="CALL",
                range=PreflopRange(strategy=strategy, evs=evs),
            ),
        )
    )

    ranked_hands = policy.rank_for("CALL")[:3]
    expected_order = tuple(
        sorted(
            ("AJs", "KQs", "AQs"),
            key=lambda hand_key: (
                -strategy[_HAND_KEY_TO_169_INDEX[hand_key]],
                -evs[_HAND_KEY_TO_169_INDEX[hand_key]],
                RANGE_169_ORDER.index(hand_key),
            ),
        )
    )

    assert ranked_hands == expected_order


@pytest.mark.parametrize("target_frequency", (-0.1, 1.1))
def test_binary_calibrator_rejects_out_of_range_target_frequency(
    target_frequency: float,
) -> None:
    """测试二元校准器会拒绝越界目标频率.

    Args:
        target_frequency: 非法目标频率.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()

    with pytest.raises(ValueError, match="target_frequency"):
        calibrator_module.calibrate_binary_policy(
            _build_binary_policy(),
            target_frequency=target_frequency,
        )


def test_multinomial_calibrator_rejects_invalid_target_mix() -> None:
    """测试多动作校准器会拒绝非法目标混合.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    base_policy, _ = _build_multinomial_policy()

    with pytest.raises(ValueError, match="target_mix"):
        calibrator_module.calibrate_multinomial_policy(
            base_policy,
            target_mix={"FOLD": 0.90, "CALL": 0.10},
        )


def test_binary_calibrator_rejects_non_simplex_policy() -> None:
    """测试二元校准器会拒绝非单纯形输入策略.

    Returns:
        None.
    """

    calibrator_module = _load_policy_calibrator_module()
    action_policy_action_cls = calibrator_module.ActionPolicyAction
    action_policy_cls = calibrator_module.ActionPolicy
    invalid_policy = action_policy_cls(
        actions=(
            action_policy_action_cls(
                action_name="FOLD",
                range=_build_range(default_frequency=0.70),
            ),
            action_policy_action_cls(
                action_name="OPEN",
                range=_build_range(default_frequency=0.20),
            ),
        )
    )

    with pytest.raises(ValueError, match="概率总和"):
        calibrator_module.calibrate_binary_policy(
            invalid_policy,
            target_frequency=0.10,
        )
