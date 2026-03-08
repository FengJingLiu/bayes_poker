"""玩家统计后验平滑原语测试。"""

from __future__ import annotations

import pytest

from bayes_poker.player_metrics.enums import ActionType, Position, Street, TableType
from bayes_poker.player_metrics.params import PostFlopParams, PreFlopParams
from bayes_poker.player_metrics.posterior import (
    ActionSpaceKind,
    ActionSpaceSpec,
    PosteriorSmoothingConfig,
    classify_postflop_action_space,
    classify_preflop_action_space,
    resolve_aggressive_leaf_fields,
    smooth_binary_counts,
    smooth_multinomial_counts,
)


def test_smooth_binary_counts_returns_expected_pseudo_counts() -> None:
    """Beta 二元后验应匹配给定公式。"""

    posterior = smooth_binary_counts(
        prior_probability=0.40,
        prior_strength=20.0,
        positive_count=3.0,
        total_count=10.0,
    )

    assert posterior.positive == pytest.approx(11.0)
    assert posterior.total == pytest.approx(30.0)


def test_smooth_multinomial_counts_returns_expected_pseudo_counts() -> None:
    """Dirichlet 多元后验应匹配给定公式。"""

    posterior = smooth_multinomial_counts(
        prior_probabilities=(0.5, 0.3, 0.2),
        prior_strength=10.0,
        counts=(2.0, 1.0, 7.0),
    )

    assert posterior == pytest.approx((7.0, 4.0, 9.0))


@pytest.mark.parametrize(
    ("prior_strength", "message"),
    [
        (0.0, "prior_strength"),
        (-1.0, "prior_strength"),
    ],
)
def test_smoothing_functions_reject_invalid_prior_strength(
    prior_strength: float,
    message: str,
) -> None:
    """非法先验强度应被拒绝。"""

    with pytest.raises(ValueError, match=message):
        smooth_binary_counts(
            prior_probability=0.5,
            prior_strength=prior_strength,
            positive_count=1.0,
            total_count=2.0,
        )

    with pytest.raises(ValueError, match=message):
        smooth_multinomial_counts(
            prior_probabilities=(0.5, 0.5),
            prior_strength=prior_strength,
            counts=(1.0, 1.0),
        )


def test_smoothing_functions_reject_invalid_probabilities_and_counts() -> None:
    """非法概率和计数应被拒绝。"""

    with pytest.raises(ValueError, match="prior_probability"):
        smooth_binary_counts(
            prior_probability=1.5,
            prior_strength=10.0,
            positive_count=1.0,
            total_count=2.0,
        )

    with pytest.raises(ValueError, match="positive_count"):
        smooth_binary_counts(
            prior_probability=0.5,
            prior_strength=10.0,
            positive_count=-1.0,
            total_count=2.0,
        )

    with pytest.raises(ValueError, match="total_count"):
        smooth_binary_counts(
            prior_probability=0.5,
            prior_strength=10.0,
            positive_count=3.0,
            total_count=2.0,
        )

    with pytest.raises(ValueError, match="prior_probabilities"):
        smooth_multinomial_counts(
            prior_probabilities=(0.6, 0.6),
            prior_strength=10.0,
            counts=(1.0, 1.0),
        )

    with pytest.raises(ValueError, match="counts"):
        smooth_multinomial_counts(
            prior_probabilities=(0.5, 0.5),
            prior_strength=10.0,
            counts=(1.0, -1.0),
        )


def test_classify_preflop_action_space_marks_unopened_rfi_as_binary() -> None:
    """无人入池首个翻前动作应视为二元节点。"""

    params = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=Position.BUTTON,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=ActionType.FOLD,
        in_position_on_flop=False,
    )

    action_space = classify_preflop_action_space(params)

    assert action_space.kind is ActionSpaceKind.BINARY
    assert action_space.positive_field == "raise_samples"
    assert action_space.total_fields == ("fold_samples", "raise_samples")


def test_classify_postflop_action_space_marks_sized_check_spot_as_multinomial() -> None:
    """翻后无人下注且使用 bet sizing 时应解析为多元叶子动作空间。"""

    params = PostFlopParams(
        table_type=TableType.SIX_MAX,
        street=Street.FLOP,
        round=0,
        prev_action=ActionType.CHECK,
        num_bets=0,
        in_position=False,
        num_players=2,
    )
    raw_stats = {
        "bet_0_40": 0,
        "bet_40_80": 3,
        "bet_80_120": 0,
        "bet_over_120": 0,
        "raise_samples": 0,
        "check_call_samples": 2,
        "fold_samples": 0,
    }
    pool_stats = {
        "bet_0_40": 2,
        "bet_40_80": 4,
        "bet_80_120": 3,
        "bet_over_120": 1,
        "raise_samples": 0,
        "check_call_samples": 10,
        "fold_samples": 0,
    }

    action_space = classify_postflop_action_space(
        params,
        raw_field_counts=raw_stats,
        pool_field_counts=pool_stats,
    )

    assert action_space.kind is ActionSpaceKind.MULTINOMIAL
    assert action_space.total_fields == (
        "check_call_samples",
        "bet_0_40",
        "bet_40_80",
        "bet_80_120",
        "bet_over_120",
    )


