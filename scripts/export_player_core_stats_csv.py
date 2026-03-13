#!/usr/bin/env python3
"""导出玩家核心统计指标到 CSV。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bayes_poker.player_metrics.core_stats_csv import export_player_core_stats_csv
from bayes_poker.player_metrics.enums import TableType


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。

    Returns:
        解析后的参数对象。
    """

    parser = argparse.ArgumentParser(
        description="导出 player_stats.db 的核心统计到 CSV",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/database/player_stats.db"),
        help="player_stats.db 路径，默认 data/database/player_stats.db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/database/player_core_stats.csv"),
        help="输出 CSV 路径，默认 data/database/player_core_stats.csv",
    )
    parser.add_argument(
        "--table-type",
        choices=("all", "heads_up", "six_max", "eight_max", "nine_max"),
        default="all",
        help="桌型过滤，默认 all",
    )
    return parser.parse_args(argv)


def resolve_table_type(table_type_name: str) -> TableType | None:
    """解析桌型参数。

    Args:
        table_type_name: 桌型参数字符串。

    Returns:
        对应 TableType，`all` 时返回 None。
    """

    if table_type_name == "all":
        return None
    mapping = {
        "heads_up": TableType.HEADS_UP,
        "six_max": TableType.SIX_MAX,
        "eight_max": TableType.EIGHT_MAX,
        "nine_max": TableType.NINE_MAX,
    }
    return mapping[table_type_name]


def main(argv: list[str] | None = None) -> int:
    """脚本入口。

    Args:
        argv: 可选参数列表。

    Returns:
        进程退出码。
    """

    args = parse_args(argv)
    table_type = resolve_table_type(args.table_type)
    exported_count = export_player_core_stats_csv(
        db_path=args.db_path,
        output_path=args.output,
        table_type=table_type,
    )
    print(
        f"已导出 {exported_count} 条玩家核心统计到 {args.output}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
