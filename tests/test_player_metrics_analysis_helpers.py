from __future__ import annotations

import json
from pathlib import Path

import pytest

from bayes_poker.player_metrics.analysis_helpers import (
    build_core_stats_comparison,
    build_node_delta_table,
)
from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_total_hands,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import ActionType, Position, PreflopPotType, Street, TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.params import PostFlopParams, PreFlopParams


def _set_preflop_action(
    stats: PlayerStats,
    params: PreFlopParams,
    *,
    raise_samples: int = 0,
    check_call_samples: int = 0,
    fold_samples: int = 0,
) -> None:
    action_stats = stats.preflop_stats[params.to_index()]
    action_stats.raise_samples = raise_samples
    action_stats.check_call_samples = check_call_samples
    action_stats.fold_samples = fold_samples


def _set_postflop_action(
    stats: PlayerStats,
    params: PostFlopParams,
    *,
    bet_0_40: int = 0,
    bet_40_80: int = 0,
    bet_80_120: int = 0,
    bet_over_120: int = 0,
    raise_samples: int = 0,
    check_call_samples: int = 0,
    fold_samples: int = 0,
) -> None:
    action_stats = stats.postflop_stats[params.to_index()]
    action_stats.bet_0_40 = bet_0_40
    action_stats.bet_40_80 = bet_40_80
    action_stats.bet_80_120 = bet_80_120
    action_stats.bet_over_120 = bet_over_120
    action_stats.raise_samples = raise_samples
    action_stats.check_call_samples = check_call_samples
    action_stats.fold_samples = fold_samples


def _build_raw_and_smoothed_stats() -> tuple[PlayerStats, PlayerStats]:
    raw_stats = PlayerStats(
        player_name="LowSampleHero",
        table_type=TableType.SIX_MAX,
        vpip=StatValue(positive=3, total=20),
    )
    smoothed_stats = PlayerStats(
        player_name="LowSampleHero",
        table_type=TableType.SIX_MAX,
        vpip=StatValue(positive=3, total=20),
    )

    preflop_primary = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=Position.BUTTON,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=ActionType.FOLD,
        in_position_on_flop=False,
    )
    preflop_secondary = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=Position.BIG_BLIND,
        num_callers=0,
        num_raises=1,
        num_active_players=6,
        previous_action=ActionType.FOLD,
        in_position_on_flop=False,
    )
    _set_preflop_action(raw_stats, preflop_primary, raise_samples=1)
    _set_preflop_action(smoothed_stats, preflop_primary, raise_samples=8, check_call_samples=6, fold_samples=6)
    _set_preflop_action(raw_stats, preflop_secondary, check_call_samples=2, fold_samples=1)
    _set_preflop_action(smoothed_stats, preflop_secondary, raise_samples=4, check_call_samples=8, fold_samples=8)

    postflop_primary = PostFlopParams(
        table_type=TableType.SIX_MAX,
        street=Street.FLOP,
        round=0,
        prev_action=ActionType.CHECK,
        num_bets=0,
        in_position=True,
        num_players=2,
        preflop_pot_type=PreflopPotType.SINGLE_RAISED,
        is_preflop_aggressor=True,
    )
    postflop_secondary = PostFlopParams(
        table_type=TableType.SIX_MAX,
        street=Street.TURN,
        round=0,
        prev_action=ActionType.CALL,
        num_bets=1,
        in_position=False,
        num_players=2,
        preflop_pot_type=PreflopPotType.SINGLE_RAISED,
        is_preflop_aggressor=False,
    )
    _set_postflop_action(raw_stats, postflop_primary, bet_0_40=1)
    _set_postflop_action(
        smoothed_stats,
        postflop_primary,
        bet_0_40=5,
        bet_40_80=3,
        check_call_samples=8,
        fold_samples=4,
    )
    _set_postflop_action(raw_stats, postflop_secondary, fold_samples=2, check_call_samples=1)
    _set_postflop_action(
        smoothed_stats,
        postflop_secondary,
        bet_40_80=2,
        raise_samples=3,
        check_call_samples=5,
        fold_samples=10,
    )
    return raw_stats, smoothed_stats


