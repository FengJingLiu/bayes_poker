"""真实场景: Hero 作为 opener 遭遇 3-Bet 全位置组合覆盖测试。

Hero 在各位置 open raise, 对手在后位 3-bet, 行动权回到 Hero,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 Facing 3-Bet 组合共 15 种 (hero_opener < 3bettor, 按行动顺序):
  Hero UTG open -> 3bettor 可以是 MP / CO / BTN / SB / BB  (5 种)
  Hero MP open  -> 3bettor 可以是 CO / BTN / SB / BB        (4 种)
  Hero CO open  -> 3bettor 可以是 BTN / SB / BB              (3 种)
  Hero BTN open -> 3bettor 可以是 SB / BB                    (2 种)
  Hero SB open  -> 3bettor 只能是 BB                         (1 种)
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
    ALL_FACING_3BET_COMBINATIONS_6MAX,
    PREFLOP_ACTION_ORDER_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_facing_3bet_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _facing_3bet_combo_id(combo: tuple[Position, Position]) -> str:
    """为 pytest parametrize 生成可读的 Facing 3-Bet 测试 ID。

    Args:
        combo: (hero_opener, 3bettor) 元组。

    Returns:
        形如 "hero_UTG_open-MP_3bet" 的字符串。
    """
    hero_opener, three_bettor = combo
    return f"hero_{hero_opener.value}_open-{three_bettor.value}_3bet"


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "facing_3bet_combo",
    ALL_FACING_3BET_COMBINATIONS_6MAX,
    ids=[_facing_3bet_combo_id(c) for c in ALL_FACING_3BET_COMBINATIONS_6MAX],
)
def test_facing_3bet_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    facing_3bet_combo: tuple[Position, Position],
) -> None:
    """验证单个 Facing 3-Bet 组合下 StrategyEngine 返回合法推荐。

    对每种 (hero_opener, 3bettor) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        facing_3bet_combo: (hero_opener, 3bettor) 元组。
    """
    hero_opener_position, three_bettor_position = facing_3bet_combo
    player_row = selected_players[0]

    observed_state = build_facing_3bet_state(
        hero_opener_position=hero_opener_position,
        three_bettor_position=three_bettor_position,
        three_bettor_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=(
                f"facing_3bet_{hero_opener_position.value}"
                f"_{three_bettor_position.value}_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"hero {hero_opener_position.value} open"
        f" -> {three_bettor_position.value} 3bet -> hero 决策"
    )
    assert_valid_recommendation(decision, label=label)


@pytest.mark.large_sample
def test_facing_3bet_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 15 种 Facing 3-Bet 组合 x 3 名玩家, 验证推荐并导出 GTO+。

    对每种 (hero_opener, 3bettor) 位置组合, 遍历所有样本玩家作为 3bettor,
    验证 engine 返回 RecommendationDecision, 导出 GTO+ 范围文本,
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
        hero_opener_position,
        three_bettor_position,
    ) in ALL_FACING_3BET_COMBINATIONS_6MAX:
        combo_key = (
            f"hero_{hero_opener_position.value}_open-{three_bettor_position.value}_3bet"
        )
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_facing_3bet_state(
                hero_opener_position=hero_opener_position,
                three_bettor_position=three_bettor_position,
                three_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=f"facing_3bet_full_{combo_key}_{player_row.player_name}_{state_version}",
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

    assert len(all_snapshots) == 15, (
        f"期望 15 种 Facing 3-Bet 组合, 实际={len(all_snapshots)}"
    )

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"facing_3bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"Facing 3-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_opener_position",
    [Position.UTG, Position.MP, Position.CO, Position.BTN],
    ids=["UTG", "MP", "CO", "BTN"],
)
def test_facing_3bet_same_hero_different_3bettor_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_opener_position: Position,
) -> None:
    """验证同一 hero(opener) 位置下, 不同 3bettor 位置命中不同策略节点。

    策略引擎应区分 3bettor 所在位置, 返回不同的 node_id 或不同的动作分布。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_opener_position: 固定的 hero(opener) 位置。
    """
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_opener_position)

    three_bettor_positions = PREFLOP_ACTION_ORDER_6MAX[hero_order + 1 :]
    if len(three_bettor_positions) < 2:
        pytest.skip(
            f"hero {hero_opener_position.value} open 仅有 "
            f"{len(three_bettor_positions)} 个 3bettor 位置, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, three_bettor_pos in enumerate(three_bettor_positions, start=1):
        observed_state = build_facing_3bet_state(
            hero_opener_position=hero_opener_position,
            three_bettor_position=three_bettor_pos,
            three_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"facing_3bet_diff_{hero_opener_position.value}"
                    f"_{three_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"hero {hero_opener_position.value} open"
                f" -> {three_bettor_pos.value} 3bet"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_opener_position.value} open Facing 3-Bet: "
        f"面对所有 3bettor 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_opener_position.value} open Facing 3-Bet -> 不同 3bettor 差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "three_bettor_position",
    [Position.MP, Position.CO, Position.BTN, Position.SB, Position.BB],
    ids=["MP", "CO", "BTN", "SB", "BB"],
)
def test_facing_3bet_same_3bettor_different_hero_opener_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    three_bettor_position: Position,
) -> None:
    """验证同一 3bettor 位置下, 不同 hero(opener) 位置命中不同策略节点。

    同一个 3bettor 位置, hero 从不同位置 open 后遭遇 3bet,
    策略应有差异。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        three_bettor_position: 固定的 3bettor 位置。
    """
    three_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(three_bettor_position)

    hero_opener_positions = PREFLOP_ACTION_ORDER_6MAX[:three_bettor_order]
    if len(hero_opener_positions) < 2:
        pytest.skip(
            f"3bettor {three_bettor_position.value} 仅有 "
            f"{len(hero_opener_positions)} 个 hero(opener) 位置, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, hero_opener_pos in enumerate(hero_opener_positions, start=1):
        observed_state = build_facing_3bet_state(
            hero_opener_position=hero_opener_pos,
            three_bettor_position=three_bettor_position,
            three_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"facing_3bet_hero_diff_{three_bettor_position.value}"
                    f"_{hero_opener_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"hero {hero_opener_pos.value} open"
                f" -> {three_bettor_position.value} 3bet"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"3bettor {three_bettor_position.value} Facing 3-Bet: "
        f"不同 hero(opener) 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n3bettor {three_bettor_position.value} <- 不同 hero(opener) 位置差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
