#!/usr/bin/env python3
"""导出 hero 策略调整对比 CSV。

遍历全部 15 种 6-max RFI 位置组合 x N 名玩家样本,
对每种场景运行 StrategyEngine, 输出 prior/posterior 动作分布与对手激进度明细,
方便验证 hero 策略调整是否生效。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
    StrategyEngineConfig,
    build_strategy_engine,
)
from bayes_poker.strategy.strategy_engine.contracts import StrategyDecision

# 复用测试 helpers 中的工具函数
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from real_scenario.helpers import (
    ALL_RFI_COMBINATIONS_6MAX,
    PLAYER_CORE_STATS_CSV_PATH,
    PLAYER_STATS_DB_PATH,
    STRATEGY_DB_PATH,
    PlayerPfrRow,
    build_rfi_state,
    load_players_with_large_pfr_spread,
)

LOGGER = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。

    Returns:
        解析后的参数对象。
    """

    parser = argparse.ArgumentParser(
        description="导出 hero 策略调整对比 CSV (15 种 RFI 组合 x N 名玩家)",
    )
    parser.add_argument(
        "--strategy-db",
        type=Path,
        default=STRATEGY_DB_PATH,
        help=f"策略数据库路径, 默认 {STRATEGY_DB_PATH}",
    )
    parser.add_argument(
        "--player-stats-db",
        type=Path,
        default=PLAYER_STATS_DB_PATH,
        help=f"玩家统计数据库路径, 默认 {PLAYER_STATS_DB_PATH}",
    )
    parser.add_argument(
        "--player-csv",
        type=Path,
        default=PLAYER_CORE_STATS_CSV_PATH,
        help=f"玩家核心统计 CSV 路径, 默认 {PLAYER_CORE_STATS_CSV_PATH}",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/database/hero_adjustment_report.csv"),
        help="输出 CSV 路径, 默认 data/database/hero_adjustment_report.csv",
    )
    parser.add_argument(
        "--min-hands",
        type=int,
        default=200,
        help="最小总手数过滤阈值, 默认 200",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=5,
        help="玩家采样数量, 默认 5",
    )
    parser.add_argument(
        "--source-ids",
        type=str,
        default="1,2,3,4,5",
        help="策略源 ID, 逗号分隔, 默认 1,2,3,4,5",
    )
    return parser.parse_args(argv)


def _build_engine(
    *,
    strategy_db_path: Path,
    player_stats_db_path: Path,
    source_ids: tuple[int, ...],
) -> StrategyEngine:
    """构建 StrategyEngine 实例。

    Args:
        strategy_db_path: 策略数据库路径。
        player_stats_db_path: 玩家统计数据库路径。
        source_ids: 策略源 ID 集合。

    Returns:
        已初始化的 StrategyEngine。
    """

    return build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=strategy_db_path,
            player_stats_db_path=player_stats_db_path,
            table_type=TableType.SIX_MAX,
            source_ids=source_ids,
        )
    )


def _collect_all_action_codes(
    results: list[tuple[str, str, PlayerPfrRow, RecommendationDecision]],
) -> list[str]:
    """从所有结果中收集并排序全部动作编码。

    Args:
        results: (opener_pos, hero_pos, player_row, decision) 元组列表。

    Returns:
        排序后的动作编码列表。
    """

    action_codes: set[str] = set()
    for _, _, _, decision in results:
        action_codes.update(decision.prior_action_distribution.keys())
        action_codes.update(decision.action_distribution.keys())
    return sorted(action_codes)


def _build_csv_row(
    *,
    opener_pos: str,
    hero_pos: str,
    player_row: PlayerPfrRow,
    decision: RecommendationDecision,
    all_action_codes: list[str],
) -> dict[str, object]:
    """构建单行 CSV 数据。

    Args:
        opener_pos: Opener 位置名。
        hero_pos: Hero 位置名。
        player_row: 对手玩家统计行。
        decision: Hero 推荐决策。
        all_action_codes: 全部动作编码 (用于列名一致)。

    Returns:
        字段名 -> 值的映射。
    """

    row: dict[str, object] = {
        "opener_position": opener_pos,
        "hero_position": hero_pos,
        "player_name": player_row.player_name,
        "total_hands": player_row.total_hands,
        "pfr_pct": f"{player_row.pfr_pct:.2f}",
        "selected_node_id": decision.selected_node_id,
        "selected_source_id": decision.selected_source_id,
        "sampled_action": decision.action_code or "",
    }

    # prior / posterior 动作分布
    for action_code in all_action_codes:
        prior_val = decision.prior_action_distribution.get(action_code, 0.0)
        post_val = decision.action_distribution.get(action_code, 0.0)
        delta = post_val - prior_val
        row[f"prior_{action_code}"] = f"{prior_val:.6f}"
        row[f"post_{action_code}"] = f"{post_val:.6f}"
        row[f"delta_{action_code}"] = f"{delta:+.6f}"

    # 对手激进度明细 (聚合)
    details = decision.opponent_aggression_details
    if details:
        aggregated_ratio = 1.0
        prior_freqs: list[str] = []
        posterior_freqs: list[str] = []
        raw_ratios: list[str] = []
        dampened_ratios: list[str] = []

        for d in details:
            prior_f = float(d["prior_freq"])  # type: ignore[arg-type]
            posterior_f = float(d["posterior_freq"])  # type: ignore[arg-type]
            ratio = float(d["ratio"])  # type: ignore[arg-type]
            dampened = float(d.get("dampened_ratio", ratio))  # type: ignore[arg-type]
            aggregated_ratio *= dampened
            prior_freqs.append(f"{prior_f:.4f}")
            posterior_freqs.append(f"{posterior_f:.4f}")
            raw_ratios.append(f"{ratio:.4f}")
            dampened_ratios.append(f"{dampened:.4f}")

        row["opp_count"] = len(details)
        row["opp_prior_freqs"] = ";".join(prior_freqs)
        row["opp_posterior_freqs"] = ";".join(posterior_freqs)
        row["opp_raw_ratios"] = ";".join(raw_ratios)
        row["opp_dampened_ratios"] = ";".join(dampened_ratios)
        row["aggregated_aggression_ratio"] = f"{aggregated_ratio:.6f}"
    else:
        row["opp_count"] = 0
        row["opp_prior_freqs"] = ""
        row["opp_posterior_freqs"] = ""
        row["opp_raw_ratios"] = ""
        row["opp_dampened_ratios"] = ""
        row["aggregated_aggression_ratio"] = ""

    return row


