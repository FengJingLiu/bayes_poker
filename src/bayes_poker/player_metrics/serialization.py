"""PlayerStats 序列化/反序列化模块。

提供 PlayerStats、ActionStats、StatValue 与数据库/JSON 之间的转换。
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from .enums import TableType
from .models import ActionStats, PlayerStats, StatValue

if TYPE_CHECKING:
    from pokerkit import HandHistory


def stat_value_to_dict(sv: StatValue) -> dict[str, int]:
    """将 StatValue 转换为字典。"""
    return {"positive": sv.positive, "total": sv.total}


def stat_value_from_dict(d: dict[str, int]) -> StatValue:
    """从字典创建 StatValue。"""
    return StatValue(positive=d["positive"], total=d["total"])


def action_stats_to_dict(stats: ActionStats) -> dict[str, int]:
    """将 ActionStats 转换为字典。"""
    return {
        "bet_0_40": stats.bet_0_40,
        "bet_40_80": stats.bet_40_80,
        "bet_80_120": stats.bet_80_120,
        "bet_over_120": stats.bet_over_120,
        "raise_samples": stats.raise_samples,
        "check_call_samples": stats.check_call_samples,
        "fold_samples": stats.fold_samples,
    }


def action_stats_from_dict(d: dict[str, int]) -> ActionStats:
    """从字典创建 ActionStats。"""
    return ActionStats(
        bet_0_40=d.get("bet_0_40", 0),
        bet_40_80=d.get("bet_40_80", 0),
        bet_80_120=d.get("bet_80_120", 0),
        bet_over_120=d.get("bet_over_120", 0),
        raise_samples=d.get("raise_samples", 0),
        check_call_samples=d.get("check_call_samples", 0),
        fold_samples=d.get("fold_samples", 0),
    )


def action_stats_list_to_json(stats_list: list[ActionStats]) -> str:
    """将 ActionStats 列表序列化为 JSON 字符串。"""
    return json.dumps([action_stats_to_dict(s) for s in stats_list], separators=(",", ":"))


def action_stats_list_from_json(json_str: str) -> list[ActionStats]:
    """从 JSON 字符串反序列化 ActionStats 列表。"""
    data = json.loads(json_str)
    return [action_stats_from_dict(d) for d in data]


def player_stats_to_row(stats: PlayerStats) -> dict[str, Any]:
    """将 PlayerStats 转换为数据库行字典。

    Returns:
        包含以下键的字典：
        - player_name: str
        - table_type: int
        - vpip_positive: int
        - vpip_total: int
        - preflop_stats_json: str
        - postflop_stats_json: str
    """
    return {
        "player_name": stats.player_name,
        "table_type": int(stats.table_type),
        "vpip_positive": stats.vpip.positive,
        "vpip_total": stats.vpip.total,
        "preflop_stats_json": action_stats_list_to_json(stats.preflop_stats),
        "postflop_stats_json": action_stats_list_to_json(stats.postflop_stats),
    }


def player_stats_from_row(row: dict[str, Any]) -> PlayerStats:
    """从数据库行字典创建 PlayerStats。

    Args:
        row: 数据库行，包含 player_name, table_type, vpip_positive 等字段。

    Returns:
        PlayerStats 实例。
    """
    table_type = TableType(row["table_type"])
    stats = PlayerStats(
        player_name=row["player_name"],
        table_type=table_type,
    )
    stats.vpip = StatValue(
        positive=row["vpip_positive"],
        total=row["vpip_total"],
    )
    stats.preflop_stats = action_stats_list_from_json(row["preflop_stats_json"])
    stats.postflop_stats = action_stats_list_from_json(row["postflop_stats_json"])
    return stats


def merge_player_stats(target: PlayerStats, source: PlayerStats) -> None:
    """将 source 的统计数据累加到 target。

    注意：两者必须具有相同的 table_type，否则 stats 列表长度可能不匹配。

    Args:
        target: 目标 PlayerStats，将被修改。
        source: 源 PlayerStats，数据将被累加到 target。

    Raises:
        ValueError: 如果 table_type 不匹配。
    """
    if target.table_type != source.table_type:
        raise ValueError(
            f"table_type 不匹配: target={target.table_type}, source={source.table_type}"
        )

    target.vpip.append(source.vpip)

    for i, stats in enumerate(source.preflop_stats):
        if i < len(target.preflop_stats):
            target.preflop_stats[i].append(stats)

    for i, stats in enumerate(source.postflop_stats):
        if i < len(target.postflop_stats):
            target.postflop_stats[i].append(stats)


HAND_HASH_LENGTH = 32


def compute_hand_hash(hh: HandHistory) -> str:
    """计算手牌的唯一哈希值。

    使用 players + actions 生成 SHA256 哈希，截取前 32 个十六进制字符 (128 bits)。
    对于千万级手牌，碰撞概率约为 10^-24，极其安全。

    Args:
        hh: HandHistory 对象。

    Returns:
        32 字符的十六进制哈希字符串。
    """
    players_str = "|".join(hh.players) if hh.players else ""
    actions_str = "|".join(hh.actions) if hh.actions else ""
    content = f"{players_str}\n{actions_str}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:HAND_HASH_LENGTH]