def test_build_core_stats_comparison_returns_raw_and_smoothed_columns() -> None:
    raw_stats, smoothed_stats = _build_raw_and_smoothed_stats()

    result = build_core_stats_comparison(raw_stats, smoothed_stats)

    assert list(result.columns) == [
        "指标",
        "原始值",
        "平滑值",
        "原始百分比",
        "平滑百分比",
    ]
    assert result["指标"].tolist() == ["总手数", "VPIP", "PFR", "WTP", "AGG"]

    pfr_raw_positive, pfr_raw_total = calculate_pfr(raw_stats)
    pfr_smoothed_positive, pfr_smoothed_total = calculate_pfr(smoothed_stats)
    pfr_row = result[result["指标"] == "PFR"].iloc[0]
    assert pfr_row["原始值"] == f"{pfr_raw_positive}/{pfr_raw_total}"
    assert pfr_row["平滑值"] == f"{pfr_smoothed_positive}/{pfr_smoothed_total}"

    total_hands_row = result[result["指标"] == "总手数"].iloc[0]
    assert total_hands_row["原始值"] == str(calculate_total_hands(raw_stats))
    assert total_hands_row["平滑值"] == str(calculate_total_hands(smoothed_stats))


def test_build_node_delta_table_returns_top_preflop_nodes_sorted_by_delta() -> None:
    raw_stats, smoothed_stats = _build_raw_and_smoothed_stats()

    result = build_node_delta_table(raw_stats, smoothed_stats, scope="preflop", top_n=2)

    assert list(result.columns) == [
        "索引",
        "节点描述",
        "原始样本数",
        "平滑样本数",
        "原始加注%",
        "平滑加注%",
        "原始跟注%",
        "平滑跟注%",
        "原始弃牌%",
        "平滑弃牌%",
        "L1差异",
    ]
    assert len(result) == 2
    assert result.iloc[0]["L1差异"] >= result.iloc[1]["L1差异"]
    assert "BUTTON" in result.iloc[0]["节点描述"] or "BIG_BLIND" in result.iloc[0]["节点描述"]


def test_build_node_delta_table_returns_postflop_sizing_fields() -> None:
    raw_stats, smoothed_stats = _build_raw_and_smoothed_stats()

    result = build_node_delta_table(raw_stats, smoothed_stats, scope="postflop", top_n=2)

    assert len(result) == 2
    assert result.iloc[0]["原始样本数"] >= 1
    assert "FLOP" in " ".join(result["节点描述"].tolist()) or "TURN" in " ".join(
        result["节点描述"].tolist()
    )


def test_build_node_delta_table_ignores_extra_preflop_slots() -> None:
    raw_stats, smoothed_stats = _build_raw_and_smoothed_stats()
    raw_stats.preflop_stats.extend(ActionStats() for _ in range(24))
    smoothed_stats.preflop_stats.extend(ActionStats() for _ in range(24))

    result = build_node_delta_table(raw_stats, smoothed_stats, scope="preflop", top_n=2)

    assert len(result) == 2


def test_notebook_contains_low_sample_comparison_section() -> None:
    notebook_path = Path("notebooks/player_stats_analysis.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    joined_sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "## 8. 低样本玩家：平滑 vs 非平滑" in joined_sources
    assert 'LOW_SAMPLE_PLAYER_NAME = "AndrewYuen"' in joined_sources


def test_notebook_contains_configured_player_comparison_section() -> None:
    notebook_path = Path("notebooks/player_stats_analysis.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    joined_sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "## 9. 当前配置玩家：平滑 vs 非平滑" in joined_sources
    assert "configured_raw_stats, configured_smoothed_stats = load_player_stats_comparison(" in joined_sources
    assert "PLAYER_NAME," in joined_sources
