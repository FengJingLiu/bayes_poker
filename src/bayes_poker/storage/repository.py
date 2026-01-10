"""数据库操作仓储（精简版 - 仅玩家查询）。"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from pokerkit.notation import HandHistory

from bayes_poker.storage.models import HandPlayerRecord, HandRecord
from bayes_poker.storage.schema import init_database

LOGGER = logging.getLogger(__name__)


@dataclass
class HandSearchResult:
    hand_hash: str
    yyyymmdd: int
    table_name: str | None
    hand_id: int | None


class HandRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            init_database(self._conn)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> HandRepository:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get_or_create_player_id(self, name: str) -> int:
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("SELECT player_id FROM players WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row["player_id"]

        cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
        conn.commit()
        return cursor.lastrowid  # type: ignore

    def insert_hand(self, hand: HandRecord) -> bool:
        conn = self.connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO hands (
                    hand_hash, hash_version, yyyymmdd, hand_id, table_name,
                    seat_count, button_seat, phhs_blob, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hand.hand_hash,
                    hand.hash_version,
                    hand.yyyymmdd,
                    hand.hand_id,
                    hand.table_name,
                    hand.seat_count,
                    hand.button_seat,
                    hand.phhs_blob,
                    hand.source,
                ),
            )

            if cursor.rowcount == 0:
                return False

            for player in hand.players:
                player_id = self.get_or_create_player_id(player.player_name)

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO hand_players (
                        hand_hash, player_id, yyyymmdd, seat_no, rel_pos, starting_stack
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hand.hand_hash,
                        player_id,
                        hand.yyyymmdd,
                        player.seat_no,
                        player.rel_pos,
                        player.starting_stack,
                    ),
                )

            conn.commit()
            return True

        except sqlite3.Error as e:
            LOGGER.error("插入手牌失败: %s", e)
            conn.rollback()
            return False

    def insert_hand_with_player_names(
        self, hand: HandRecord, player_names: list[str]
    ) -> bool:
        """兼容方法：直接调用 insert_hand（player_names 已在 hand.players 中）。"""
        return self.insert_hand(hand)

    def find_hands_by_player(
        self,
        player_name: str,
        start_date: int | None = None,
        end_date: int | None = None,
    ) -> list[HandSearchResult]:
        conn = self.connect()
        cursor = conn.cursor()

        sql = """
            SELECT h.hand_hash, h.yyyymmdd, h.table_name, h.hand_id
            FROM players p
            JOIN hand_players hp ON hp.player_id = p.player_id
            JOIN hands h ON h.hand_hash = hp.hand_hash
            WHERE p.name = ?
        """
        params: list[Any] = [player_name]

        if start_date is not None:
            sql += " AND h.yyyymmdd >= ?"
            params.append(start_date)
        if end_date is not None:
            sql += " AND h.yyyymmdd <= ?"
            params.append(end_date)

        sql += " ORDER BY h.yyyymmdd DESC"

        cursor.execute(sql, params)
        return [
            HandSearchResult(
                hand_hash=row["hand_hash"],
                yyyymmdd=row["yyyymmdd"],
                table_name=row["table_name"],
                hand_id=row["hand_id"],
            )
            for row in cursor.fetchall()
        ]

    def get_hand_history(self, hand_hash: str) -> HandHistory | None:
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("SELECT phhs_blob FROM hands WHERE hand_hash = ?", (hand_hash,))
        row = cursor.fetchone()

        if not row or not row["phhs_blob"]:
            return None

        buffer = BytesIO(row["phhs_blob"])
        hands = list(HandHistory.load_all(buffer))
        return hands[0] if hands else None

    def get_stats(self) -> dict[str, int]:
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM hands")
        hands_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM players")
        players_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM hand_players")
        hand_players_count = cursor.fetchone()["cnt"]

        return {
            "hands": hands_count,
            "players": players_count,
            "hand_players": hand_players_count,
        }
