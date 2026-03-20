"""真实场景: Hero Open 后遭遇 3-Bet + 4-Bet, 行动权回到 Hero 全位置组合覆盖测试。

Hero 在各位置 open raise, 某对手 3-bet, 另一对手 4-bet, 行动权回到 Hero,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 Hero Open Facing 4-Bet 组合共 20 种 (hero_opener < 3bettor < 4bettor, 按行动顺序):
  Hero UTG open -> MP 3bet -> CO/BTN/SB/BB 4bet               (4 种)
  Hero UTG open -> CO 3bet -> BTN/SB/BB 4bet                   (3 种)
  Hero UTG open -> BTN 3bet -> SB/BB 4bet                      (2 种)
  Hero UTG open -> SB 3bet -> BB 4bet                          (1 种)
  Hero MP open  -> CO 3bet -> BTN/SB/BB 4bet                   (3 种)
  Hero MP open  -> BTN 3bet -> SB/BB 4bet                      (2 种)
  Hero MP open  -> SB 3bet -> BB 4bet                          (1 种)
  Hero CO open  -> BTN 3bet -> SB/BB 4bet                      (2 种)
  Hero CO open  -> SB 3bet -> BB 4bet                          (1 种)
  Hero BTN open -> SB 3bet -> BB 4bet                          (1 种)
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
    ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX,
    PREFLOP_ACTION_ORDER_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_hero_open_facing_4bet_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _hero_open_facing_4bet_combo_id(
    combo: tuple[Position, Position, Position],
) -> str:
    """为 pytest parametrize 生成可读的 Hero Open Facing 4-Bet 测试 ID。

    Args:
        combo: (hero_opener, 3bettor, 4bettor) 元组。

    Returns:
        形如 "hero_UTG_open-MP_3bet-CO_4bet" 的字符串。
    """
    hero_opener, three_bettor, four_bettor = combo
    return (
        f"hero_{hero_opener.value}_open"
        f"-{three_bettor.value}_3bet"
        f"-{four_bettor.value}_4bet"
    )


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_open_facing_4bet_combo",
    ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX,
    ids=[
        _hero_open_facing_4bet_combo_id(c)
        for c in ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX
    ],
)
def test_hero_open_facing_4bet_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_open_facing_4bet_combo: tuple[Position, Position, Position],
) -> None:
    """验证单个 Hero Open Facing 4-Bet 组合下 StrategyEngine 返回合法推荐。

    对每种 (hero_opener, 3bettor, 4bettor) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_open_facing_4bet_combo: (hero_opener, 3bettor, 4bettor) 元组。
    """
    hero_opener_position, three_bettor_position, four_bettor_position = (
        hero_open_facing_4bet_combo
    )
    player_row = selected_players[0]

    observed_state = build_hero_open_facing_4bet_state(
        hero_opener_position=hero_opener_position,
        three_bettor_position=three_bettor_position,
        four_bettor_position=four_bettor_position,
        three_bettor_player_name=player_row.player_name,
        four_bettor_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=(
                f"hero_open_facing_4bet_{hero_opener_position.value}"
                f"_{three_bettor_position.value}_{four_bettor_position.value}"
                f"_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"hero {hero_opener_position.value} open"
        f" -> {three_bettor_position.value} 3bet"
        f" -> {four_bettor_position.value} 4bet -> hero 决策"
    )
    assert_valid_recommendation(decision, label=label)


@pytest.mark.large_sample
def test_hero_open_facing_4bet_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 20 种 Hero Open Facing 4-Bet 组合 x 3 名玩家, 验证推荐并导出 GTO+。

    对每种 (hero_opener, 3bettor, 4bettor) 位置组合, 遍历所有样本玩家
    作为 3bettor 和 4bettor, 验证 engine 返回 RecommendationDecision,
    导出 GTO+ 范围文本, 并打印 prior vs posterior 对比。

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
        hero_opener_position,
        three_bettor_position,
        four_bettor_position,
    ) in ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX:
        combo_key = (
            f"hero_{hero_opener_position.value}_open"
            f"-{three_bettor_position.value}_3bet"
            f"-{four_bettor_position.value}_4bet"
        )
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_hero_open_facing_4bet_state(
                hero_opener_position=hero_opener_position,
                three_bettor_position=three_bettor_position,
                four_bettor_position=four_bettor_position,
                three_bettor_player_name=player_row.player_name,
                four_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=(
                        f"hero_open_facing_4bet_full_{combo_key}"
                        f"_{player_row.player_name}_{state_version}"
                    ),
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

    assert len(all_snapshots) == 20, (
        f"期望 20 种 Hero Open Facing 4-Bet 组合, 实际={len(all_snapshots)}"
    )

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"hero_open_facing_4bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"Hero Open Facing 4-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_opener_position",
    [Position.UTG, Position.MP, Position.CO],
    ids=["UTG", "MP", "CO"],
)
def test_hero_open_facing_4bet_same_hero_different_combo_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_opener_position: Position,
) -> None:
    """验证同一 hero(opener) 位置下, 不同 3bettor/4bettor 组合命中不同策略节点。

    面对不同位置组合的 3-bet + 4-bet, hero 的策略应有差异。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_opener_position: 固定的 hero(opener) 位置。
    """
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_opener_position)

    combos = [
        (three_bettor, four_bettor)
        for j, three_bettor in enumerate(
            PREFLOP_ACTION_ORDER_6MAX[hero_order + 1 :], start=hero_order + 1
        )
        for four_bettor in PREFLOP_ACTION_ORDER_6MAX[j + 1 :]
    ]
    if len(combos) < 2:
        pytest.skip(
            f"hero {hero_opener_position.value} open 仅有 "
            f"{len(combos)} 个 3bettor/4bettor 组合, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, (three_bettor_pos, four_bettor_pos) in enumerate(combos, start=1):
        observed_state = build_hero_open_facing_4bet_state(
            hero_opener_position=hero_opener_position,
            three_bettor_position=three_bettor_pos,
            four_bettor_position=four_bettor_pos,
            three_bettor_player_name=player_row.player_name,
            four_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"hero_open_facing_4bet_diff_{hero_opener_position.value}"
                    f"_{three_bettor_pos.value}_{four_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"hero {hero_opener_position.value} open"
                f" -> {three_bettor_pos.value} 3bet"
                f" -> {four_bettor_pos.value} 4bet"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_opener_position.value} open Hero Open Facing 4-Bet: "
        f"面对所有 3bettor/4bettor 组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_opener_position.value} open Hero Open Facing 4-Bet"
        f" -> 不同 3bettor/4bettor 组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
