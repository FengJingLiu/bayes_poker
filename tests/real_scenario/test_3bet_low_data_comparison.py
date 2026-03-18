"""真实场景: 数据不足玩家 3-Bet 对手范围 belief-k vs G5 对比。

从 player_core_stats.csv 按手数分层 (10/50/200/1000+) 选取真实玩家,
在 UTG open + BTN 3bet → hero BB 场景下, 对比两种后验路径对
**3-bet 对手 (两次 raise)** 范围的判断差异:
  - opener: 做了 1 次 raise (open)
  - 3bettor: 做了 re-raise (3bet) — 本测试重点关注

输出:
  - stdout: 逐玩家对手范围 + hero 行为对比表
  - CSV: data/reports/3bet_low_data_belief_k_vs_g5.csv
"""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
)

from .helpers import (
    PLAYER_CORE_STATS_CSV_PATH,
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

# 固定场景: UTG open, BTN 3bet, hero BB
_OPENER = Position.UTG
_THREE_BETTOR = Position.BTN
_HERO = Position.BB

# 手数分层区间: (label, min_hands_exclusive, max_hands_inclusive)
_HAND_TIERS: list[tuple[str, int, int]] = [
    ("tier_10", 5, 15),
    ("tier_50", 30, 70),
    ("tier_200", 150, 300),
    ("tier_1000", 800, 2000),
]

# 每层采样数
_SAMPLES_PER_TIER = 3


# ---------------------------------------------------------------------------
# 玩家加载
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TieredPlayer:
    """分层玩家信息。

    Attributes:
        tier: 所属手数层级标签。
        player: 玩家统计行。
    """

    tier: str
    player: PlayerPfrRow


def _load_tiered_players(csv_path: Path) -> list[TieredPlayer]:
    """按手数分层从 CSV 加载玩家样本。

    每个层级中按 PFR 排序后等距采样, 保证 PFR 分布多样性。

    Args:
        csv_path: player_core_stats.csv 路径。

    Returns:
        按层级排列的玩家列表。
    """
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    result: list[TieredPlayer] = []

    for tier_label, min_h, max_h in _HAND_TIERS:
        candidates: list[PlayerPfrRow] = []
        for row in rows:
            table_type = (row.get("table_type") or "").strip().upper()
            if table_type != "SIX_MAX":
                continue
            name = (row.get("player_name") or "").strip()
            if not name or name.lower().startswith("aggregated_"):
                continue

            try:
                hands = int(float((row.get("total_hands") or "0").strip()))
            except ValueError:
                continue
            if not (min_h < hands <= max_h):
                continue

            pfr_raw = (row.get("pfr_pct") or "").strip().rstrip("%")
            if not pfr_raw or pfr_raw.upper() == "N/A":
                continue
            try:
                pfr = float(pfr_raw)
            except ValueError:
                continue

            candidates.append(
                PlayerPfrRow(player_name=name, total_hands=hands, pfr_pct=pfr)
            )

        if len(candidates) < _SAMPLES_PER_TIER:
            pytest.skip(
                f"tier={tier_label} 可用玩家不足: "
                f"need={_SAMPLES_PER_TIER}, have={len(candidates)}"
            )

        # 按 PFR 排序后等距采样
        candidates.sort(key=lambda p: (p.pfr_pct, -p.total_hands, p.player_name))
        step = max(1, len(candidates) // _SAMPLES_PER_TIER)
        for i in range(_SAMPLES_PER_TIER):
            idx = min(i * step, len(candidates) - 1)
            result.append(TieredPlayer(tier=tier_label, player=candidates[idx]))

    return result


# ---------------------------------------------------------------------------
# CSV 导出
# ---------------------------------------------------------------------------


def _write_low_data_csv(
    rows: list[dict[str, object]],
    output_path: Path,
) -> None:
    """写入对比 CSV。

    Args:
        rows: CSV 行列表。
        output_path: 输出路径。
    """
    if not rows:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 统一列
    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    for r in rows:
        for k in all_keys:
            r.setdefault(k, "")

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[CSV] 低数据对比已写入: {output_path} ({len(rows)} 行)")


def _build_csv_row(
    *,
    tier: str,
    player: PlayerPfrRow,
    path_label: str,
    decision: RecommendationDecision,
) -> dict[str, object]:
    """从决策构建 CSV 行。

    Args:
        tier: 手数层级标签。
        player: 对手玩家行。
        path_label: "belief_k" 或 "g5"。
        decision: Hero 推荐决策。

    Returns:
        CSV 行字典。
    """
    row: dict[str, object] = {
        "tier": tier,
        "player_name": player.player_name,
        "total_hands": player.total_hands,
        "pfr_pct": round(player.pfr_pct, 2),
        "path": path_label,
    }

    # 对手范围明细
    for i, detail in enumerate(decision.opponent_aggression_details):
        prefix = f"opp{i}"
        row[f"{prefix}_player_id"] = detail.get("player_id", "")
        row[f"{prefix}_prior_freq"] = _safe_round(detail.get("prior_freq"))
        row[f"{prefix}_posterior_freq"] = _safe_round(detail.get("posterior_freq"))
        row[f"{prefix}_ratio"] = _safe_round(detail.get("ratio"))
        row[f"{prefix}_dampened_ratio"] = _safe_round(detail.get("dampened_ratio"))

    # aggression_ratio
    notes = decision.notes
    if "aggression_ratio=" in notes:
        row["aggression_ratio"] = float(
            notes.split("aggression_ratio=", maxsplit=1)[1].split(";")[0]
        )
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


def _safe_round(val: object) -> object:
    """安全四舍五入。

    Args:
        val: 任意值。

    Returns:
        四舍五入后的浮点数或空字符串。
    """
    if isinstance(val, (int, float)):
        return round(float(val), 6)
    return ""


# ---------------------------------------------------------------------------
# stdout 打印
# ---------------------------------------------------------------------------


def _print_opponent_range_comparison(
    tier: str,
    player: PlayerPfrRow,
    bk_dec: RecommendationDecision,
    g5_dec: RecommendationDecision,
) -> None:
    """打印单个玩家的对手范围和 hero 行为对比。

    Args:
        tier: 手数层级。
        player: 对手玩家。
        bk_dec: belief-k 决策。
        g5_dec: G5 决策。
    """
    print(
        f"\n--- {tier} | {player.player_name} "
        f"(hands={player.total_hands}, pfr={player.pfr_pct:.1f}%) ---"
    )

    # 对手范围
    print("  对手范围 (opener=UTG raise, 3bettor=BTN re-raise):")
    for label, dec in [("belief-k", bk_dec), ("g5    ", g5_dec)]:
        for d in dec.opponent_aggression_details:
            pid = d.get("player_id", "?")
            pf = _safe_round(d.get("prior_freq"))
            qf = _safe_round(d.get("posterior_freq"))
            ratio = _safe_round(d.get("ratio"))
            dampened = _safe_round(d.get("dampened_ratio"))
            print(
                f"    [{label}] {pid}: "
                f"prior={pf} → post={qf}, "
                f"ratio={ratio}, dampened={dampened}"
            )

    # hero 动作
    all_actions = sorted(
        set(bk_dec.action_distribution) | set(g5_dec.action_distribution)
    )
    print("  Hero 动作分布:")
    print(
        f"    {'action':<8} {'bk_prior':>10} {'bk_post':>10} "
        f"{'g5_prior':>10} {'g5_post':>10} {'Δ(bk-g5)':>10}"
    )
    for ac in all_actions:
        bkp = bk_dec.prior_action_distribution.get(ac, 0.0)
        bkq = bk_dec.action_distribution.get(ac, 0.0)
        g5p = g5_dec.prior_action_distribution.get(ac, 0.0)
        g5q = g5_dec.action_distribution.get(ac, 0.0)
        print(
            f"    {ac:<8} {bkp:10.4f} {bkq:10.4f} "
            f"{g5p:10.4f} {g5q:10.4f} {bkq - g5q:+10.4f}"
        )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


@pytest.mark.large_sample
def test_3bet_low_data_opponent_range_belief_k_vs_g5(
    real_scenario_engine: StrategyEngine,
    real_scenario_engine_g5: StrategyEngine,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """对比数据不足玩家在 3-Bet 场景下 belief-k vs G5 的对手范围判断。

    按手数分 4 层 (10/50/200/1000+), 每层 3 名玩家,
    同时作为 opener 和 3bettor, 对比两种路径的:
      1. 对手 prior/posterior freq 和 ratio (重点: 3bettor 那一行)
      2. hero 动作分布差异

    Args:
        real_scenario_engine: belief-k 路径引擎。
        real_scenario_engine_g5: G5 路径引擎。
        capsys: pytest 输出捕获。
    """
    tiered_players = _load_tiered_players(PLAYER_CORE_STATS_CSV_PATH)
    csv_rows: list[dict[str, object]] = []
    state_ver = 0

    print(f"\n{'=' * 88}")
    print(
        f"3-Bet 低数据对手范围对比: {_OPENER.value} open → "
        f"{_THREE_BETTOR.value} 3bet → hero {_HERO.value}"
    )
    print(f"分层: {[t[0] for t in _HAND_TIERS]}, 每层 {_SAMPLES_PER_TIER} 名玩家")
    print(f"{'=' * 88}")

    for tp in tiered_players:
        state_ver += 1
        observed = build_3bet_state(
            hero_position=_HERO,
            opener_position=_OPENER,
            three_bettor_position=_THREE_BETTOR,
            opener_player_name=tp.player.player_name,
            three_bettor_player_name=tp.player.player_name,
            state_version=state_ver,
        )

        # belief-k
        bk_dec = asyncio.run(
            real_scenario_engine(
                session_id=f"bk_low_{tp.tier}_{tp.player.player_name}_{state_ver}",
                observed_state=observed,
            )
        )
        bk_rec = assert_valid_recommendation(
            bk_dec, label=f"[BK] {tp.tier} {tp.player.player_name}"
        )

        # G5
        state_ver += 1
        observed_g5 = build_3bet_state(
            hero_position=_HERO,
            opener_position=_OPENER,
            three_bettor_position=_THREE_BETTOR,
            opener_player_name=tp.player.player_name,
            three_bettor_player_name=tp.player.player_name,
            state_version=state_ver,
        )
        g5_dec = asyncio.run(
            real_scenario_engine_g5(
                session_id=f"g5_low_{tp.tier}_{tp.player.player_name}_{state_ver}",
                observed_state=observed_g5,
            )
        )
        g5_rec = assert_valid_recommendation(
            g5_dec, label=f"[G5] {tp.tier} {tp.player.player_name}"
        )

        _print_opponent_range_comparison(tp.tier, tp.player, bk_rec, g5_rec)

        csv_rows.append(
            _build_csv_row(
                tier=tp.tier,
                player=tp.player,
                path_label="belief_k",
                decision=bk_rec,
            )
        )
        csv_rows.append(
            _build_csv_row(
                tier=tp.tier,
                player=tp.player,
                path_label="g5",
                decision=g5_rec,
            )
        )

    csv_path = _CSV_OUTPUT_DIR / "3bet_low_data_belief_k_vs_g5.csv"
    _write_low_data_csv(csv_rows, csv_path)

    # 汇总
    print(f"\n{'=' * 88}")
    print("汇总")
    print(f"{'=' * 88}")
    expected_rows = len(tiered_players) * 2
    print(f"  总玩家: {len(tiered_players)}, CSV 行: {len(csv_rows)}")
    assert len(csv_rows) == expected_rows, (
        f"期望 {expected_rows} 行, 实际 {len(csv_rows)}"
    )

    # 按层级汇总平均差异
    tier_deltas: dict[str, list[float]] = {}
    for i in range(0, len(csv_rows), 2):
        bk_row = csv_rows[i]
        g5_row = csv_rows[i + 1]
        tier = str(bk_row["tier"])

        # 对手 3bettor (opp1) posterior_freq 差异
        bk_pf = bk_row.get("opp1_posterior_freq", 0.0)
        g5_pf = g5_row.get("opp1_posterior_freq", 0.0)
        if isinstance(bk_pf, (int, float)) and isinstance(g5_pf, (int, float)):
            tier_deltas.setdefault(tier, []).append(float(g5_pf) - float(bk_pf))

    for tier_label, deltas in tier_deltas.items():
        avg = sum(deltas) / len(deltas) if deltas else 0.0
        print(
            f"  {tier_label}: 3bettor posterior_freq Δ(G5-BK) "
            f"avg={avg:+.6f}, n={len(deltas)}"
        )
