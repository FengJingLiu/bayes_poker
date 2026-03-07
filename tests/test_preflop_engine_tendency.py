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
    population_stats = ActionStats(
        raise_samples=2,
        check_call_samples=1,
        fold_samples=1,
    )
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


def test_build_profile_tracks_size_signal_only_when_samples_are_enough() -> None:
    """测试尺寸信号只有在样本充足时才启用.

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
    population_stats = ActionStats(
        raise_samples=1,
        check_call_samples=1,
        fold_samples=1,
    )
    profile_builder = tendency_module.PlayerTendencyProfileBuilder(
        smoothing_k=4.0,
        confidence_k=4.0,
        size_signal_threshold=10,
    )

    profile = profile_builder.build(
        player_stats=player_stats,
        params=params,
        population_stats=population_stats,
        size_signal_sample_count=9,
    )

    assert profile.size_signal_enabled is False
