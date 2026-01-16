"""PlayerStats SQLite 存储仓库。

提供 PlayerStats 的持久化存储，包括：
- 去重：通过 processed_hands 表追踪已处理的手牌 ID
- 读取：使用 Rust 二进制格式 (stats_binary)

注意：写入操作已移至 Rust API (poker_stats_rs.py_batch_process_phhs)。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.player_metrics.serialization import player_stats_from_binary

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

# SQL 语句
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
    """PlayerStats 的 SQLite 存储仓库（只读）。

    数据写入由 Rust API 处理，此仓库仅提供读取功能。

    用法：
        with PlayerStatsRepository("data/player_stats.db") as repo:
            stats = repo.get("PlayerName", TableType.SIX_MAX)
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
        self._ensure_processed_hands_schema(cursor)
        # 只在 player_stats 表存在时创建索引
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='player_stats'"
        )
        if cursor.fetchone() is not None:
            cursor.executescript(CREATE_INDEXES)
        self.conn.commit()

    def _ensure_processed_hands_schema(self, cursor: sqlite3.Cursor) -> None:
        """确保 processed_hands 表使用正确的 schema。"""
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
        """检查手牌是否已处理。"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_hands WHERE hand_hash = ?",
            (hand_hash,),
        )
        return cursor.fetchone() is not None

    def get_processed_hand_hashes(self, hand_hashes: Sequence[str]) -> set[str]:
        """批量检查手牌是否已处理。"""
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
        """标记单个手牌为已处理。"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT OR IGNORE INTO processed_hands (hand_hash, processed_at) VALUES (?, ?)",
            (hand_hash, now),
        )
        self.conn.commit()

    def mark_hands_processed(self, hand_hashes: Sequence[str]) -> None:
        """批量标记手牌为已处理。"""
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
        """获取已处理手牌数量。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM processed_hands")
        return cursor.fetchone()[0]

    def get_processed_hands_legacy_count(self) -> int:
        """获取旧版手牌记录数量。"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands_legacy'"
        )
        if cursor.fetchone() is None:
            return 0
        cursor.execute("SELECT COUNT(*) FROM processed_hands_legacy")
        return cursor.fetchone()[0]

    # ========== PlayerStats 查询 ==========

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
            "SELECT stats_binary FROM player_stats WHERE player_name = ? AND table_type = ?",
            (player_name, int(table_type)),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return player_stats_from_binary(row[0])

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
                "SELECT stats_binary FROM player_stats WHERE table_type = ?",
                (int(table_type),),
            )
        else:
            cursor.execute("SELECT stats_binary FROM player_stats")
        return [player_stats_from_binary(row[0]) for row in cursor.fetchall()]

    # ========== 统计信息 ==========

    def _table_exists(self, table_name: str) -> bool:
        """检查表是否存在。"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def get_stats(self) -> dict[str, int]:
        """获取仓库统计信息。"""
        cursor = self.conn.cursor()

        player_count = 0
        if self._table_exists("player_stats"):
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

        if self._table_exists("player_stats"):
            cursor.execute("DELETE FROM player_stats")

        cursor.execute("DELETE FROM processed_hands")

        if self._table_exists("processed_hands_legacy"):
            cursor.execute("DELETE FROM processed_hands_legacy")

        self.conn.commit()
        LOGGER.warning("已清空 player_stats 和 processed_hands 表")
