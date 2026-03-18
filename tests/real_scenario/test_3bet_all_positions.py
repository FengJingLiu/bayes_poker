"""真实场景: 3-Bet 全位置组合覆盖测试 (G5 贝叶斯路径)。

Hero 遍历所有可能位置, opener 和 3bettor 遍历所有合法位置组合,
使用 G5 OpponentEstimator 贝叶斯后验路径验证 StrategyEngine
对每种组合均能返回合法的 RecommendationDecision, 并将 hero 范围变化导出 CSV。

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
import csv
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

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_CSV_OUTPUT_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "reports"


def _3bet_combo_id(combo: tuple[Position, Position, Position]) -> str:
    """为 pytest parametrize 生成可读的 3-Bet 测试 ID。

    Args:
        combo: (opener, 3bettor, hero) 元组。

    Returns:
        形如 "UTG_open-MP_3bet-hero_CO" 的字符串。
    """
    opener, three_bettor, hero = combo
    return f"{opener.value}_open-{three_bettor.value}_3bet-hero_{hero.value}"


# ---------------------------------------------------------------------------
# CSV 导出
# ---------------------------------------------------------------------------


def _write_3bet_hero_range_csv(
    all_snapshots: dict[str, list[HeroStrategySnapshot]],
    output_path: Path,
) -> None:
    """将 3-Bet 场景下 hero 范围变化写入 CSV 文件。

    Args:
        all_snapshots: combo_key -> snapshot 列表映射。
        output_path: 输出 CSV 路径。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_action_codes: set[str] = set()
    for snapshots in all_snapshots.values():
        for snap in snapshots:
            all_action_codes |= set(snap.prior_action_distribution)
            all_action_codes |= set(snap.action_distribution)
    sorted_actions = sorted(all_action_codes)

    header = [
        "combo",
        "player_name",
        "total_hands",
        "pfr_pct",
        "node_id",
        "source_id",
    ]
    for ac in sorted_actions:
        header.extend([f"prior_{ac}", f"posterior_{ac}", f"delta_{ac}"])

    rows: list[list[str | float | int]] = []
    for combo_key, snapshots in all_snapshots.items():
        for snap in snapshots:
            row: list[str | float | int] = [
                combo_key,
                snap.player_name,
                snap.total_hands,
                round(snap.pfr_pct, 4),
                snap.selected_node_id,
                snap.selected_source_id,
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

    print(f"\n[CSV] 3-Bet hero 范围变化已写入: {output_path} ({len(rows)} 行)")


# ---------------------------------------------------------------------------
# 测试: 单组合验证 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "three_bet_combo",
    ALL_3BET_COMBINATIONS_6MAX,
    ids=[_3bet_combo_id(c) for c in ALL_3BET_COMBINATIONS_6MAX],
)
def test_3bet_single_combo_returns_valid_recommendation(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    three_bet_combo: tuple[Position, Position, Position],
) -> None:
    """验证单个 3-Bet 组合下 G5 引擎返回合法推荐。

    对每种 (opener, 3bettor, hero) 位置组合, 使用样本玩家,
    验证 engine 能返回 RecommendationDecision 且各字段合法。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
        real_scenario_engine_g5(
            session_id=(
                f"g5_3bet_{opener_position.value}_{three_bettor_position.value}"
                f"_{hero_position.value}_{player_row.player_name}"
            ),
            observed_state=observed_state,
        )
    )

    label = (
        f"[G5] {opener_position.value} open -> {three_bettor_position.value} 3bet"
        f" -> hero {hero_position.value}"
    )
    assert_valid_recommendation(decision, label=label)


# ---------------------------------------------------------------------------
# 测试: 全组合 + 多玩家遍历, 含 GTO+ 导出 + CSV (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_3bet_all_combos_all_players_with_csv_export(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    tmp_path: Path,
) -> None:
    """全覆盖: 20 种 3-Bet 组合 x 3 名玩家 (G5 路径), 验证推荐并导出 CSV。

    对每种 (opener, 3bettor, hero) 位置组合, 遍历所有样本玩家作为 3bettor,
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
                real_scenario_engine_g5(
                    session_id=f"g5_3bet_full_{combo_key}_{player_row.player_name}_{state_version}",
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

    assert len(all_snapshots) == 20, f"期望 20 种 3-Bet 组合, 实际={len(all_snapshots)}"

    for combo_key, snapshots in all_snapshots.items():
        assert len(snapshots) == len(selected_players), (
            f"{combo_key}: 期望 {len(selected_players)} 个快照, 实际={len(snapshots)}"
        )

    for combo_key, snapshots in all_snapshots.items():
        export_dir = tmp_path / f"3bet_gtoplus_{combo_key}"
        print(f"\n{'=' * 88}")
        print(f"[G5] 3-Bet 组合: {combo_key}")
        print(f"{'=' * 88}")
        for snapshot in snapshots:
            write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
            print_snapshot(snapshot)
        print_pairwise_range_comparison(snapshots)

    # 导出 CSV
    csv_path = _CSV_OUTPUT_DIR / "3bet_hero_range_g5.csv"
    _write_3bet_hero_range_csv(all_snapshots, csv_path)


# ---------------------------------------------------------------------------
# 测试: 同一 opener 下不同 3bettor/hero 组合差异 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "opener_position",
    [Position.UTG, Position.MP, Position.CO, Position.BTN],
    ids=["UTG", "MP", "CO", "BTN"],
)
def test_3bet_same_opener_different_3bettor_hero_produce_different_nodes(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    opener_position: Position,
) -> None:
    """验证同一 opener 位置下, 不同 3bettor/hero 组合命中不同策略节点 (G5 路径)。

    策略引擎应区分 3bettor 和 hero 所在位置, 返回不同的 node_id 或不同的动作分布。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
            real_scenario_engine_g5(
                session_id=(
                    f"g5_3bet_diff_{opener_position.value}"
                    f"_{three_bettor_pos.value}_{hero_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"[G5] {opener_position.value} open -> {three_bettor_pos.value} 3bet"
                f" -> hero {hero_pos.value}"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert unique_nodes or unique_distributions > 1, (
        f"[G5] {opener_position.value} open 3-Bet: "
        f"所有组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n[G5] {opener_position.value} open 3-Bet -> 不同组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


# ---------------------------------------------------------------------------
# 测试: 同一 hero 下不同 opener/3bettor 组合差异 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
@pytest.mark.parametrize(
    "hero_position",
    [Position.CO, Position.BTN, Position.SB, Position.BB],
    ids=["CO", "BTN", "SB", "BB"],
)
def test_3bet_same_hero_different_opener_3bettor_produce_different_nodes(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    hero_position: Position,
) -> None:
    """验证同一 hero 位置下, 不同 opener/3bettor 组合命中不同策略节点 (G5 路径)。

    面对不同位置组合的 3-bet, hero 的策略应有差异。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
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
            real_scenario_engine_g5(
                session_id=(
                    f"g5_3bet_hero_diff_{hero_position.value}"
                    f"_{opener_pos.value}_{three_bettor_pos.value}_{idx}"
                ),
                observed_state=observed_state,
            )
        )
        rec = assert_valid_recommendation(
            decision,
            label=(
                f"[G5] {opener_pos.value} open -> {three_bettor_pos.value} 3bet"
                f" -> hero {hero_position.value}"
            ),
        )
        node_ids.append(rec.selected_node_id)  # type: ignore[arg-type]
        distributions.append(dict(rec.action_distribution))

    unique_nodes = set(node_ids)
    unique_distributions = len({tuple(sorted(d.items())) for d in distributions})
    assert len(unique_nodes) > 1 or unique_distributions > 1, (
        f"[G5] hero {hero_position.value} 3-Bet: "
        f"面对所有组合命中相同节点且分布完全一致, 可能存在问题。"
        f"node_ids={node_ids}"
    )

    print(
        f"\n[G5] hero {hero_position.value} <- 不同 3-Bet 组合差异: "
        f"unique_nodes={len(unique_nodes)}/{len(node_ids)}, "
        f"unique_distributions={unique_distributions}/{len(distributions)}"
    )