def main(argv: list[str] | None = None) -> int:
    """脚本入口。

    Args:
        argv: 可选参数列表。

    Returns:
        进程退出码。
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = parse_args(argv)
    source_ids = tuple(int(x.strip()) for x in args.source_ids.split(","))

    # 1. 加载玩家样本
    LOGGER.info(
        "加载玩家样本: csv=%s, min_hands=%d, sample_count=%d",
        args.player_csv,
        args.min_hands,
        args.sample_count,
    )
    players = load_players_with_large_pfr_spread(
        csv_path=args.player_csv,
        min_hands=args.min_hands,
        sample_count=args.sample_count,
    )
    LOGGER.info(
        "已选取 %d 名玩家: %s",
        len(players),
        [(p.player_name, f"pfr={p.pfr_pct:.1f}%") for p in players],
    )

    # 2. 构建引擎
    LOGGER.info("构建 StrategyEngine ...")
    engine = _build_engine(
        strategy_db_path=args.strategy_db,
        player_stats_db_path=args.player_stats_db,
        source_ids=source_ids,
    )

    # 3. 遍历 15 种 RFI 组合 x N 名玩家
    results: list[tuple[str, str, PlayerPfrRow, RecommendationDecision]] = []
    total_combos = len(ALL_RFI_COMBINATIONS_6MAX) * len(players)
    processed = 0
    state_version = 0

    for opener_position, hero_position in ALL_RFI_COMBINATIONS_6MAX:
        for player_row in players:
            state_version += 1
            observed_state = build_rfi_state(
                hero_position=hero_position,
                opener_position=opener_position,
                opener_player_name=player_row.player_name,
                state_version=state_version,
            )

            decision: StrategyDecision = asyncio.run(
                engine(
                    session_id=f"export_{opener_position.value}_{hero_position.value}_{player_row.player_name}",
                    observed_state=observed_state,
                )
            )

            processed += 1
            opener_val = opener_position.value
            hero_val = hero_position.value

            if isinstance(decision, RecommendationDecision):
                results.append((opener_val, hero_val, player_row, decision))
                LOGGER.info(
                    "[%d/%d] %s open -> hero %s, player=%s -> OK (node=%s)",
                    processed,
                    total_combos,
                    opener_val,
                    hero_val,
                    player_row.player_name,
                    decision.selected_node_id,
                )
            else:
                LOGGER.warning(
                    "[%d/%d] %s open -> hero %s, player=%s -> %s: %s",
                    processed,
                    total_combos,
                    opener_val,
                    hero_val,
                    player_row.player_name,
                    type(decision).__name__,
                    getattr(decision, "reason", getattr(decision, "notes", "?")),
                )

    if not results:
        LOGGER.error("无任何有效结果, 请检查数据库与配置。")
        return 1

    # 4. 收集全部动作编码
    all_action_codes = _collect_all_action_codes(results)
    LOGGER.info("动作编码集合: %s", all_action_codes)

    # 5. 写 CSV
    fieldnames: list[str] = [
        "opener_position",
        "hero_position",
        "player_name",
        "total_hands",
        "pfr_pct",
        "selected_node_id",
        "selected_source_id",
        "sampled_action",
    ]
    for action_code in all_action_codes:
        fieldnames.append(f"prior_{action_code}")
        fieldnames.append(f"post_{action_code}")
        fieldnames.append(f"delta_{action_code}")

    fieldnames.extend(
        [
            "opp_count",
            "opp_prior_freqs",
            "opp_posterior_freqs",
            "opp_raw_ratios",
            "opp_dampened_ratios",
            "aggregated_aggression_ratio",
        ]
    )

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for opener_val, hero_val, player_row, decision in results:
            row = _build_csv_row(
                opener_pos=opener_val,
                hero_pos=hero_val,
                player_row=player_row,
                decision=decision,
                all_action_codes=all_action_codes,
            )
            writer.writerow(row)

    LOGGER.info(
        "已导出 %d 行到 %s (位置组合=%d, 玩家=%d, 动作编码=%d)",
        len(results),
        output_path,
        len(ALL_RFI_COMBINATIONS_6MAX),
        len(players),
        len(all_action_codes),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
