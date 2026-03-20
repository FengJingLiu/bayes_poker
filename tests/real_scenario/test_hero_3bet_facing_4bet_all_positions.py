"""真实场景: Hero 3-Bet 遭遇 4-Bet 全位置组合覆盖测试。

场景描述: 某人 open raise, Hero 3-bet, 另一人 4-bet, 行动权回到 Hero,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 Hero 3-Bet Facing 4-Bet 组合共 20 种 (opener < hero_3bettor < 4bettor, 按行动顺序):
  UTG open, Hero MP 3bet -> 4bettor 可以是 CO / BTN / SB / BB  (4 种)
  UTG open, Hero CO 3bet -> 4bettor 可以是 BTN / SB / BB        (3 种)
  UTG open, Hero BTN 3bet -> 4bettor 可以是 SB / BB              (2 种)
  UTG open, Hero SB 3bet -> 4bettor 只能是 BB                    (1 种)
  MP open, Hero CO 3bet -> 4bettor 可以是 BTN / SB / BB          (3 种)
  MP open, Hero BTN 3bet -> 4bettor 可以是 SB / BB               (2 种)
  MP open, Hero SB 3bet -> 4bettor 只能是 BB                     (1 种)
  CO open, Hero BTN 3bet -> 4bettor 可以是 SB / BB               (2 种)
  CO open, Hero SB 3bet -> 4bettor 只能是 BB                     (1 种)
  BTN open, Hero SB 3bet -> 4bettor 只能是 BB                    (1 种)
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
    ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX,
    PREFLOP_ACTION_ORDER_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_hero_3bet_facing_4bet_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)


def _combo_id(combo: tuple[Position, Position, Position]) -> str:
    """为 pytest parametrize 生成可读的 Hero 3-Bet Facing 4-Bet 测试 ID。

    Args:
        combo: (opener, hero_3bettor, 4bettor) 元组。

    Returns:
        形如 "UTG_open-hero_MP_3bet-CO_4bet" 的字符串。
    """
    opener, hero_3bettor, four_bettor = combo
    return (
        f"{opener.value}_open-hero_{hero_3bettor.value}_3bet"
        f"-{four_bettor.value}_4bet"
    )


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_3bet_facing_4bet_combo",
    ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX,
    ids=[
        _combo_id(c) for c in ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX
    ],
)
def test_hero_3bet_facing_4bet_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_3bet_facing_4bet_combo: tuple[Position, Position, Position],
) -> None:
    """验证单个 Hero 3-Bet Facing 4-Bet 组合下 StrategyEngine 返回合法推荐。

    对每种 (opener, hero_3bettor, 4bettor) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_3bet_facing_4bet_combo: (opener, hero_3bettor, 4bettor) 元组。
    """
    opener_position, hero_3bettor_position, four_bettor_position = (
        hero_3bet_facing_4bet_combo
    )
    player_row = selected_players[0]

    observed_state = build_hero_3bet_facing_4bet_state(
        opener_position=opener_position,
        hero_3bettor_position=hero_3bettor_position,
        four_bettor_position=four_bettor_position,
        opener_player_name=player_row.player_name,
        four_bettor_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=(
                f"hero_3bet_facing_4bet_{opener_position.value}"
                f"_{hero_3bettor_position.value}"
                f"_{four_bettor_position.value}"
                f"_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"{opener_position.value} open -> hero {hero_3bettor_position.value} 3bet"
        f" -> {four_bettor_position.value} 4bet -> hero 决策"
    )
    assert_valid_recommendation(decision, label=label)


@pytest.mark.large_sample
def test_hero_3bet_facing_4bet_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 20 种 Hero 3-Bet Facing 4-Bet 组合 x 全部样本玩家, 验证推荐并导出 GTO+。

    对每种 (opener, hero_3bettor, 4bettor) 位置组合, 遍历所有样本玩家
    分别作为 opener 和 4bettor, 验证 engine 返回 RecommendationDecision,
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
        opener_position,
        hero_3bettor_position,
        four_bettor_position,
    ) in ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX:
        combo_key = (
            f"{opener_position.value}_open"
            f"-hero_{hero_3bettor_position.value}_3bet"
            f"-{four_bettor_position.value}_4bet"
        )
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_hero_3bet_facing_4bet_state(
                opener_position=opener_position,
                hero_3bettor_position=hero_3bettor_position,
                four_bettor_position=four_bettor_position,
                opener_player_name=player_row.player_name,
                four_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=(
                        f"hero_3bet_facing_4bet_full_{combo_key}"
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
        f"期望 20 种 Hero 3-Bet Facing 4-Bet 组合, 实际={len(all_snapshots)}"
    )

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"hero_3bet_facing_4bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"Hero 3-Bet Facing 4-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_3bettor_position",
    [Position.MP, Position.CO, Position.BTN],
    ids=["MP", "CO", "BTN"],
)
def test_hero_3bet_facing_4bet_same_hero_different_combo_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_3bettor_position: Position,
) -> None:
    """验证同一 hero(3bettor) 位置下, 不同 opener/4bettor 组合命中不同策略节点。

    固定 hero 的 3bet 位置, 遍历所有合法的 (opener, 4bettor) 组合,
    策略引擎应区分不同前置行动序列, 返回不同的 node_id 或不同的动作分布。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_3bettor_position: 固定的 hero(3bettor) 位置。
    """
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_3bettor_position)

    combos = [
        (opener, four_bettor)
        for opener in PREFLOP_ACTION_ORDER_6MAX[:hero_order]
        for four_bettor in PREFLOP_ACTION_ORDER_6MAX[hero_order + 1 :]
    ]
    if len(combos) < 2:
        pytest.skip(
            f"hero {hero_3bettor_position.value} 3bet 仅有 "
            f"{len(combos)} 个 (opener, 4bettor) 组合, 无需对比"
        )

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, (opener_pos, four_bettor_pos) in enumerate(combos, start=1):
        observed_state = build_hero_3bet_facing_4bet_state(
            opener_position=opener_pos,
            hero_3bettor_position=hero_3bettor_position,
            four_bettor_position=four_bettor_pos,
            opener_player_name=player_row.player_name,
            four_bettor_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=(
                    f"hero_3bet_facing_4bet_diff_{hero_3bettor_position.value}"
                    f"_{opener_pos.value}_{four_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"{opener_pos.value} open -> hero {hero_3bettor_position.value} 3bet"
                f" -> {four_bettor_pos.value} 4bet"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_3bettor_position.value} 3bet Facing 4-Bet: "
        f"面对所有 opener/4bettor 组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_3bettor_position.value} 3bet Facing 4-Bet -> 不同组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
