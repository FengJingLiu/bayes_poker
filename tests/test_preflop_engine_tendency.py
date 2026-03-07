"""翻前玩家画像与平滑层测试."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from bayes_poker.player_metrics.enums import ActionType, Position, TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats
from bayes_poker.player_metrics.params import PreFlopParams


def _load_tendency_module() -> ModuleType:
    """加载翻前玩家画像模块.

    Returns:
        翻前玩家画像模块对象.
    """

    try:
        return importlib.import_module("bayes_poker.strategy.preflop_engine.tendency")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少翻前画像模块: {exc}")


def _make_preflop_params() -> PreFlopParams:
    """构造测试使用的翻前参数.

    Returns:
        指向 6-max CO 首入池场景的翻前参数.
    """

    return PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=Position.CO,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=ActionType.FOLD,
        in_position_on_flop=False,
    )


def _make_player_stats(
    *,
    params: PreFlopParams,
    raise_samples: int,
    check_call_samples: int,
    fold_samples: int,
) -> PlayerStats:
    """构造测试使用的玩家统计.

    Args:
        params: 要写入的翻前参数.
        raise_samples: 激进行动样本数.
        check_call_samples: 跟注/过牌样本数.
        fold_samples: 弃牌样本数.

    Returns:
        含指定翻前统计的玩家统计对象.
    """

    player_stats = PlayerStats(
        player_name="hero",
        table_type=TableType.SIX_MAX,
    )
    action_stats = player_stats.get_preflop_stats(params)
    action_stats.raise_samples = raise_samples
    action_stats.check_call_samples = check_call_samples
    action_stats.fold_samples = fold_samples
    return player_stats


def _make_population_stats() -> ActionStats:
    """构造测试使用的总体统计.

    Returns:
        带有最小先验频率的总体统计对象.
    """

    return ActionStats(
        raise_samples=1,
        check_call_samples=1,
        fold_samples=1,
    )


def test_build_profile_blends_population_and_player_stats() -> None:
    """测试画像构建会融合总体先验与玩家样本.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()
    params = _make_preflop_params()
    player_stats = _make_player_stats(
        params=params,
        raise_samples=3,
        check_call_samples=1,
        fold_samples=0,
    )
    population_stats = ActionStats(raise_samples=2, check_call_samples=1, fold_samples=1)
    profile_builder = tendency_module.PlayerTendencyProfileBuilder(
        smoothing_k=4.0,
        confidence_k=4.0,
        size_signal_threshold=10,
    )

    profile = profile_builder.build(
        player_stats=player_stats,
        params=params,
        population_stats=population_stats,
    )

    assert profile.open_freq == pytest.approx(0.625)
    assert profile.call_freq == pytest.approx(0.25)
    assert 0.0 < profile.confidence < 1.0
    assert profile.confidence == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("sample_count", "expected_enabled"),
    [
        (None, False),
        (9, False),
        (10, True),
        (11, True),
    ],
)
def test_build_profile_sets_size_signal_flag_from_sample_count(
    sample_count: int | None,
    expected_enabled: bool,
) -> None:
    """测试尺寸信号启用标记会遵循样本阈值.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()
    params = _make_preflop_params()
    player_stats = _make_player_stats(
        params=params,
        raise_samples=1,
        check_call_samples=0,
        fold_samples=0,
    )
    population_stats = _make_population_stats()
    profile_builder = tendency_module.PlayerTendencyProfileBuilder(
        smoothing_k=4.0,
        confidence_k=4.0,
        size_signal_threshold=10,
    )

    profile = profile_builder.build(
        player_stats=player_stats,
        params=params,
        population_stats=population_stats,
        size_signal_sample_count=sample_count,
    )

    assert profile.size_signal_enabled is expected_enabled


def test_smooth_frequency_returns_blended_frequency() -> None:
    """测试 `smooth_frequency()` 会返回平滑后的频率.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()

    assert tendency_module.smooth_frequency(3, 4, 0.5, 4.0) == pytest.approx(0.625)


@pytest.mark.parametrize(
    ("n_act", "total", "mu", "k", "message"),
    [
        (-1, 4, 0.5, 4.0, "n_act"),
        (1, -1, 0.5, 4.0, "total"),
        (5, 4, 0.5, 4.0, "n_act"),
        (1, 4, 0.5, 0.0, "k"),
        (1, 4, 0.5, -1.0, "k"),
    ],
)
def test_smooth_frequency_rejects_invalid_inputs(
    n_act: int,
    total: int,
    mu: float,
    k: float,
    message: str,
) -> None:
    """测试 `smooth_frequency()` 会拒绝非法输入.

    Args:
        n_act: 玩家动作样本数.
        total: 玩家总样本数.
        mu: 总体先验频率.
        k: 先验强度.
        message: 预期异常消息片段.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()

    with pytest.raises(ValueError, match=message):
        tendency_module.smooth_frequency(n_act, total, mu, k)


def test_build_confidence_returns_smoothed_confidence() -> None:
    """测试 `build_confidence()` 会返回平滑后的置信度.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()

    assert tendency_module.build_confidence(4, 4.0) == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("total", "k", "message"),
    [
        (-1, 4.0, "total"),
        (1, 0.0, "k"),
        (1, -1.0, "k"),
    ],
)
def test_build_confidence_rejects_invalid_inputs(
    total: int,
    k: float,
    message: str,
) -> None:
    """测试 `build_confidence()` 会拒绝非法输入.

    Args:
        total: 玩家总样本数.
        k: 置信度平滑系数.
        message: 预期异常消息片段.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()

    with pytest.raises(ValueError, match=message):
        tendency_module.build_confidence(total, k)


def test_build_profile_rejects_negative_size_signal_sample_count() -> None:
    """测试画像构建会拒绝负数的尺寸样本数.

    Returns:
        None.
    """

    tendency_module = _load_tendency_module()
    params = _make_preflop_params()
    player_stats = _make_player_stats(
        params=params,
        raise_samples=1,
        check_call_samples=0,
        fold_samples=0,
    )
    population_stats = _make_population_stats()
    profile_builder = tendency_module.PlayerTendencyProfileBuilder(
        smoothing_k=4.0,
        confidence_k=4.0,
        size_signal_threshold=10,
    )

    with pytest.raises(ValueError, match="size_signal_sample_count"):
        profile_builder.build(
            player_stats=player_stats,
            params=params,
            population_stats=population_stats,
            size_signal_sample_count=-1,
        )
