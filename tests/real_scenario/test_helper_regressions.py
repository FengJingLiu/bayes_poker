"""真实场景 helper 回归测试。"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.domain.poker import ActionType
from bayes_poker.domain.table import Position

from . import test_comprehensive_opponent_profiles as comprehensive_profiles
from .helpers import (
    ALL_3BET_COMBINATIONS_6MAX,
    ALL_4BET_COMBINATIONS_6MAX,
    ALL_FACING_3BET_COMBINATIONS_6MAX,
    ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX,
    ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX,
    ALL_RFI_COMBINATIONS_6MAX,
    _POSITION_TO_SEAT_6MAX,
    build_hero_3bet_facing_4bet_state,
    generate_scenario_report,
)


def test_build_hero_3bet_facing_4bet_state_resolves_opener_before_hero_turn() -> None:
    """Hero 面对 4-bet 前, opener 必须先完成对 4-bet 的响应。"""

    observed_state = build_hero_3bet_facing_4bet_state(
        opener_position=Position.UTG,
        hero_3bettor_position=Position.MP,
        four_bettor_position=Position.CO,
        opener_player_name="opener",
        four_bettor_player_name="four_bettor",
    )

    opener_seat = _POSITION_TO_SEAT_6MAX[Position.UTG]
    opener = observed_state.players[opener_seat]

    assert opener.is_folded is True
    assert (
        observed_state.get_preflop_previous_action_for_seat(opener_seat)
        == ActionType.FOLD
    )
    assert observed_state.get_live_opponent_last_action_indices_before_current_turn() == (
        (_POSITION_TO_SEAT_6MAX[Position.CO], 2),
    )


def test_generate_scenario_report_preserves_percent_scale_and_action_codes(
    tmp_path: Path,
) -> None:
    """报告应保留百分比尺度, 且动作码不能压缩成首字母。"""

    output_path = tmp_path / "scenario_report.md"
    generate_scenario_report(
        output_path=output_path,
        scenario_name="测试场景",
        total_elapsed_ms=12.3,
        results=[
            {
                "combo": "UTG_open-hero_MP_3bet-CO_4bet",
                "player_name": "villain",
                "total_hands": 120,
                "vpip_pct": 16.7,
                "pfr_pct": 21.3,
                "data_level": "medium",
                "segment": "tight_aggressive",
                "elapsed_ms": 4.2,
                "prior_distribution": {
                    "F": 0.88,
                    "R6": 0.01,
                    "R19": 0.11,
                },
                "posterior_distribution": {
                    "F": 0.45,
                    "C": 0.35,
                    "R22": 0.20,
                },
            }
        ],
    )

    content = output_path.read_text(encoding="utf-8")

    assert "| 16.7% | 21.3% |" in content
    assert "1670.0%" not in content
    assert "F:88% R6:1% R19:11%" in content
    assert "F:45% C:35% R22:20%" in content


def test_comprehensive_suite_uses_all_legal_position_combinations() -> None:
    """综合画像测试必须遍历每个场景的全部合法位置组合。"""

    assert comprehensive_profiles._REPRESENTATIVE_RFI == ALL_RFI_COMBINATIONS_6MAX
    assert comprehensive_profiles._REPRESENTATIVE_3BET == ALL_3BET_COMBINATIONS_6MAX
    assert (
        comprehensive_profiles._REPRESENTATIVE_FACING_3BET
        == ALL_FACING_3BET_COMBINATIONS_6MAX
    )
    assert comprehensive_profiles._REPRESENTATIVE_4BET == ALL_4BET_COMBINATIONS_6MAX
    assert (
        comprehensive_profiles._REPRESENTATIVE_HERO_OPEN_FACING_4BET
        == ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX
    )
    assert (
        comprehensive_profiles._REPRESENTATIVE_HERO_3BET_FACING_4BET
        == ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX
    )
