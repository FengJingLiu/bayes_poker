"""测试 UTG open EV 调整验证工具。"""

from __future__ import annotations

import csv
from pathlib import Path

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine.utg_open_ev_validation import (
    build_utg_open_player_node_context,
    parse_percent_value,
    sanitize_filename,
    select_players_with_large_vpip_pfr_gap,
)


def test_parse_percent_value() -> None:
    """应正确解析百分比字符串。"""

    assert parse_percent_value("41.9%") == 41.9
    assert parse_percent_value(" N/A ") is None
    assert parse_percent_value("") is None


def test_sanitize_filename() -> None:
    """应清理文件名中的非法字符。"""

    assert sanitize_filename("A/B:C") == "A_B_C"
    assert sanitize_filename("  ") == "unknown"


def test_build_utg_open_player_node_context() -> None:
    """应构造 SIX_MAX 的 UTG open 节点上下文。"""

    context = build_utg_open_player_node_context(TableType.SIX_MAX)

    assert context.actor_seat == 3
    assert context.node_context.raise_time == 0
    assert context.node_context.pot_size == 1.5


def test_select_players_with_large_vpip_pfr_gap(tmp_path: Path) -> None:
    """应按 VPIP/PFR 差异和手数筛选并排序玩家。"""

    csv_path = tmp_path / "player_core_stats.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "player_name",
                "table_type",
                "total_hands",
                "vpip_pct",
                "pfr_pct",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "player_name": "Alice",
                "table_type": "SIX_MAX",
                "total_hands": "300",
                "vpip_pct": "40.0%",
                "pfr_pct": "10.0%",
            }
        )
        writer.writerow(
            {
                "player_name": "Bob",
                "table_type": "SIX_MAX",
                "total_hands": "500",
                "vpip_pct": "30.0%",
                "pfr_pct": "20.0%",
            }
        )
        writer.writerow(
            {
                "player_name": "aggregated_sixmax_100",
                "table_type": "SIX_MAX",
                "total_hands": "999",
                "vpip_pct": "35.0%",
                "pfr_pct": "22.0%",
            }
        )

    selected = select_players_with_large_vpip_pfr_gap(
        csv_path=csv_path,
        table_type_name="SIX_MAX",
        top_n=2,
        min_hands=200,
    )

    assert [item.player_name for item in selected] == ["Alice", "Bob"]
    assert selected[0].vpip_pfr_gap_pct == 30.0
