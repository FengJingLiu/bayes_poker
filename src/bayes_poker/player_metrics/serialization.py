"""PlayerStats 序列化/反序列化模块。

提供 PlayerStats 与 Rust 二进制格式之间的转换。
"""

from __future__ import annotations

import hashlib
import struct
from typing import TYPE_CHECKING

from .enums import TableType
from .models import ActionStats, PlayerStats, StatValue

if TYPE_CHECKING:
    from pokerkit import HandHistory


def action_stats_from_binary(data: bytes, offset: int) -> tuple[ActionStats, int]:
    """从二进制数据反序列化单个 ActionStats。

    与 Rust ActionStats::deserialize 兼容的二进制格式：
    - bet_0_40: i32 (little-endian)
    - bet_40_80: i32
    - bet_80_120: i32
    - bet_over_120: i32
    - raise_samples: i32
    - check_call_samples: i32
    - fold_samples: i32

    Args:
        data: 二进制数据。
        offset: 起始偏移量。

    Returns:
        (ActionStats 实例, 新的偏移量)。
    """
    # 每个 ActionStats 占用 7 个 i32 = 28 字节
    values = struct.unpack_from("<7i", data, offset)
    stats = ActionStats(
        bet_0_40=values[0],
        bet_40_80=values[1],
        bet_80_120=values[2],
        bet_over_120=values[3],
        raise_samples=values[4],
        check_call_samples=values[5],
        fold_samples=values[6],
    )
    return stats, offset + 28


def player_stats_from_binary(data: bytes) -> PlayerStats:
    """从二进制数据反序列化 PlayerStats。

    与 Rust PlayerStats::deserialize 兼容的二进制格式：
    - name_len: u32 (little-endian)
    - name_bytes: [u8; name_len]
    - table_type: u8
    - vpip_positive: i32
    - vpip_total: i32
    - preflop_len: u32
    - preflop_stats: [ActionStats; preflop_len]
    - postflop_len: u32
    - postflop_stats: [ActionStats; postflop_len]

    Args:
        data: 二进制数据。

    Returns:
        PlayerStats 实例。

    Raises:
        struct.error: 如果数据格式不正确。
    """
    offset = 0

    # 读取 player_name
    (name_len,) = struct.unpack_from("<I", data, offset)
    offset += 4
    name_bytes = data[offset : offset + name_len]
    player_name = name_bytes.decode("utf-8", errors="replace")
    offset += name_len

    # 读取 table_type, vpip_positive, vpip_total
    (table_type_raw,) = struct.unpack_from("<B", data, offset)
    offset += 1
    vpip_positive, vpip_total = struct.unpack_from("<2i", data, offset)
    offset += 8

    # 读取 preflop_stats
    (preflop_len,) = struct.unpack_from("<I", data, offset)
    offset += 4
    preflop_stats: list[ActionStats] = []
    for _ in range(preflop_len):
        stats, offset = action_stats_from_binary(data, offset)
        preflop_stats.append(stats)

    # 读取 postflop_stats
    (postflop_len,) = struct.unpack_from("<I", data, offset)
    offset += 4
    postflop_stats: list[ActionStats] = []
    for _ in range(postflop_len):
        stats, offset = action_stats_from_binary(data, offset)
        postflop_stats.append(stats)

    # 构建 PlayerStats
    table_type = TableType(table_type_raw)
    result = PlayerStats(player_name=player_name, table_type=table_type)
    result.vpip = StatValue(positive=vpip_positive, total=vpip_total)
    result.preflop_stats = preflop_stats
    result.postflop_stats = postflop_stats

    return result


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
