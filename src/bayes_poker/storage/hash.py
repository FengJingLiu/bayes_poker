"""主键哈希生成算法。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

HASH_VERSION = 2

POSITION_ORDER = ["SB", "BB", "UTG", "MP", "CO", "BTN"]


def _position_sort_key(pos: str | None) -> int:
    if pos is None:
        return 99
    try:
        return POSITION_ORDER.index(pos)
    except ValueError:
        return 50


def compute_hand_hash(
    yyyymmdd: int,
    player_snapshots: Sequence[tuple[str | None, str, int]],
    actions: list[str],
    board_tokens: str,
) -> str:
    """
    计算手牌哈希值。

    Args:
        yyyymmdd: 日期 (yyyymmdd 格式)
        player_snapshots: [(rel_pos, player_name, starting_stack), ...] 按 SB-BB-UTG-MP-CO-BTN 排序
        actions: 行动列表
        board_tokens: 公共牌

    Returns:
        sha256 哈希值 (hex)
    """
    sorted_snapshots = sorted(
        player_snapshots,
        key=lambda x: _position_sort_key(x[0]),
    )

    payload = {
        "d": yyyymmdd,
        "p": [[s[1], s[2]] for s in sorted_snapshots],
        "a": actions,
        "b": board_tokens,
    }

    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
