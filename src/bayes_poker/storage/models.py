"""数据模型定义（精简版）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlayerRecord:
    player_id: int | None
    name: str


@dataclass
class HandPlayerRecord:
    hand_hash: str
    player_id: int
    player_name: str
    yyyymmdd: int
    seat_no: int
    rel_pos: str | None = None
    starting_stack: int | None = None


@dataclass
class HandRecord:
    hand_hash: str
    hash_version: int
    yyyymmdd: int
    seat_count: int
    phhs_blob: bytes

    hand_id: int | None = None
    table_name: str | None = None
    button_seat: int | None = None
    source: str | None = None

    players: list[HandPlayerRecord] = field(default_factory=list)
