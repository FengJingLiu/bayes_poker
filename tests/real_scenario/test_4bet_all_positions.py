"""真实场景: 4-Bet 全位置组合覆盖测试。

Hero 遍历所有可能位置, opener/3bettor/4bettor 遍历所有合法位置组合,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 4-Bet 组合共 15 种 (opener < 3bettor < 4bettor < hero, 按行动顺序):
  UTG open, MP 3bet, CO 4bet -> hero 在 BTN / SB / BB  (3 种)
  UTG open, MP 3bet, BTN 4bet -> hero 在 SB / BB       (2 种)
  UTG open, MP 3bet, SB 4bet -> hero 在 BB             (1 种)
  UTG open, CO 3bet, BTN 4bet -> hero 在 SB / BB       (2 种)
  UTG open, CO 3bet, SB 4bet -> hero 在 BB             (1 种)
  UTG open, BTN 3bet, SB 4bet -> hero 在 BB            (1 种)
  MP open, CO 3bet, BTN 4bet -> hero 在 SB / BB        (2 种)
  MP open, CO 3bet, SB 4bet -> hero 在 BB              (1 种)
  MP open, BTN 3bet, SB 4bet -> hero 在 BB             (1 种)
  CO open, BTN 3bet, SB 4bet -> hero 在 BB             (1 种)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
)

from .helpers import (
    ALL_4BET_COMBINATIONS_6MAX,
    PREFLOP_ACTION_ORDER_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_4bet_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _4bet_combo_id(
    combo: tuple[Position, Position, Position, Position],
) -> str:
    """为 pytest parametrize 生成可读的 4-Bet 测试 ID。

    Args:
        combo: (opener, 3bettor, 4bettor, hero) 元组。

    Returns:
        形如 "UTG_open-MP_3bet-CO_4bet-hero_BTN" 的字符串。
    """
    opener, three_bettor, four_bettor, hero = combo
    return (
        f"{opener.value}_open-{three_bettor.value}_3bet"
        f"-{four_bettor.value}_4bet-hero_{hero.value}"
    )


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "four_bet_combo",
    ALL_4BET_COMBINATIONS_6MAX,
    ids=[_4bet_combo_id(c) for c in ALL_4BET_COMBINATIONS_6MAX],
)
def test_4bet_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    four_bet_combo: tuple[Position, Position, Position, Position],
) -> None:
    """验证单个 4-Bet 组合下 StrategyEngine 返回合法推荐。

    对每种 (opener, 3bettor, 4bettor, hero) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        four_bet_combo: (opener, 3bettor, 4bettor, hero) 元组。
    """
    opener_position, three_bettor_position, four_bettor_position, hero_position = (
        four_bet_combo
    )
    player_row = selected_players[0]

    observed_state = build_4bet_state(
        hero_position=hero_position,
        opener_position=opener_position,
        three_bettor_position=three_bettor_position,
        four_bettor_position=four_bettor_position,
        opener_player_name=player_row.player_name,
        three_bettor_player_name=player_row.player_name,
        four_bettor_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=(
                f"4bet_{opener_position.value}_{three_bettor_position.value}"
                f"_{four_bettor_position.value}_{hero_position.value}"
                f"_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"{opener_position.value} open -> {three_bettor_position.value} 3bet"
        f" -> {four_bettor_position.value} 4bet -> hero {hero_position.value}"
    )
    assert_valid_recommendation(decision, label=label)


@pytest.mark.large_sample
def test_4bet_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 15 种 4-Bet 组合 x 3 名玩家, 验证推荐并导出 GTO+。

    对每种 (opener, 3bettor, 4bettor, hero) 位置组合, 遍历所有样本玩家
    作为 4bettor, 验证 engine 返回 RecommendationDecision, 导出 GTO+ 范围文本,
    并打印 prior vs posterior 对比。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        tmp_path: pytest 临时目录。
    """
    pfr_values = [row.pfr_pct for row in selected_players]
    assert max(pfr_values) > min(pfr_values), "样本玩家 PFR 应有差异"

    all_snapshots: dict[str, list[HeroStrategySnapshot]] = {}
    state_version = 0

    for (
        opener_position,
        three_bettor_position,
        four_bettor_position,
        hero_position,
    ) in ALL_4BET_COMBINATIONS_6MAX:
        combo_key = (
            f"{opener_position.value}_open"
            f"-{three_bettor_position.value}_3bet"
            f"-{four_bettor_position.value}_4bet"
            f"-hero_{hero_position.value}"
        )
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_4bet_state(
                hero_position=hero_position,
                opener_position=opener_position,
                three_bettor_position=three_bettor_position,
                four_bettor_position=four_bettor_position,
                opener_player_name=player_row.player_name,
                three_bettor_player_name=player_row.player_name,
                four_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=f"4bet_full_{combo_key}_{player_row.player_name}_{state_version}",
                    observed_state=observed_state,
                )
            )

            label = f"{combo_key} player={player_row.player_name}"
            rec = assert_valid_recommendation(decision, label=label)

            snapshot = build_snapshot_from_decision(
                player_row=player_row,
                decision=rec,
                engine=real_scenario_engine,
            )
            combo_snapshots.append(snapshot)

        all_snapshots[combo_key] = combo_snapshots

    assert len(all_snapshots) == 15, f"期望 15 种 4-Bet 组合, 实际={len(all_snapshots)}"

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"4bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"4-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_position",
    [Position.BTN, Position.SB, Position.BB],
    ids=["BTN", "SB", "BB"],
)
def test_4bet_same_hero_different_combo_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_position: Position,
) -> None:
    """验证同一 hero 位置下, 不同 opener/3bettor/4bettor 组合命中不同策略节点。

    面对不同位置组合的 4-bet, hero 的策略应有差异。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_position: 固定的 hero 位置。
    """
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)

    combos = [
        (opener, three_bettor, four_bettor)
        for i, opener in enumerate(PREFLOP_ACTION_ORDER_6MAX[:hero_order])
        for j, three_bettor in enumerate(
            PREFLOP_ACTION_ORDER_6MAX[i + 1 : hero_order], start=i + 1
        )
        for four_bettor in PREFLOP_ACTION_ORDER_6MAX[j + 1 : hero_order]
    ]
    if len(combos) < 2:
        pytest.skip(
            f"hero {hero_position.value} 仅有 {len(combos)} 个 4-Bet 组合, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, (opener_pos, three_bettor_pos, four_bettor_pos) in enumerate(
        combos, start=1
    ):
        observed_state = build_4bet_state(
            hero_position=hero_position,
            opener_position=opener_pos,
            three_bettor_position=three_bettor_pos,
            four_bettor_position=four_bettor_pos,
            opener_player_name=player_row.player_name,
            three_bettor_player_name=player_row.player_name,
            four_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"4bet_hero_diff_{hero_position.value}"
                    f"_{opener_pos.value}_{three_bettor_pos.value}"
                    f"_{four_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"{opener_pos.value} open -> {three_bettor_pos.value} 3bet"
                f" -> {four_bettor_pos.value} 4bet -> hero {hero_position.value}"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_position.value} 4-Bet: "
        f"面对所有组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_position.value} <- 不同 4-Bet 组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
