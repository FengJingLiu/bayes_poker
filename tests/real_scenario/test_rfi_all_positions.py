"""真实场景: RFI (Raise First In) 全位置组合覆盖测试。

Hero 遍历所有可能位置, 对手遍历所有可能位置进行 RFI open,
验证 StrategyEngine 对每种组合均能返回合法的 RecommendationDecision。

6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
合法 RFI 组合共 15 种 (opener 必须在 hero 之前行动):
  UTG open -> hero 在 MP / CO / BTN / SB / BB (5 种)
  MP  open -> hero 在 CO / BTN / SB / BB      (4 种)
  CO  open -> hero 在 BTN / SB / BB           (3 种)
  BTN open -> hero 在 SB / BB                 (2 种)
  SB  open -> hero 在 BB                      (1 种)
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
    ALL_RFI_COMBINATIONS_6MAX,
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_rfi_state,
    build_snapshot_from_decision,
    load_gtoplus_ranges_for_decision,
    print_pairwise_range_comparison,
    print_snapshot,
    write_gtoplus_exports,
)

# ---------------------------------------------------------------------------
# parametrize ID 生成
# ---------------------------------------------------------------------------


def _rfi_combo_id(combo: tuple[Position, Position]) -> str:
    """为 pytest parametrize 生成可读的测试 ID。

    Args:
        combo: (opener_position, hero_position) 元组。

    Returns:
        形如 "UTG_open-hero_BTN" 的字符串。
    """
    opener, hero = combo
    return f"{opener.value}_open-hero_{hero.value}"


# ---------------------------------------------------------------------------
# 测试: 单组合验证
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "rfi_combo",
    ALL_RFI_COMBINATIONS_6MAX,
    ids=[_rfi_combo_id(c) for c in ALL_RFI_COMBINATIONS_6MAX],
)
def test_rfi_single_combo_returns_valid_recommendation(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    rfi_combo: tuple[Position, Position],
) -> None:
    """验证单个 RFI 组合下 StrategyEngine 返回合法推荐。

    对每种 (opener, hero) 位置组合, 使用第一个样本玩家作为 opener,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        rfi_combo: (opener_position, hero_position) 元组。
    """

    opener_position, hero_position = rfi_combo
    player_row = selected_players[0]

    observed_state = build_rfi_state(
        hero_position=hero_position,
        opener_position=opener_position,
        opener_player_name=player_row.player_name,
    )

    decision = asyncio.run(
        real_scenario_engine(
            session_id=f"rfi_{opener_position.value}_{hero_position.value}_{player_row.player_name}",
            observed_state=observed_state,
        )
    )

    label = f"{opener_position.value} open -> hero {hero_position.value}"
    assert_valid_recommendation(decision, label=label)


# ---------------------------------------------------------------------------
# 测试: 全组合 + 多玩家遍历, 含 GTO+ 导出
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_rfi_all_combos_all_players_with_gtoplus_export(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 15 种 RFI 组合 x 3 名玩家, 验证推荐并导出 GTO+。

    对每种 (opener, hero) 位置组合, 遍历所有样本玩家作为 opener,
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

    for opener_position, hero_position in ALL_RFI_COMBINATIONS_6MAX:
        combo_key = f"{opener_position.value}_open-hero_{hero_position.value}"
        combo_snapshots: list[HeroStrategySnapshot] = []

        for player_row in selected_players:
            state_version += 1
            observed_state = build_rfi_state(
                hero_position=hero_position,
                opener_position=opener_position,
                opener_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine(
                    session_id=f"rfi_full_{combo_key}_{player_row.player_name}_{state_version}",
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

    # 验证全部 15 种组合都有结果
    assert len(all_snapshots) == 15, f"期望 15 种 RFI 组合, 实际={len(all_snapshots)}"

    # 每种组合应有 3 个快照 (对应 3 名样本玩家)
    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    # 导出 GTO+ 文本并打印
    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"rfi_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"RFI 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)


# ---------------------------------------------------------------------------
# 测试: 验证同一 opener 位置下不同 hero 位置的策略差异
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "opener_position",
    [Position.UTG, Position.MP, Position.CO, Position.BTN],
    ids=["UTG", "MP", "CO", "BTN"],
)
def test_rfi_same_opener_different_hero_positions_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    opener_position: Position,
) -> None:
    """验证同一 opener 位置下, 不同 hero 位置命中不同策略节点。

    策略引擎应区分 hero 所在位置, 返回不同的 node_id 或不同的动作分布。
    同一 opener 对应多个 hero 位置时, 至少应有部分差异。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        opener_position: 固定的 opener 位置。
    """

    from .helpers import PREFLOP_ACTION_ORDER_6MAX

    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    hero_positions = PREFLOP_ACTION_ORDER_6MAX[opener_order + 1 :]
    if len(hero_positions) < 2:
        pytest.skip(f"{opener_position.value} open 仅有 1 个 hero 位置, 无需对比")

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, hero_position in enumerate(hero_positions, start=1):
        observed_state = build_rfi_state(
            hero_position=hero_position,
            opener_position=opener_position,
            opener_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=f"rfi_diff_{opener_position.value}_{hero_position.value}_{idx}",
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=f"{opener_position.value} open -> hero {hero_position.value}",
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    # 至少有部分 hero 位置命中不同节点或产生不同分布
    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert unique_nodes or unique_distributions > 1, (
        f"{opener_position.value} open: "
        f"所有 hero 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n{opener_position.value} open -> hero 位置差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


# ---------------------------------------------------------------------------
# 测试: 验证同一 hero 位置下不同 opener 位置的策略差异
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_position",
    [Position.CO, Position.BTN, Position.SB, Position.BB],
    ids=["CO", "BTN", "SB", "BB"],
)
def test_rfi_same_hero_different_opener_positions_produce_different_nodes(
    real_scenario_engine: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_position: Position,
) -> None:
    """验证同一 hero 位置下, 不同 opener 位置命中不同策略节点。

    面对不同位置的 open, hero 的 GTO 策略应有差异。
    例如 BTN 面对 UTG open vs CO open, 动作分布应不同。

    Args:
        real_scenario_engine: 真实场景 StrategyEngine fixture。
        selected_players: 玩家样本 fixture。
        hero_position: 固定的 hero 位置。
    """

    from .helpers import PREFLOP_ACTION_ORDER_6MAX

    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)
    opener_positions = PREFLOP_ACTION_ORDER_6MAX[:hero_order]
    if len(opener_positions) < 2:
        pytest.skip(f"hero {hero_position.value} 仅有 1 个 opener 位置, 无需对比")

    player_row = selected_players[0]
    node_ids: list[int] = []
    distributions: list[dict[str, float]] = []

    for idx, opener_position in enumerate(opener_positions, start=1):
        observed_state = build_rfi_state(
            hero_position=hero_position,
            opener_position=opener_position,
            opener_player_name=player_row.player_name,
            state_version=idx,
        )
        decision = asyncio.run(
            real_scenario_engine(
                session_id=f"rfi_hero_diff_{hero_position.value}_{opener_position.value}_{idx}",
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=f"{opener_position.value} open -> hero {hero_position.value}",
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    # 面对不同位置 open, hero 策略应有差异
    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"hero {hero_position.value}: "
        f"面对所有 opener 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\nhero {hero_position.value} <- 不同 opener 差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
