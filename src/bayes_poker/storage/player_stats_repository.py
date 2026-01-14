"""PlayerStats SQLite 存储仓库。

提供 PlayerStats 的持久化存储，包括：
- 去重：通过 processed_hands 表追踪已处理的手牌 ID
- 累加合并：同一玩家的多次数据自动累加
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.player_metrics.serialization import (
    merge_player_stats,
    player_stats_from_row,
    player_stats_to_row,
)

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

# SQL 语句
CREATE_PLAYER_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS player_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    table_type INTEGER NOT NULL,
    vpip_positive INTEGER NOT NULL DEFAULT 0,
    vpip_total INTEGER NOT NULL DEFAULT 0,
    preflop_stats_json TEXT NOT NULL,
    postflop_stats_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(player_name, table_type)
)
"""

CREATE_PROCESSED_HANDS_TABLE = """
CREATE TABLE IF NOT EXISTS processed_hands (
    hand_hash TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
)
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_player_name ON player_stats(player_name);
CREATE INDEX IF NOT EXISTS idx_table_type ON player_stats(table_type);
"""


class PlayerStatsRepository:
    """PlayerStats 的 SQLite 存储仓库。

    支持去重和累加合并。

    用法：
        repo = PlayerStatsRepository("data/player_stats.db")
        repo.connect()
        try:
            repo.upsert_with_merge(stats)
        finally:
            repo.close()

    或使用上下文管理器：
        with PlayerStatsRepository("data/player_stats.db") as repo:
            repo.upsert_with_merge(stats)
    """

    def __init__(self, db_path: str | Path) -> None:
        """初始化仓库。

        Args:
            db_path: SQLite 数据库文件路径。
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """连接数据库并初始化表结构。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PlayerStatsRepository:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        """获取数据库连接。"""
        if self._conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        return self._conn

    def _init_tables(self) -> None:
        """初始化数据库表。"""
        cursor = self.conn.cursor()
        cursor.execute(CREATE_PLAYER_STATS_TABLE)

        self._ensure_processed_hands_schema(cursor)

        cursor.executescript(CREATE_INDEXES)
        self.conn.commit()

    def _ensure_processed_hands_schema(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands'"
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(CREATE_PROCESSED_HANDS_TABLE)
            return

        cursor.execute("PRAGMA table_info(processed_hands)")
        columns = {r[1] for r in cursor.fetchall()}

        if "hand_hash" in columns:
            return

        if "hand_id" in columns:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands_legacy'"
            )
            legacy = cursor.fetchone()
            if legacy is None:
                cursor.execute("ALTER TABLE processed_hands RENAME TO processed_hands_legacy")
            else:
                cursor.execute("DROP TABLE processed_hands")

            cursor.execute(CREATE_PROCESSED_HANDS_TABLE)
            return

        cursor.execute("DROP TABLE processed_hands")
        cursor.execute(CREATE_PROCESSED_HANDS_TABLE)

    # ========== 手牌去重 ==========

    def is_hand_processed(self, hand_hash: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_hands WHERE hand_hash = ?",
            (hand_hash,),
        )
        return cursor.fetchone() is not None

    def get_processed_hand_hashes(self, hand_hashes: Sequence[str]) -> set[str]:
        if not hand_hashes:
            return set()

        processed: set[str] = set()
        cursor = self.conn.cursor()

        chunk_size = 900
        for i in range(0, len(hand_hashes), chunk_size):
            chunk = list(hand_hashes[i : i + chunk_size])
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT hand_hash FROM processed_hands WHERE hand_hash IN ({placeholders})",
                chunk,
            )
            processed.update({row[0] for row in cursor.fetchall()})

        return processed

    def mark_hand_processed(self, hand_hash: str) -> None:
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO processed_hands (hand_hash, processed_at) VALUES (?, ?)",
            (hand_hash, now),
        )
        self.conn.commit()

    def mark_hands_processed(self, hand_hashes: Sequence[str]) -> None:
        if not hand_hashes:
            return

        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.executemany(
            "INSERT OR IGNORE INTO processed_hands (hand_hash, processed_at) VALUES (?, ?)",
            [(h, now) for h in hand_hashes],
        )
        self.conn.commit()

    def get_processed_hands_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM processed_hands")
        return cursor.fetchone()[0]

    def get_processed_hands_legacy_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands_legacy'"
        )
        if cursor.fetchone() is None:
            return 0
        cursor.execute("SELECT COUNT(*) FROM processed_hands_legacy")
        return cursor.fetchone()[0]

    # ========== PlayerStats CRUD ==========

    def get(self, player_name: str, table_type: TableType) -> PlayerStats | None:
        """查询单个玩家的统计数据。

        Args:
            player_name: 玩家名称。
            table_type: 桌型。

        Returns:
            PlayerStats 实例，如果不存在则返回 None。
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT player_name, table_type, vpip_positive, vpip_total,
                   preflop_stats_json, postflop_stats_json
            FROM player_stats
            WHERE player_name = ? AND table_type = ?
            """,
            (player_name, int(table_type)),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return player_stats_from_row(dict(row))

    def get_all(self, table_type: TableType | None = None) -> list[PlayerStats]:
        """查询所有玩家的统计数据。

        Args:
            table_type: 可选的桌型过滤条件。

        Returns:
            PlayerStats 列表。
        """
        cursor = self.conn.cursor()
        if table_type is not None:
            cursor.execute(
                """
                SELECT player_name, table_type, vpip_positive, vpip_total,
                       preflop_stats_json, postflop_stats_json
                FROM player_stats
                WHERE table_type = ?
                """,
                (int(table_type),),
            )
        else:
            cursor.execute(
                """
                SELECT player_name, table_type, vpip_positive, vpip_total,
                       preflop_stats_json, postflop_stats_json
                FROM player_stats
                """
            )
        return [player_stats_from_row(dict(row)) for row in cursor.fetchall()]

    def upsert(self, stats: PlayerStats) -> None:
        """插入或更新玩家统计数据（覆盖模式）。

        Args:
            stats: 要保存的 PlayerStats。
        """
        row = player_stats_to_row(stats)
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO player_stats (
                player_name, table_type, vpip_positive, vpip_total,
                preflop_stats_json, postflop_stats_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_name, table_type) DO UPDATE SET
                vpip_positive = excluded.vpip_positive,
                vpip_total = excluded.vpip_total,
                preflop_stats_json = excluded.preflop_stats_json,
                postflop_stats_json = excluded.postflop_stats_json,
                updated_at = excluded.updated_at
            """,
            (
                row["player_name"],
                row["table_type"],
                row["vpip_positive"],
                row["vpip_total"],
                row["preflop_stats_json"],
                row["postflop_stats_json"],
                now,
                now,
            ),
        )
        self.conn.commit()

    def upsert_with_merge(self, new_stats: PlayerStats) -> None:
        """插入或累加合并玩家统计数据。

        如果玩家已存在，则将新数据累加到现有数据；否则直接插入。

        Args:
            new_stats: 要累加的 PlayerStats。
        """
        existing = self.get(new_stats.player_name, new_stats.table_type)
        if existing:
            merge_player_stats(existing, new_stats)
            self.upsert(existing)
        else:
            self.upsert(new_stats)

    def upsert_batch(self, stats_list: list[PlayerStats]) -> None:
        """批量插入或更新（覆盖模式）。

        Args:
            stats_list: PlayerStats 列表。
        """
        for stats in stats_list:
            self.upsert(stats)

    def upsert_batch_with_merge(self, stats_map: dict[str, PlayerStats]) -> None:
        """批量插入或累加合并。

        Args:
            stats_map: 玩家名称 -> PlayerStats 的字典。
        """
        if not stats_map:
            return

        stats_list = list(stats_map.values())
        keys = [(s.player_name, int(s.table_type)) for s in stats_list]

        existing_map: dict[tuple[str, int], PlayerStats] = {}
        cursor = self.conn.cursor()

        chunk_size = 450
        for i in range(0, len(keys), chunk_size):
            chunk_keys = keys[i : i + chunk_size]
            conditions = " OR ".join(
                ["(player_name = ? AND table_type = ?)"] * len(chunk_keys)
            )
            params = [v for k in chunk_keys for v in k]
            cursor.execute(
                f"""
                SELECT player_name, table_type, vpip_positive, vpip_total,
                       preflop_stats_json, postflop_stats_json
                FROM player_stats
                WHERE {conditions}
                """,
                params,
            )
            for row in cursor.fetchall():
                ps = player_stats_from_row(dict(row))
                existing_map[(ps.player_name, int(ps.table_type))] = ps

        now = datetime.now().isoformat()
        rows_to_upsert = []

        for new_stats in stats_list:
            key = (new_stats.player_name, int(new_stats.table_type))
            existing = existing_map.get(key)
            if existing:
                merge_player_stats(existing, new_stats)
                final = existing
            else:
                final = new_stats

            row = player_stats_to_row(final)
            rows_to_upsert.append((
                row["player_name"],
                row["table_type"],
                row["vpip_positive"],
                row["vpip_total"],
                row["preflop_stats_json"],
                row["postflop_stats_json"],
                now,
                now,
            ))

        cursor.executemany(
            """
            INSERT INTO player_stats (
                player_name, table_type, vpip_positive, vpip_total,
                preflop_stats_json, postflop_stats_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_name, table_type) DO UPDATE SET
                vpip_positive = excluded.vpip_positive,
                vpip_total = excluded.vpip_total,
                preflop_stats_json = excluded.preflop_stats_json,
                postflop_stats_json = excluded.postflop_stats_json,
                updated_at = excluded.updated_at
            """,
            rows_to_upsert,
        )
        self.conn.commit()

    # ========== 统计信息 ==========

    def get_stats(self) -> dict[str, int]:
        """获取仓库统计信息。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM player_stats")
        player_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM processed_hands")
        hands_count = cursor.fetchone()[0]
        legacy_count = self.get_processed_hands_legacy_count()
        return {
            "player_count": player_count,
            "processed_hands_count": hands_count,
            "processed_hands_legacy_count": legacy_count,
        }

    def clear(self) -> None:
        """清空所有数据（谨慎使用）。"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM player_stats")
        cursor.execute("DELETE FROM processed_hands")
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands_legacy'"
        )
        if cursor.fetchone() is not None:
            cursor.execute("DELETE FROM processed_hands_legacy")
        self.conn.commit()
        LOGGER.warning("已清空 player_stats 和 processed_hands 表")
