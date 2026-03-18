"""真实场景: 3-Bet belief-k vs G5 对手范围 + hero 行为对比。

选取代表性 3-bet 组合, 分别用旧 belief-k 和新 G5 后验路径运行,
对比:
  1. 对手范围估算 (prior_freq → posterior_freq, 即 aggression 调整)
  2. hero 动作分布差异 (prior/posterior 各 action)

输出 CSV: data/reports/3bet_hero_range_belief_k_vs_g5.csv
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
    HeroStrategySnapshot,
    PlayerPfrRow,
    assert_valid_recommendation,
    build_3bet_state,
    build_snapshot_from_decision,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_CSV_OUTPUT_DIR: Path = Path(__file__).resolve().parents[2] / "data" / "reports"

# 代表性子集: 覆盖早 / 中 / 晚位 opener + 不同层级 3bettor
_REPRESENTATIVE_COMBOS: list[tuple[Position, Position, Position]] = [
    (Position.UTG, Position.MP, Position.BTN),  # 早位 open + 早位 3bet
    (Position.UTG, Position.BTN, Position.BB),  # 早位 open + 晚位 3bet
    (Position.CO, Position.BTN, Position.SB),  # 晚位 open + 晚位 3bet
]

# ---------------------------------------------------------------------------
# CSV 导出
# ---------------------------------------------------------------------------


def _write_comparison_csv(
    rows: list[dict[str, object]],
    output_path: Path,
) -> None:
    """将 belief-k vs G5 对比数据写入 CSV。

    Args:
        rows: 每行是一条记录 (含 path=belief_k / g5)。
        output_path: 输出文件路径。
    """
    if not rows:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[CSV] 3-Bet belief-k vs G5 对比已写入: {output_path} ({len(rows)} 行)")


def _build_row(
    *,
    combo_key: str,
    opener: str,
    three_bettor: str,
    hero: str,
    player_name: str,
    total_hands: int,
    pfr_pct: float,
    path: str,
    decision: RecommendationDecision,
) -> dict[str, object]:
    """从 RecommendationDecision 构建 CSV 行。

    Args:
        combo_key: 组合标识。
        opener: Opener 位置名。
        three_bettor: 3-bettor 位置名。
        hero: Hero 位置名。
        player_name: 对手玩家名。
        total_hands: 对手总手数。
        pfr_pct: 对手 PFR 百分比。
        path: "belief_k" 或 "g5"。
        decision: Hero 推荐决策。

    Returns:
        CSV 行字典。
    """
    row: dict[str, object] = {
        "combo": combo_key,
        "opener": opener,
        "3bettor": three_bettor,
        "hero": hero,
        "player": player_name,
        "hands": total_hands,
        "pfr_pct": pfr_pct,
        "path": path,
    }

    # 对手范围: 从 opponent_aggression_details 取 prior/posterior freq
    details = decision.opponent_aggression_details
    for i, detail in enumerate(details):
        prefix = f"opp{i}"
        row[f"{prefix}_seat"] = detail.get("seat", "")
        row[f"{prefix}_player_id"] = detail.get("player_id", "")
        row[f"{prefix}_prior_freq"] = _round_or_na(detail.get("prior_freq"))
        row[f"{prefix}_posterior_freq"] = _round_or_na(detail.get("posterior_freq"))
        row[f"{prefix}_ratio"] = _round_or_na(detail.get("ratio"))
        row[f"{prefix}_dampened_ratio"] = _round_or_na(detail.get("dampened_ratio"))

    # aggression_ratio (from notes)
    notes = decision.notes
    if "aggression_ratio=" in notes:
        ratio_text = notes.split("aggression_ratio=", maxsplit=1)[1].split(";")[0]
        row["aggression_ratio"] = float(ratio_text)
    else:
        row["aggression_ratio"] = ""

    # hero 动作分布
    all_actions = sorted(
        set(decision.prior_action_distribution) | set(decision.action_distribution)
    )
    for ac in all_actions:
        prior = decision.prior_action_distribution.get(ac, 0.0)
        posterior = decision.action_distribution.get(ac, 0.0)
        row[f"prior_{ac}"] = round(prior, 6)
        row[f"post_{ac}"] = round(posterior, 6)
        row[f"delta_{ac}"] = round(posterior - prior, 6)

    return row


def _round_or_na(val: object) -> object:
    """安全四舍五入数值, 非数值返回空字符串。

    Args:
        val: 任意值。

    Returns:
        四舍五入后的浮点数或空字符串。
    """
    if isinstance(val, (int, float)):
        return round(float(val), 6)
    return ""


# ---------------------------------------------------------------------------
# 对比输出 (stdout)
# ---------------------------------------------------------------------------


def _print_comparison_table(
    combo_key: str,
    player_name: str,
    bk_decision: RecommendationDecision,
    g5_decision: RecommendationDecision,
) -> None:
    """打印单个组合 + 玩家的 belief-k vs G5 对比。

    Args:
        combo_key: 组合标识。
        player_name: 对手玩家名。
        bk_decision: belief-k 路径的决策。
        g5_decision: G5 路径的决策。
    """
    all_actions = sorted(
        set(bk_decision.action_distribution)
        | set(g5_decision.action_distribution)
    )

    print(f"\n--- {combo_key} | {player_name} ---")

    # 对手范围比较
    print("  对手范围 (opponent aggression):")
    for label, dec in [("belief-k", bk_decision), ("g5", g5_decision)]:
        for d in dec.opponent_aggression_details:
            pid = d.get("player_id", "?")
            pf = _round_or_na(d.get("prior_freq"))
            qf = _round_or_na(d.get("posterior_freq"))
            ratio = _round_or_na(d.get("dampened_ratio"))
            print(f"    [{label}] {pid}: prior={pf} post={qf} dampened={ratio}")

    # hero 动作分布对比
    print("  Hero 动作分布 (prior → posterior):")
    print(f"    {'action':<8} {'bk_prior':>10} {'bk_post':>10} {'g5_prior':>10} {'g5_post':>10} {'bk-g5_Δ':>10}")
    for ac in all_actions:
        bk_prior = bk_decision.prior_action_distribution.get(ac, 0.0)
        bk_post = bk_decision.action_distribution.get(ac, 0.0)
        g5_prior = g5_decision.prior_action_distribution.get(ac, 0.0)
        g5_post = g5_decision.action_distribution.get(ac, 0.0)
        delta = bk_post - g5_post
        print(f"    {ac:<8} {bk_prior:10.4f} {bk_post:10.4f} {g5_prior:10.4f} {g5_post:10.4f} {delta:+10.4f}")


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_3bet_belief_k_vs_g5_comparison(
    real_scenario_engine: StrategyEngine,
    real_scenario_engine_g5: StrategyEngine,
    selected_players: list[PlayerPfrRow],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """对比 belief-k 与 G5 路径下 3-Bet 场景的对手范围和 hero 行为差异。

    选取代表性组合和所有样本玩家, 分别用两种引擎运行,
    输出对比表到 stdout 和 CSV。

    Args:
        real_scenario_engine: belief-k 路径 StrategyEngine。
        real_scenario_engine_g5: G5 路径 StrategyEngine。
        selected_players: 玩家样本。
        capsys: pytest 输出捕获。
    """
    csv_rows: list[dict[str, object]] = []
    state_version = 0

    for opener_pos, three_bettor_pos, hero_pos in _REPRESENTATIVE_COMBOS:
        combo_key = (
            f"{opener_pos.value}_open"
            f"-{three_bettor_pos.value}_3bet"
            f"-hero_{hero_pos.value}"
        )

        for player_row in selected_players:
            state_version += 1
            observed = build_3bet_state(
                hero_position=hero_pos,
                opener_position=opener_pos,
                three_bettor_position=three_bettor_pos,
                opener_player_name=player_row.player_name,
                three_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )

            # belief-k
            bk_dec = asyncio.run(
                real_scenario_engine(
                    session_id=f"bk_3bet_cmp_{combo_key}_{player_row.player_name}_{state_version}",
                    observed_state=observed,
                )
            )
            bk_rec = assert_valid_recommendation(
                bk_dec, label=f"[BK] {combo_key} {player_row.player_name}"
            )

            # G5
            state_version += 1
            observed_g5 = build_3bet_state(
                hero_position=hero_pos,
                opener_position=opener_pos,
                three_bettor_position=three_bettor_pos,
                opener_player_name=player_row.player_name,
                three_bettor_player_name=player_row.player_name,
                state_version=state_version,
            )
            g5_dec = asyncio.run(
                real_scenario_engine_g5(
                    session_id=f"g5_3bet_cmp_{combo_key}_{player_row.player_name}_{state_version}",
                    observed_state=observed_g5,
                )
            )
            g5_rec = assert_valid_recommendation(
                g5_dec, label=f"[G5] {combo_key} {player_row.player_name}"
            )

            _print_comparison_table(combo_key, player_row.player_name, bk_rec, g5_rec)

            # 构建 CSV 行
            common = {
                "combo_key": combo_key,
                "opener": opener_pos.value,
                "three_bettor": three_bettor_pos.value,
                "hero": hero_pos.value,
                "player_name": player_row.player_name,
                "total_hands": player_row.total_hands,
                "pfr_pct": player_row.pfr_pct,
            }
            csv_rows.append(
                _build_row(
                    **common,
                    path="belief_k",
                    decision=bk_rec,
                )
            )
            csv_rows.append(
                _build_row(
                    **common,
                    path="g5",
                    decision=g5_rec,
                )
            )

    # 统一列 (不同组合可能有不同 action code)
    all_keys: dict[str, None] = {}
    for r in csv_rows:
        for k in r:
            all_keys[k] = None
    for r in csv_rows:
        for k in all_keys:
            r.setdefault(k, "")

    csv_path = _CSV_OUTPUT_DIR / "3bet_hero_range_belief_k_vs_g5.csv"
    _write_comparison_csv(csv_rows, csv_path)

    # 汇总输出
    print(f"\n{'=' * 88}")
    print("3-Bet belief-k vs G5 对比汇总")
    print(f"{'=' * 88}")
    print(f"  代表性组合数: {len(_REPRESENTATIVE_COMBOS)}")
    print(f"  样本玩家数: {len(selected_players)}")
    print(f"  总行数: {len(csv_rows)}")
    print(f"  CSV: {csv_path}")

    assert len(csv_rows) == len(_REPRESENTATIVE_COMBOS) * len(selected_players) * 2
