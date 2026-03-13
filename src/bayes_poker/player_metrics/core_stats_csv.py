"""导出玩家核心统计到 CSV。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_total_hands,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.storage import PlayerStatsRepository

CSV_HEADERS: tuple[str, ...] = (
    "player_name",
    "table_type",
    "total_hands",
    "vpip",
    "pfr",
    "wtp",
    "agg",
    "vpip_pct",
    "pfr_pct",
    "wtp_pct",
    "agg_pct",
    "vpip_positive",
    "vpip_total",
    "pfr_positive",
    "pfr_total",
    "wtp_positive",
    "wtp_total",
    "agg_positive",
    "agg_total",
)


def format_stat(positive: float, total: float) -> str:
    """格式化统计值为百分比字符串。

    Args:
        positive: 命中次数。
        total: 总样本数。

    Returns:
        格式化后的百分比字符串。
    """

    if total <= 0:
        return "N/A (0)"
    pct = positive / total * 100
    return f"{pct:.1f}% ({_format_count(positive)}/{_format_count(total)})"


def build_core_stats_row(stats: PlayerStats) -> dict[str, str]:
    """构建单个玩家的核心统计行。

    Args:
        stats: 玩家统计对象。

    Returns:
        可直接写入 CSV 的字符串字典。
    """

    total_hands = float(calculate_total_hands(stats))
    vpip_positive = float(stats.vpip.positive)
    vpip_total = float(stats.vpip.total)

    pfr_positive_raw, pfr_total_raw = calculate_pfr(stats)
    pfr_positive = float(pfr_positive_raw)
    pfr_total = float(pfr_total_raw)

    wtp_positive_raw, wtp_total_raw = calculate_wtp(stats)
    wtp_positive = float(wtp_positive_raw)
    wtp_total = float(wtp_total_raw)

    agg_positive_raw, agg_total_raw = calculate_aggression(stats)
    agg_positive = float(agg_positive_raw)
    agg_total = float(agg_total_raw)

    return {
        "player_name": stats.player_name,
        "table_type": stats.table_type.name,
        "total_hands": _format_count(total_hands),
        "vpip": format_stat(vpip_positive, vpip_total),
        "pfr": format_stat(pfr_positive, pfr_total),
        "wtp": format_stat(wtp_positive, wtp_total),
        "agg": format_stat(agg_positive, agg_total),
        "vpip_pct": _format_percent(vpip_positive, vpip_total),
        "pfr_pct": _format_percent(pfr_positive, pfr_total),
        "wtp_pct": _format_percent(wtp_positive, wtp_total),
        "agg_pct": _format_percent(agg_positive, agg_total),
        "vpip_positive": _format_count(vpip_positive),
        "vpip_total": _format_count(vpip_total),
        "pfr_positive": _format_count(pfr_positive),
        "pfr_total": _format_count(pfr_total),
        "wtp_positive": _format_count(wtp_positive),
        "wtp_total": _format_count(wtp_total),
        "agg_positive": _format_count(agg_positive),
        "agg_total": _format_count(agg_total),
    }


def build_core_stats_rows(stats_list: list[PlayerStats]) -> list[dict[str, str]]:
    """构建多个玩家的核心统计行。

    Args:
        stats_list: 玩家统计列表。

    Returns:
        排序后的 CSV 行列表。
    """

    ordered_stats = sorted(
        stats_list,
        key=lambda item: (item.table_type.value, item.player_name),
    )
    return [build_core_stats_row(stats) for stats in ordered_stats]


def load_player_stats(
    db_path: Path,
    table_type: TableType | None = None,
) -> list[PlayerStats]:
    """从仓储加载玩家统计。

    Args:
        db_path: 玩家统计库路径。
        table_type: 可选桌型过滤。

    Returns:
        玩家统计列表。
    """

    with PlayerStatsRepository(db_path) as repo:
        return repo.get_all(table_type=table_type)


def export_player_core_stats_csv(
    db_path: Path,
    output_path: Path,
    table_type: TableType | None = None,
) -> int:
    """导出玩家核心统计到 CSV。

    Args:
        db_path: 玩家统计库路径。
        output_path: 输出 CSV 路径。
        table_type: 可选桌型过滤。

    Returns:
        导出的玩家数量。
    """

    stats_list = load_player_stats(db_path=db_path, table_type=table_type)
    rows = build_core_stats_rows(stats_list)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(CSV_HEADERS))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _format_percent(positive: float, total: float) -> str:
    """格式化百分比字段。

    Args:
        positive: 命中次数。
        total: 总样本数。

    Returns:
        百分比字符串。
    """

    if total <= 0:
        return "N/A"
    return f"{positive / total * 100:.1f}%"


def _format_count(value: float) -> str:
    """格式化计数字段。

    Args:
        value: 计数值。

    Returns:
        整数字符串或一位小数字符串。
    """

    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
