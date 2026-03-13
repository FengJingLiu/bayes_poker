#!/usr/bin/env python3
"""验证 UTG open 节点 EV 调整效果并导出 GTO+ 文件。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bayes_poker.strategy.strategy_engine.utg_open_ev_validation import (
    run_utg_open_ev_validation,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。

    Returns:
        解析后的参数对象。
    """

    parser = argparse.ArgumentParser(
        description="验证 _adjust_belief_with_stats_and_ev 在 UTG open 节点的效果",
    )
    parser.add_argument(
        "--strategy-db",
        type=Path,
        default=Path("data/database/preflop_strategy.sqlite3"),
        help="策略库路径，默认 data/database/preflop_strategy.sqlite3",
    )
    parser.add_argument(
        "--player-stats-db",
        type=Path,
        default=Path("data/database/player_stats.db"),
        help="玩家统计库路径，默认 data/database/player_stats.db",
    )
    parser.add_argument(
        "--player-csv",
        type=Path,
        default=Path("data/database/player_core_stats.csv"),
        help="玩家核心统计 CSV 路径，默认 data/database/player_core_stats.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/database/utg_open_ev_validation"),
        help="输出目录，默认 data/database/utg_open_ev_validation",
    )
    parser.add_argument(
        "--source-ids",
        type=str,
        default="1,2,3,4,5",
        help="策略源 ID 列表，逗号分隔，默认 1,2,3,4,5",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="取 VPIP/PFR 差异最大的玩家数量，默认 10",
    )
    parser.add_argument(
        "--min-hands",
        type=int,
        default=200,
        help="最小样本手数，默认 200",
    )
    parser.add_argument(
        "--open-size-bb",
        type=float,
        default=2.5,
        help="验证使用的 open 尺度（BB），默认 2.5",
    )
    parser.add_argument(
        "--big-blind",
        type=float,
        default=1.0,
        help="大盲金额，默认 1.0",
    )
    parser.add_argument(
        "--min-strategy",
        type=float,
        default=0.001,
        help="导出 GTO+ 时最小策略阈值，默认 0.001",
    )
    return parser.parse_args(argv)


def parse_source_ids(raw_source_ids: str) -> tuple[int, ...]:
    """解析 source_ids 字符串。

    Args:
        raw_source_ids: 逗号分隔的 source_id 字符串。

    Returns:
        source_id 元组。
    """

    items = [item.strip() for item in raw_source_ids.split(",") if item.strip()]
    if not items:
        raise ValueError("source_ids 不能为空。")
    return tuple(int(item) for item in items)


def main(argv: list[str] | None = None) -> int:
    """脚本入口。

    Args:
        argv: 可选参数列表。

    Returns:
        进程退出码。
    """

    args = parse_args(argv)
    source_ids = parse_source_ids(args.source_ids)
    output = run_utg_open_ev_validation(
        strategy_db_path=args.strategy_db,
        player_stats_db_path=args.player_stats_db,
        player_core_csv_path=args.player_csv,
        output_dir=args.output_dir,
        source_ids=source_ids,
        top_n=args.top_n,
        min_hands=args.min_hands,
        open_size_bb=args.open_size_bb,
        big_blind=args.big_blind,
        min_strategy=args.min_strategy,
    )
    print(
        "UTG open EV 调整验证完成: "
        f"players={output.player_count}, "
        f"summary={output.summary_csv_path}, "
        f"prior_gtoplus={output.prior_gtoplus_path}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
