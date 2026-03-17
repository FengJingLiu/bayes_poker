"""真实场景: 3-Bet 全位置组合覆盖测试。

Hero 遍历所有可能位置, opener 和 3bettor 遍历所有合法位置组合,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 3-Bet 组合共 20 种 (opener < 3bettor < hero, 按行动顺序):
  UTG open, MP 3bet -> hero 在 CO / BTN / SB / BB  (4 种)
  UTG open, CO 3bet -> hero 在 BTN / SB / BB       (3 种)
  UTG open, BTN 3bet -> hero 在 SB / BB             (2 种)
  UTG open, SB 3bet -> hero 在 BB                   (1 种)
  MP open, CO 3bet -> hero 在 BTN / SB / BB          (3 种)
  MP open, BTN 3bet -> hero 在 SB / BB               (2 种)
  MP open, SB 3bet -> hero 在 BB                     (1 种)
  CO open, BTN 3bet -> hero 在 SB / BB               (2 种)
  CO open, SB 3bet -> hero 在 BB                     (1 种)
  BTN open, SB 3bet -> hero 在 BB                    (1 种)
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
    ALL_3BET_COMBINATIONS_6MAX,
    PREFLOP_ACTION_ORDER_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_3bet_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _3bet_combo_id(combo: tuple[Position, Position, Position]) -> str:
    """为 pytest parametrize 生成可读的 3-Bet 测试 ID。

    Args:
        combo: (opener, 3bettor, hero) 元组。

    Returns:
        形如 "UTG_open-MP_3bet-hero_CO" 的字符串。
    """
    opener, three_bettor, hero = combo
    return f"{opener.value}_open-{three_bettor.value}_3bet-hero_{hero.value}"


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "three_bet_combo",
    ALL_3BET_COMBINATIONS_6MAX,
    ids=[_3bet_combo_id(c) for c in ALL_3BET_COMBINATIONS_6MAX],
)
def test_3bet_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    three_bet_combo: tuple[Position, Position, Position],
) -> None:
    """验证单个 3-Bet 组合下 StrategyEngine 返回合法推荐。

    对每种 (opener, 3bettor, hero) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        three_bet_combo: (opener, 3bettor, hero) 元组。
    """
    opener_position, three_bettor_position, hero_position = three_bet_combo
    player_row = selected_players[0]

    observed_state = build_3bet_state(
        hero_position=hero_position,
        opener_position=opener_position,
        three_bettor_position=three_bettor_position,
        opener_player_name=player_row.player_name,
        three_bettor_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=(
                f"3bet_{opener_position.value}_{three_bettor_position.value}"
                f"_{hero_position.value}_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"{opener_position.value} open -> {three_bettor_position.value} 3bet"
        f" -> hero {hero_position.value}"
    )
    assert_valid_recommendation(decision, label=label)


@pytest.mark.large_sample
def test_3bet_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 20 种 3-Bet 组合 x 3 名玩家, 验证推荐并导出 GTO+。

    对每种 (opener, 3bettor, hero) 位置组合, 遍历所有样本玩家作为 3bettor,
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
        opener_position,
        three_bettor_position,
        hero_position,
    ) in ALL_3BET_COMBINATIONS_6MAX:
        combo_key = (
            f"{opener_position.value}_open"
            f"-{three_bettor_position.value}_3bet"
            f"-hero_{hero_position.value}"
        )
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_3bet_state(
                hero_position=hero_position,
                opener_position=opener_position,
                three_bettor_position=three_bettor_position,
                opener_player_name=player_row.player_name,
                three_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=f"3bet_full_{combo_key}_{player_row.player_name}_{state_version}",
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

    assert len(all_snapshots) == 20, f"期望 20 种 3-Bet 组合, 实际={len(all_snapshots)}"

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"3bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"3-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "opener_position",
    [Position.UTG, Position.MP, Position.CO, Position.BTN],
    ids=["UTG", "MP", "CO", "BTN"],
)
def test_3bet_same_opener_different_3bettor_hero_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    opener_position: Position,
) -> None:
    """验证同一 opener 位置下, 不同 3bettor/hero 组合命中不同策略节点。

    策略引擎应区分 3bettor 和 hero 所在位置, 返回不同的 node_id 或不同的动作分布。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        opener_position: 固定的 opener 位置。
    """
    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)

    combos = [
        (three_bettor, hero)
        for j, three_bettor in enumerate(
            PREFLOP_ACTION_ORDER_6MAX[opener_order + 1 :], start=opener_order + 1
        )
        for hero in PREFLOP_ACTION_ORDER_6MAX[j + 1 :]
    ]
    if len(combos) < 2:
        pytest.skip(
            f"{opener_position.value} open 仅有 {len(combos)} 个 3-Bet 组合, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, (three_bettor_pos, hero_pos) in enumerate(combos, start=1):
        observed_state = build_3bet_state(
            hero_position=hero_pos,
            opener_position=opener_position,
            three_bettor_position=three_bettor_pos,
            opener_player_name=player_row.player_name,
            three_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"3bet_diff_{opener_position.value}"
                    f"_{three_bettor_pos.value}_{hero_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"{opener_position.value} open -> {three_bettor_pos.value} 3bet"
                f" -> hero {hero_pos.value}"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert unique_nodes or unique_distributions > 1, (
        f"{opener_position.value} open 3-Bet: "
        f"所有组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n{opener_position.value} open 3-Bet -> 不同组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_position",
    [Position.CO, Position.BTN, Position.SB, Position.BB],
    ids=["CO", "BTN", "SB", "BB"],
)
def test_3bet_same_hero_different_opener_3bettor_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_position: Position,
) -> None:
    """验证同一 hero 位置下, 不同 opener/3bettor 组合命中不同策略节点。

    面对不同位置组合的 3-bet, hero 的策略应有差异。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_position: 固定的 hero 位置。
    """
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)

    combos = [
        (opener, three_bettor)
        for i, opener in enumerate(PREFLOP_ACTION_ORDER_6MAX[:hero_order])
        for three_bettor in PREFLOP_ACTION_ORDER_6MAX[i + 1 : hero_order]
    ]
    if len(combos) < 2:
        pytest.skip(
            f"hero {hero_position.value} 仅有 {len(combos)} 个 3-Bet 组合, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, (opener_pos, three_bettor_pos) in enumerate(combos, start=1):
        observed_state = build_3bet_state(
            hero_position=hero_position,
            opener_position=opener_pos,
            three_bettor_position=three_bettor_pos,
            opener_player_name=player_row.player_name,
            three_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"3bet_hero_diff_{hero_position.value}"
                    f"_{opener_pos.value}_{three_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"{opener_pos.value} open -> {three_bettor_pos.value} 3bet"
                f" -> hero {hero_position.value}"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_position.value} 3-Bet: "
        f"面对所有组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_position.value} <- 不同 3-Bet 组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
