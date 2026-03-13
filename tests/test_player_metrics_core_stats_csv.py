"""测试玩家核心统计 CSV 导出模块。"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bayes_poker.player_metrics.core_stats_csv import (
    build_core_stats_row,
    export_player_core_stats_csv,
    format_stat,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats, StatValue


def _build_player_stats(player_name: str) -> PlayerStats:
    """构造测试用 PlayerStats 对象。

    Args:
        player_name: 玩家名称。

    Returns:
        初始化后的玩家统计对象。
    """

    return PlayerStats(
        player_name=player_name,
        table_type=TableType.SIX_MAX,
        vpip=StatValue(positive=60, total=120),
    )


def test_format_stat_with_zero_total() -> None:
    """当总样本为 0 时应返回 N/A。"""

    assert format_stat(positive=0, total=0) == "N/A (0)"


def test_build_core_stats_row_uses_metric_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """构建行数据时应复用核心统计口径。"""

    player_stats = _build_player_stats("Hero")
    module_name = "bayes_poker.player_metrics.core_stats_csv"
    monkeypatch.setattr(f"{module_name}.calculate_total_hands", lambda _stats: 120)
    monkeypatch.setattr(f"{module_name}.calculate_pfr", lambda _stats: (36, 120))
    monkeypatch.setattr(f"{module_name}.calculate_wtp", lambda _stats: (45, 100))
    monkeypatch.setattr(f"{module_name}.calculate_aggression", lambda _stats: (30, 60))

    row = build_core_stats_row(player_stats)

    assert row["player_name"] == "Hero"
    assert row["table_type"] == "SIX_MAX"
    assert row["total_hands"] == "120"
    assert row["vpip"] == "50.0% (60/120)"
    assert row["pfr"] == "30.0% (36/120)"
    assert row["wtp"] == "45.0% (45/100)"
    assert row["agg"] == "50.0% (30/60)"


def test_export_player_core_stats_csv_writes_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """导出函数应生成包含头部与数据行的 CSV 文件。"""

    players = [_build_player_stats("Alice"), _build_player_stats("Bob")]
    module_name = "bayes_poker.player_metrics.core_stats_csv"
    monkeypatch.setattr(
        f"{module_name}.load_player_stats",
        lambda db_path, table_type=None: players,
    )
    monkeypatch.setattr(f"{module_name}.calculate_total_hands", lambda _stats: 120)
    monkeypatch.setattr(f"{module_name}.calculate_pfr", lambda _stats: (24, 120))
    monkeypatch.setattr(f"{module_name}.calculate_wtp", lambda _stats: (30, 100))
    monkeypatch.setattr(f"{module_name}.calculate_aggression", lambda _stats: (18, 60))

    output_path = tmp_path / "player_core_stats.csv"
    exported_count = export_player_core_stats_csv(
        db_path=tmp_path / "player_stats.db",
        output_path=output_path,
    )

    assert exported_count == 2
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert [row["player_name"] for row in rows] == ["Alice", "Bob"]
    assert rows[0]["vpip"] == "50.0% (60/120)"
    assert rows[0]["pfr"] == "20.0% (24/120)"