def test_classify_postflop_action_space_marks_unsized_check_spot_as_binary() -> None:
    """翻后无人下注且只有 unsized aggressive 时应保持二元。"""

    params = PostFlopParams(
        table_type=TableType.SIX_MAX,
        street=Street.FLOP,
        round=0,
        prev_action=ActionType.CHECK,
        num_bets=0,
        in_position=False,
        num_players=2,
    )

    action_space = classify_postflop_action_space(
        params,
        raw_field_counts={
            "bet_0_40": 0,
            "bet_40_80": 0,
            "bet_80_120": 0,
            "bet_over_120": 0,
            "raise_samples": 2,
            "check_call_samples": 4,
            "fold_samples": 0,
        },
        pool_field_counts={
            "bet_0_40": 0,
            "bet_40_80": 0,
            "bet_80_120": 0,
            "bet_over_120": 0,
            "raise_samples": 6,
            "check_call_samples": 8,
            "fold_samples": 0,
        },
    )

    assert action_space.kind is ActionSpaceKind.BINARY
    assert action_space.positive_field == "raise_samples"
    assert action_space.total_fields == ("check_call_samples", "raise_samples")


def test_classify_postflop_action_space_marks_facing_bet_as_multinomial() -> None:
    """翻后面对下注且有 bet sizing 时应视为多元叶子动作空间。"""

    params = PostFlopParams(
        table_type=TableType.SIX_MAX,
        street=Street.FLOP,
        round=0,
        prev_action=ActionType.RAISE,
        num_bets=1,
        in_position=False,
        num_players=2,
    )

    action_space = classify_postflop_action_space(
        params,
        raw_field_counts={
            "bet_0_40": 0,
            "bet_40_80": 1,
            "bet_80_120": 0,
            "bet_over_120": 0,
            "raise_samples": 0,
            "check_call_samples": 2,
            "fold_samples": 4,
        },
        pool_field_counts={
            "bet_0_40": 2,
            "bet_40_80": 3,
            "bet_80_120": 1,
            "bet_over_120": 1,
            "raise_samples": 0,
            "check_call_samples": 9,
            "fold_samples": 5,
        },
    )

    assert action_space.kind is ActionSpaceKind.MULTINOMIAL
    assert action_space.total_fields == (
        "fold_samples",
        "check_call_samples",
        "bet_0_40",
        "bet_40_80",
        "bet_80_120",
        "bet_over_120",
    )


def test_classify_preflop_action_space_marks_unopened_sb_as_multinomial() -> None:
    """SB unopened 存在 complete/limp, 不应被视为纯二元节点。"""

    params = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=Position.SMALL_BLIND,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=ActionType.FOLD,
        in_position_on_flop=False,
    )

    action_space = classify_preflop_action_space(params)

    assert action_space.kind is ActionSpaceKind.MULTINOMIAL
    assert action_space.total_fields == (
        "fold_samples",
        "check_call_samples",
        "raise_samples",
    )


@pytest.mark.parametrize("pool_prior_strength", (0.0, -1.0))
def test_posterior_smoothing_config_rejects_invalid_strength(
    pool_prior_strength: float,
) -> None:
    """后验配置应拒绝非法先验强度。"""

    with pytest.raises(ValueError, match="pool_prior_strength"):
        PosteriorSmoothingConfig(enabled=True, pool_prior_strength=pool_prior_strength)


def test_action_space_spec_rejects_inconsistent_binary_definition() -> None:
    """二元动作空间定义不一致时应抛错。"""

    with pytest.raises(ValueError, match="positive_field"):
        ActionSpaceSpec(
            kind=ActionSpaceKind.BINARY,
            total_fields=("fold_samples", "raise_samples"),
            positive_field=None,
        )


def test_resolve_aggressive_leaf_fields_rejects_mixed_bet_and_raise_samples() -> None:
    """同一 node 同时出现 bet* 和 raise_samples 时应抛错。"""

    with pytest.raises(ValueError, match="bet_\\* 与 raise_samples"):
        resolve_aggressive_leaf_fields(
            raw_field_counts={
                "bet_0_40": 1.0,
                "bet_40_80": 0.0,
                "bet_80_120": 0.0,
                "bet_over_120": 0.0,
                "raise_samples": 2.0,
            },
            pool_field_counts={
                "bet_0_40": 0.0,
                "bet_40_80": 0.0,
                "bet_80_120": 0.0,
                "bet_over_120": 0.0,
                "raise_samples": 0.0,
            },
            allow_sized_aggression=True,
        )
