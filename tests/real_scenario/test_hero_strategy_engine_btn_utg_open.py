"""真实场景: 验证 BTN 面对 UTG open 2.5bb 的 Hero 策略输出。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngineConfig,
    build_strategy_engine,
)
from bayes_poker.strategy.strategy_engine.utg_open_ev_validation import (
    sanitize_filename,
)
from bayes_poker.table.observed_state import ObservedTableState

from .helpers import (
    PLAYER_CORE_STATS_CSV_PATH,
    PLAYER_STATS_DB_PATH,
    RUN_REAL_SCENARIO_ENV,
    STRATEGY_DB_PATH,
    HeroStrategySnapshot,
    load_gtoplus_ranges_for_decision,
    load_players_with_large_pfr_spread,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _build_btn_vs_utg_open_state(
    *, utg_player_name: str, state_version: int
) -> ObservedTableState:
    """构造 BTN 面对 UTG open 2.5bb 的 preflop 快照。

    Args:
        utg_player_name: UTG 玩家名。
        state_version: 状态版本号。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。
    """

    players = [
        Player(
            seat_index=0,
            player_id="hero_btn",
            stack=100.0,
            bet=0.0,
            position=Position.BTN,
            is_button=True,
        ),
        Player(
            seat_index=1,
            player_id="sb_player",
            stack=99.5,
            bet=0.5,
            position=Position.SB,
        ),
        Player(
            seat_index=2,
            player_id="bb_player",
            stack=99.0,
            bet=1.0,
            position=Position.BB,
        ),
        Player(
            seat_index=3,
            player_id=utg_player_name,
            stack=97.5,
            bet=2.5,
            position=Position.UTG,
        ),
        Player(
            seat_index=4,
            player_id="mp_folded_player",
            stack=100.0,
            bet=0.0,
            position=Position.MP,
            is_folded=True,
        ),
        Player(
            seat_index=5,
            player_id="co_folded_player",
            stack=100.0,
            bet=0.0,
            position=Position.CO,
            is_folded=True,
        ),
    ]

    action_history = [
        PlayerAction(
            player_index=3,
            action_type=ActionType.RAISE,
            amount=2.5,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=4,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=5,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        ),
    ]

    return ObservedTableState(
        table_id="real_scenario_btn_vs_utg_open",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id=f"real_hand_{state_version}",
        street=Street.PREFLOP,
        pot=4.0,
        btn_seat=0,
        actor_seat=0,
        hero_seat=0,
        hero_cards=("As", "Kh"),
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


@pytest.mark.large_sample
@pytest.mark.skipif(
    not STRATEGY_DB_PATH.exists(),
    reason="策略数据库不存在",
)
@pytest.mark.skipif(
    not PLAYER_STATS_DB_PATH.exists(),
    reason="玩家统计数据库不存在",
)
@pytest.mark.skipif(
    not PLAYER_CORE_STATS_CSV_PATH.exists(),
    reason="player_core_stats.csv 不存在",
)
def test_real_scenario_btn_vs_utg_open_hero_strategy_ranges(tmp_path: Path) -> None:
    """验证真实场景 Hero 策略并输出 GTO+。

    该测试会在真实数据库上执行 ``StrategyEngine``:
    - Hero 固定在 BTN。
    - 前缀动作为 UTG open 2.5bb, MP/CO fold, 轮到 Hero。
    - 从 ``player_core_stats.csv`` 中挑选 ``total_hands > 200`` 且 PFR 差异较大的玩家。
    - 对比不同玩家下 Hero 命中节点与动作范围, 并打印 GTO+ 文本。

    Args:
        tmp_path: pytest 临时目录。
    """

    if os.environ.get(RUN_REAL_SCENARIO_ENV) != "1":
        pytest.skip(f"未启用真实场景测试 (设置 {RUN_REAL_SCENARIO_ENV}=1 才运行)。")

    selected_players = load_players_with_large_pfr_spread(
        csv_path=PLAYER_CORE_STATS_CSV_PATH,
        min_hands=200,
        sample_count=3,
    )
    pfr_values = [row.pfr_pct for row in selected_players]
    assert max(pfr_values) > min(pfr_values)

    engine = build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=STRATEGY_DB_PATH,
            player_stats_db_path=PLAYER_STATS_DB_PATH,
            table_type=TableType.SIX_MAX,
            source_ids=(1, 2, 3, 4, 5),
        )
    )

    snapshots: list[HeroStrategySnapshot] = []
    for index, player_row in enumerate(selected_players, start=1):
        observed_state = _build_btn_vs_utg_open_state(
            utg_player_name=player_row.player_name,
            state_version=index,
        )
        decision = asyncio.run(
            engine(
                session_id=(
                    "real_btn_vs_utg_open_"
                    f"{sanitize_filename(player_row.player_name)}_{index}"
                ),
                observed_state=observed_state,
            )
        )

        assert isinstance(
            decision,
            RecommendationDecision,
        ), f"期望 RecommendationDecision, 实际={type(decision).__name__}"
        assert decision.selected_node_id is not None
        assert decision.selected_source_id is not None
        assert decision.sampling_random is not None
        assert 0.0 <= decision.sampling_random < 1.0
        assert decision.action_distribution
        assert pytest.approx(1.0, abs=1e-6) == sum(
            decision.action_distribution.values()
        )

        gtoplus_by_action = load_gtoplus_ranges_for_decision(
            engine=engine,
            decision=decision,
            min_strategy=0.001,
        )
        assert gtoplus_by_action

        snapshot = HeroStrategySnapshot(
            player_name=player_row.player_name,
            total_hands=player_row.total_hands,
            pfr_pct=player_row.pfr_pct,
            selected_node_id=decision.selected_node_id,
            selected_source_id=decision.selected_source_id,
            action_distribution=dict(decision.action_distribution),
            prior_action_distribution=dict(decision.prior_action_distribution),
            opponent_aggression_details=list(decision.opponent_aggression_details),
            sampling_random=decision.sampling_random,
            sampled_action_code=decision.action_code,
            gtoplus_by_action=gtoplus_by_action,
        )
        snapshots.append(snapshot)

    assert len(snapshots) == 3

    export_dir = tmp_path / "real_scenario_gtoplus_btn_vs_utg_open"
    for snapshot in snapshots:
        write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
        print_snapshot(snapshot)
    print_pairwise_range_comparison(snapshots)