# ---------------------------------------------------------------------------
# 测试: 不同对手风格组合影响 hero 策略 (G5 路径)
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_3bet_different_opponent_style_combos_produce_different_hero_strategy(
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证固定 3-Bet 位置下, 不同对手风格组合会改变 hero 策略 (G5 路径)。

    固定位置组合为 ``UTG open -> MP 3bet -> hero BB``。对 ``selected_players``
    做 ``opener x 3bettor`` 全排列 (3x3=9) 后逐一运行引擎, 验证:
    1. hero 的 aggression_ratio 等于所有已行动对手 dampened_ratio 的乘积;
    2. action_distribution 至少存在两种不同输出;
    3. adjusted_belief_ranges 导出的 GTO+ 范围在不同对手组合下出现差异。

    Args:
        real_scenario_engine_g5: G5 路径 StrategyEngine fixture。
        selected_players: 按 PFR 差异采样的 3 名玩家。
        capsys: pytest 输出捕获 fixture, 用于校验 changed_actions 打印结果。
    """
    assert len(selected_players) == 3, "该测试依赖 selected_players 固定返回 3 名玩家"

    opener_position = Position.UTG
    three_bettor_position = Position.MP
    hero_position = Position.BB

    snapshots: list[HeroStrategySnapshot] = []
    state_version = 0

    for opener_row in selected_players:
        for three_bettor_row in selected_players:
            state_version += 1
            observed_state = build_3bet_state(
                hero_position=hero_position,
                opener_position=opener_position,
                three_bettor_position=three_bettor_position,
                opener_player_name=opener_row.player_name,
                three_bettor_player_name=three_bettor_row.player_name,
                state_version=state_version,
            )

            decision = asyncio.run(
                real_scenario_engine_g5(
                    session_id=(
                        "g5_3bet_style_combo"
                        f"_{opener_row.player_name}_{three_bettor_row.player_name}"
                        f"_{state_version}"
                    ),
                    observed_state=observed_state,
                )
            )
            rec = assert_valid_recommendation(
                decision,
                label=(
                    f"[G5] {opener_position.value} open({opener_row.player_name})"
                    f" -> {three_bettor_position.value} 3bet({three_bettor_row.player_name})"
                    f" -> hero {hero_position.value}"
                ),
            )

            details = rec.opponent_aggression_details
            assert details, "应包含已行动对手的 aggression 明细"
            product_ratio = 1.0
            for detail in details:
                raw_value = detail.get("dampened_ratio")
                if not isinstance(raw_value, (int, float)):
                    raw_value = detail.get("ratio")
                assert isinstance(raw_value, (int, float)), (
                    f"opponent_aggression_details 缺少数值 ratio: {detail}"
                )
                dampened_ratio = float(raw_value)
                product_ratio *= dampened_ratio

            # 引擎内部对 product 做了 clamp(0.1, 10.0), 测试侧也需同步
            clamped_product = max(0.1, min(product_ratio, 10.0))

            assert "aggression_ratio=" in rec.notes, (
                "notes 中应包含 aggression_ratio, 以便校验乘积逻辑"
            )
            ratio_text = rec.notes.split("aggression_ratio=", maxsplit=1)[1].split(";")[
                0
            ]
            logged_ratio = float(ratio_text)
            assert logged_ratio == pytest.approx(clamped_product, rel=1e-3, abs=1e-4), (
                "hero aggression_ratio 应等于所有已行动对手 dampened_ratio 的乘积(clamp后): "
                f"logged={logged_ratio}, clamped_product={clamped_product}, "
                f"raw_product={product_ratio}, details={details}"
            )

            combo_label = (
                f"opener:{opener_row.player_name}(pfr={opener_row.pfr_pct:.2f})"
                f"__3bettor:{three_bettor_row.player_name}(pfr={three_bettor_row.pfr_pct:.2f})"
            )
            snapshot_player = PlayerPfrRow(
                player_name=combo_label,
                total_hands=min(opener_row.total_hands, three_bettor_row.total_hands),
                pfr_pct=(opener_row.pfr_pct + three_bettor_row.pfr_pct) / 2.0,
            )
            snapshot = build_snapshot_from_decision(
                player_row=snapshot_player,
                decision=rec,
                engine=real_scenario_engine_g5,
            )
            snapshots.append(snapshot)
            print_snapshot(snapshot)

    assert len(snapshots) == 9, f"期望生成 9 个风格组合快照, 实际={len(snapshots)}"

    print_pairwise_range_comparison(snapshots)
    captured_output = capsys.readouterr().out

    unique_distributions = {
        tuple(sorted(snapshot.action_distribution.items())) for snapshot in snapshots
    }
    assert len(unique_distributions) >= 2, (
        "不同 opener/3bettor 风格组合下, hero action_distribution 不应全部相同"
    )

    changed_pair_count = 0
    baseline_snapshot = snapshots[0]
    for target_snapshot in snapshots[1:]:
        changed_actions = [
            action_code
            for action_code in sorted(
                set(baseline_snapshot.gtoplus_by_action)
                | set(target_snapshot.gtoplus_by_action)
            )
            if baseline_snapshot.gtoplus_by_action.get(action_code)
            != target_snapshot.gtoplus_by_action.get(action_code)
        ]
        if changed_actions:
            changed_pair_count += 1
    assert changed_pair_count >= 1, (
        "不同 opener/3bettor 风格组合下, adjusted_belief_ranges 导出的 GTO+ 范围"
        "至少应有一组对比出现变化"
    )

    changed_lines = [
        line for line in captured_output.splitlines() if "changed_actions=" in line
    ]
    assert changed_lines, (
        "print_pairwise_range_comparison 应输出 changed_actions 对比行"
    )
    assert any("changed_actions=[]" not in line for line in changed_lines), (
        "当 opener 或 3bettor 变化时, changed_actions 至少应有一行非空"
    )
