"""真实场景: RFI (Raise First In) 全位置组合覆盖测试 (G5 贝叶斯路径)。

Hero 遍历所有可能位置, 对手遍历所有可能位置进行 RFI open,
使用 G5 OpponentEstimator 贝叶斯后验路径验证 StrategyEngine
对每种组合均能返回合法的 RecommendationDecision, 并将 hero 范围变化导出 CSV。

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
import csv
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
# 常量
# ---------------------------------------------------------------------------

_CSV_OUTPUT_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "reports"

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
# CSV 导出
# ---------------------------------------------------------------------------


def _write_hero_range_csv(
    all_snapshots: dict[str, list[HeroStrategySnapshot]],
    output_path: Path,
) -> None:
    """将 hero 范围变化写入 CSV 文件。

    每行包含: 位置组合, 对手信息, 各动作的 prior/posterior/delta。

    Args:
        all_snapshots: combo_key -> snapshot 列表映射。
        output_path: 输出 CSV 路径。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 收集所有出现过的动作码
    all_action_codes: set[str] = set()
    for snapshots in all_snapshots.values():
        for snap in snapshots:
            all_action_codes |= set(snap.prior_action_distribution)
            all_action_codes |= set(snap.action_distribution)
    sorted_actions = sorted(all_action_codes)

    header = [
        "combo",
        "opener_position",
        "hero_position",
        "player_name",
        "total_hands",
        "pfr_pct",
        "node_id",
        "source_id",
        "source_kind",
    ]
    for ac in sorted_actions:
        header.extend([f"prior_{ac}", f"posterior_{ac}", f"delta_{ac}"])

    rows: list[list[str | float | int]] = []
    for combo_key, snapshots in all_snapshots.items():
        parts = combo_key.split("-hero_")
        opener_pos = parts[0].replace("_open", "") if len(parts) == 2 else combo_key
        hero_pos = parts[1] if len(parts) == 2 else ""

        for snap in snapshots:
            row: list[str | float | int] = [
                combo_key,
                opener_pos,
                hero_pos,
                snap.player_name,
                snap.total_hands,
                round(snap.pfr_pct, 4),
                snap.selected_node_id,
                snap.selected_source_id,
                _extract_source_kind(snap),
            ]
            for ac in sorted_actions:
                prior = snap.prior_action_distribution.get(ac, 0.0)
                posterior = snap.action_distribution.get(ac, 0.0)
                row.extend([
                    round(prior, 6),
                    round(posterior, 6),
                    round(posterior - prior, 6),
                ])
            rows.append(row)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"\n[CSV] Hero 范围变化已写入: {output_path} ({len(rows)} 行)")


def _extract_source_kind(snap: HeroStrategySnapshot) -> str:
    """从 opponent_aggression_details 中提取 source_kind。

    Args:
        snap: Hero 策略快照。

    Returns:
        source_kind 字符串, 不存在时返回 "unknown"。
    """
    for d in snap.opponent_aggression_details:
        kind = d.get("source_kind")
        if kind is not None:
            return str(kind)
    return "unknown"


# ---------------------------------------------------------------------------
# 测试: 单组合验证 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "rfi_combo",
    ALL_RFI_COMBINATIONS_6MAX,
    ids=[_rfi_combo_id(c) for c in ALL_RFI_COMBINATIONS_6MAX],
)
def test_rfi_single_combo_returns_valid_recommendation(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    rfi_combo: tuple[Position, Position],
) -> None:
    """验证单个 RFI 组合下 G5 引擎返回合法推荐。

    对每种 (opener, hero) 位置组合, 使用第一个样本玩家作为 opener,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
        real_scenario_engine_g5(
            session_id=f"g5_rfi_{opener_position.value}_{hero_position.value}_{player_row.player_name}",
            observed_state=observed_state,
        )
    )

    label = f"[G5] {opener_position.value} open -> hero {hero_position.value}"
    assert_valid_recommendation(decision, label=label)


# ---------------------------------------------------------------------------
# 测试: 全组合 + 多玩家遍历, 含 GTO+ 导出 + CSV 输出 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_rfi_all_combos_all_players_with_csv_export(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 15 种 RFI 组合 x 3 名玩家 (G5 路径), 验证推荐并导出 CSV。

    对每种 (opener, hero) 位置组合, 遍历所有样本玩家作为 opener,
    验证 engine 返回 RecommendationDecision, 导出 GTO+ 范围文本,
    打印 prior vs posterior 对比, 并将全部 hero 范围变化写入 CSV。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
                real_scenario_engine_g5(
                    session_id=f"g5_rfi_full_{combo_key}_{player_row.player_name}_{state_version}",
                    observed_state=observed_state,
                )
            )

            label = f"[G5] {combo_key} player={player_row.player_name}"
            rec = assert_valid_recommendation(decision, label=label)

            snapshot = build_snapshot_from_decision(
                player_row=player_row,
                decision=rec,
                engine=real_scenario_engine_g5,
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
        print(f"[G5] RFI 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)

    # 导出 hero 范围变化 CSV
    csv_path = _CSV_OUTPUT_DIR / "rfi_hero_range_g5.csv"
    _write_hero_range_csv(all_snapshots, csv_path)


# ---------------------------------------------------------------------------
# 测试: 验证同一 opener 位置下不同 hero 位置的策略差异 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "opener_position",
    [Position.UTG, Position.MP, Position.CO, Position.BTN],
    ids=["UTG", "MP", "CO", "BTN"],
)
def test_rfi_same_opener_different_hero_positions_produce_different_nodes(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    opener_position: Position,
) -> None:
    """验证同一 opener 位置下, 不同 hero 位置命中不同策略节点 (G5 路径)。

    策略引擎应区分 hero 所在位置, 返回不同的 node_id 或不同的动作分布。
    同一 opener 对应多个 hero 位置时, 至少应有部分差异。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
            real_scenario_engine_g5(
                session_id=f"g5_rfi_diff_{opener_position.value}_{hero_position.value}_{idx}",
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=f"[G5] {opener_position.value} open -> hero {hero_position.value}",
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    # 至少有部分 hero 位置命中不同节点或产生不同分布
    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert unique_nodes or unique_distributions > 1, (
        f"[G5] {opener_position.value} open: "
        f"所有 hero 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n[G5] {opener_position.value} open -> hero 位置差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


# ---------------------------------------------------------------------------
# 测试: 验证同一 hero 位置下不同 opener 位置的策略差异 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_position",
    [Position.CO, Position.BTN, Position.SB, Position.BB],
    ids=["CO", "BTN", "SB", "BB"],
)
def test_rfi_same_hero_different_opener_positions_produce_different_nodes(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_position: Position,
) -> None:
    """验证同一 hero 位置下, 不同 opener 位置命中不同策略节点 (G5 路径)。

    面对不同位置的 open, hero 的 GTO 策略应有差异。
    例如 BTN 面对 UTG open vs CO open, 动作分布应不同。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
            real_scenario_engine_g5(
                session_id=f"g5_rfi_hero_diff_{hero_position.value}_{opener_position.value}_{idx}",
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=f"[G5] {opener_position.value} open -> hero {hero_position.value}",
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    # 面对不同位置 open, hero 策略应有差异
    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"[G5] hero {hero_position.value}: "
        f"面对所有 opener 位置命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n[G5] hero {hero_position.value} <- 不同 opener 差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )
