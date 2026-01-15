"""Rust 加速的玩家统计构建和查询入口。

此模块提供简化的 Python API，底层使用 Rust 实现以获得最佳性能。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

try:
    import poker_stats_rs
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    import poker_stats_rs

from .enums import TableType
from .models import ActionStats, PlayerStats, StatValue


@dataclass
class BatchResult:
    hands_count: int
    players_count: int
    duration_seconds: float

    @property
    def speed(self) -> float:
        return (
            self.hands_count / self.duration_seconds if self.duration_seconds > 0 else 0
        )


def batch_process_phhs(
    phhs_dir: str | Path,
    db_path: str | Path,
    *,
    max_files_in_memory: int | None = None,
) -> tuple[int, int, int]:
    """批量处理 PHHS 文件并保存到 SQLite。

    Args:
        phhs_dir: PHHS 文件目录
        db_path: SQLite 数据库路径
        max_files_in_memory: 可选；每批最多同时加载的 PHHS 文件数量，用于控制内存占用。

    Returns:
        (新增手牌数, 玩家数, 跳过手牌数) 元组
    """
    return poker_stats_rs.py_batch_process_phhs(
        str(phhs_dir),
        str(db_path),
        max_files_in_memory,
    )


def load_player_stats(
    db_path: str | Path,
    player_names: list[str],
    table_type: TableType | int | None = None,
) -> list[PlayerStats]:
    """从 SQLite 加载玩家统计，并返回 Python 的 PlayerStats。

    Args:
        db_path: SQLite 数据库路径
        player_names: 玩家名列表
        table_type: 可选；指定桌型（2=HU, 6=6max）。不传则取该玩家任意一条记录。

    Returns:
        PlayerStats 列表（Python dataclass）。
    """

    table_type_value: int | None
    if table_type is None:
        table_type_value = None
    else:
        table_type_value = int(table_type)

    raw_list = poker_stats_rs.py_load_player_stats_full(
        str(db_path),
        player_names,
        table_type_value,
    )

    results: list[PlayerStats] = []
    for raw in raw_list:
        py_table_type = TableType(raw.table_type)
        stats = PlayerStats(player_name=raw.player_name, table_type=py_table_type)
        stats.vpip = StatValue(positive=raw.vpip_positive, total=raw.vpip_total)

        stats.preflop_stats = [
            ActionStats(
                bet_0_40=s[0],
                bet_40_80=s[1],
                bet_80_120=s[2],
                bet_over_120=s[3],
                raise_samples=s[4],
                check_call_samples=s[5],
                fold_samples=s[6],
            )
            for s in raw.preflop_stats
        ]

        stats.postflop_stats = [
            ActionStats(
                bet_0_40=s[0],
                bet_40_80=s[1],
                bet_80_120=s[2],
                bet_over_120=s[3],
                raise_samples=s[4],
                check_call_samples=s[5],
                fold_samples=s[6],
            )
            for s in raw.postflop_stats
        ]

        results.append(stats)

    return results


def get_vpip(db_path: str | Path, player_name: str) -> float | None:
    """获取玩家 VPIP。

    Args:
        db_path: SQLite 数据库路径
        player_name: 玩家名

    Returns:
        VPIP 百分比 (0-1)，如果玩家不存在返回 None
    """
    results = load_player_stats(db_path, [player_name])
    if not results:
        return None
    stats = results[0]
    if stats.vpip.total == 0:
        return None
    return stats.vpip.positive / stats.vpip.total
