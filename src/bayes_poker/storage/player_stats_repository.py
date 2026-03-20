"""PlayerStats SQLite 存储仓库。

提供 PlayerStats 的持久化存储，包括：
- 去重：通过 processed_hands 表追踪已处理的手牌 ID
- 读取：使用 Rust 二进制格式 (stats_binary)

注意：写入操作已移至 Rust API (poker_stats_rs.py_batch_process_phhs)。
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import (
    PlayerMetricsSummary,
    PlayerStats,
)
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

_CREATE_METRICS_SUMMARY_TABLE = """
CREATE TABLE IF NOT EXISTS player_metrics_summary (
    player_name TEXT    NOT NULL,
    table_type  INTEGER NOT NULL,
    total_hands INTEGER NOT NULL,
    vpip_pos    INTEGER NOT NULL,
    vpip_total  INTEGER NOT NULL,
    pfr_pos     INTEGER NOT NULL,
    pfr_total   INTEGER NOT NULL,
    agg_pos     INTEGER NOT NULL,
    agg_total   INTEGER NOT NULL,
    wtp_pos     INTEGER NOT NULL,
    wtp_total   INTEGER NOT NULL,
    vpip_mean   REAL,
    vpip_sigma  REAL,
    pfr_mean    REAL,
    pfr_sigma   REAL,
    agg_mean    REAL,
    agg_sigma   REAL,
    wtp_mean    REAL,
    wtp_sigma   REAL,
    PRIMARY KEY (player_name, table_type)
)
"""

_ALTER_METRICS_SUMMARY_ADD_BASE_MODEL_COLS = [
    "ALTER TABLE player_metrics_summary ADD COLUMN vpip_mean  REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN vpip_sigma REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN pfr_mean   REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN pfr_sigma  REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN agg_mean   REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN agg_sigma  REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN wtp_mean   REAL",
    "ALTER TABLE player_metrics_summary ADD COLUMN wtp_sigma  REAL",
]

_CREATE_METRICS_SUMMARY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_player_metrics_summary_tt_name
ON player_metrics_summary(table_type, player_name)
"""

_UPSERT_METRICS_SUMMARY = """
INSERT OR REPLACE INTO player_metrics_summary (
    player_name,
    table_type,
    total_hands,
    vpip_pos,
    vpip_total,
    pfr_pos,
    pfr_total,
    agg_pos,
    agg_total,
    wtp_pos,
    wtp_total,
    vpip_mean,
    vpip_sigma,
    pfr_mean,
    pfr_sigma,
    agg_mean,
    agg_sigma,
    wtp_mean,
    wtp_sigma
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_POOL_PRIOR_PLAYER_NAMES: dict[TableType, str] = {
    TableType.SIX_MAX: "aggregated_sixmax_100",
}


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
                cursor.execute(
                    "ALTER TABLE processed_hands RENAME TO processed_hands_legacy"
                )
            else:
                cursor.execute("DROP TABLE processed_hands")

            cursor.execute(CREATE_PROCESSED_HANDS_TABLE)
            return

        cursor.execute("DROP TABLE processed_hands")
        cursor.execute(CREATE_PROCESSED_HANDS_TABLE)

    def _create_metrics_summary_table(self, cursor: sqlite3.Cursor) -> None:
        """创建轻量指标 summary 表，并确保 base_model 列存在.

        对已有旧表自动执行 ALTER TABLE 补列（幂等）.

        Args:
            cursor: SQLite 游标.

        Returns:
            None.
        """

        cursor.execute(_CREATE_METRICS_SUMMARY_TABLE)
        cursor.execute(_CREATE_METRICS_SUMMARY_INDEX)
        # 确保 base_model 列存在（旧表迁移）
        cursor.execute("PRAGMA table_info(player_metrics_summary)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        for alter_sql in _ALTER_METRICS_SUMMARY_ADD_BASE_MODEL_COLS:
            col_name = alter_sql.split("ADD COLUMN")[1].strip().split()[0]
            if col_name not in existing_cols:
                cursor.execute(alter_sql)

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

    def get(
        self,
        player_name: str,
        table_type: TableType,
    ) -> PlayerStats | None:
        """查询单个玩家的统计数据。

        Args:
            player_name: 玩家名称。
            table_type: 桌型。

        Returns:
            PlayerStats 实例。
            当目标玩家不存在且存在桌型聚合玩家时，返回聚合玩家统计。
            两者都不存在时返回 None。
        """
        raw_stats = self._get_raw(player_name, table_type)
        if raw_stats is None:
            pool_player_name = _POOL_PRIOR_PLAYER_NAMES.get(table_type)
            if not pool_player_name or player_name == pool_player_name:
                return None
            return self._get_raw(pool_player_name, table_type)
        return raw_stats

    def _get_raw(self, player_name: str, table_type: TableType) -> PlayerStats | None:
        """查询原始玩家统计。

        Args:
            player_name: 玩家名称。
            table_type: 桌型。

        Returns:
            未做后验平滑的原始 `PlayerStats`。
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

    def load_all_for_estimator(self, table_type: TableType) -> list[PlayerStats]:
        """加载全量 PlayerStats 供 OpponentEstimator 初始化。

        复用现有 player_stats_from_binary 反序列化，按 table_type 过滤。
        会排除 aggregated_* 聚合先验玩家（避免污染相似玩家搜索结果），
        并按玩家名稳定排序（保证 random_seed 可复现性与数据库顺序无关）。

        Args:
            table_type: 桌型过滤条件。

        Returns:
            指定桌型的玩家 PlayerStats 列表（已排除聚合玩家，按名称排序）。
        """
        stats_list = self.get_all(table_type=table_type)
        filtered = [
            stats
            for stats in stats_list
            if not stats.player_name.casefold().startswith("aggregated_")
        ]
        filtered.sort(key=lambda s: s.player_name.casefold())
        return filtered

    def summary_table_exists(self) -> bool:
        """检查 summary 表是否存在.

        Returns:
            `player_metrics_summary` 表是否存在.
        """

        return self._table_exists("player_metrics_summary")

    def build_metrics_summary(
        self,
        table_type: TableType,
        *,
        batch_size: int = 500,
    ) -> int:
        """为估计器构建轻量指标 summary 表（含预计算 BaseModel 高斯参数）.

        两阶段流程：
        1. 反序列化全量 player_stats，写入整数计数字段（VPIP/PFR/AGG/WTP）。
        2. 用全量 summary 构建全局先验直方图，再逐玩家计算 BaseModel 高斯参数并回写。

        Args:
            table_type: 桌型过滤条件.
            batch_size: 每批反序列化并写入的玩家数量.

        Returns:
            实际写入或覆盖的 summary 行数.

        Raises:
            ValueError: 当 `batch_size` 小于等于 0 时抛出.
        """

        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")

        if not self._table_exists("player_stats"):
            return 0

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = self.conn.cursor()
            self._create_metrics_summary_table(cursor)
            cursor.execute(
                "DELETE FROM player_metrics_summary WHERE table_type = ?",
                (int(table_type),),
            )

            read_cursor = self.conn.cursor()
            write_cursor = self.conn.cursor()
            read_cursor.execute(
                """
                SELECT player_name, stats_binary
                FROM player_stats
                WHERE table_type = ?
                ORDER BY player_name
                """,
                (int(table_type),),
            )

            written = 0
            while rows := read_cursor.fetchmany(batch_size):
                batch_payload: list[tuple[int | str, ...]] = []
                for row in rows:
                    player_name = str(row["player_name"])
                    if player_name.casefold().startswith("aggregated_"):
                        continue

                    stats = player_stats_from_binary(row["stats_binary"])
                    pfr_pos, pfr_total = calculate_pfr(stats)
                    agg_pos, agg_total = calculate_aggression(stats)
                    wtp_pos, wtp_total = calculate_wtp(stats)
                    batch_payload.append(
                        (
                            player_name,
                            int(table_type),
                            stats.vpip.total,
                            stats.vpip.positive,
                            stats.vpip.total,
                            pfr_pos,
                            pfr_total,
                            agg_pos,
                            agg_total,
                            wtp_pos,
                            wtp_total,
                            # base_model 列暂写 NULL，第二阶段回填
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                    )

                if not batch_payload:
                    continue

                write_cursor.executemany(_UPSERT_METRICS_SUMMARY, batch_payload)
                written += len(batch_payload)

            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        # ── 阶段 2：预计算 BaseModel 高斯参数并回填 ──────────────────
        self._build_and_store_base_models(table_type, batch_size=batch_size)
        return written

    def _build_and_store_base_models(
        self,
        table_type: TableType,
        *,
        batch_size: int = 2000,
    ) -> None:
        """用 summary 表中的整数计数构建全局先验，逐玩家计算 BaseModel 并回写.

        Args:
            table_type: 桌型.
            batch_size: 每批回写的玩家数量.

        Returns:
            None.
        """
        from bayes_poker.player_metrics.hist_distribution import HistDistribution
        from bayes_poker.player_metrics.opponent_estimator import (
            OpponentEstimator,
            OpponentEstimatorOptions,
        )

        opts = OpponentEstimatorOptions()

        # 读取全量整数计数（不含高斯列）
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT player_name, vpip_pos, vpip_total,
                   pfr_pos, pfr_total, agg_pos, agg_total, wtp_pos, wtp_total
            FROM player_metrics_summary
            WHERE table_type = ?
            ORDER BY player_name
            """,
            (int(table_type),),
        )
        rows = cursor.fetchall()
        if not rows:
            return

        # 构建先验直方图
        vpip_prior = HistDistribution(opts.prior_num_bins)
        pfr_prior = HistDistribution(opts.prior_num_bins)
        agg_prior = HistDistribution(opts.prior_num_bins)
        wtp_prior = HistDistribution(opts.prior_num_bins)
        for row in rows:
            if row["vpip_total"] > opts.min_samples:
                vpip_prior.add_sample(row["vpip_pos"] / row["vpip_total"])
            if row["pfr_total"] > opts.min_samples:
                pfr_prior.add_sample(row["pfr_pos"] / row["pfr_total"])
            if row["agg_total"] > opts.min_samples:
                agg_prior.add_sample(row["agg_pos"] / row["agg_total"])
            if row["wtp_total"] > opts.min_samples:
                wtp_prior.add_sample(row["wtp_pos"] / row["wtp_total"])
        vpip_prior.normalize()
        pfr_prior.normalize()
        agg_prior.normalize()
        wtp_prior.normalize()

        # 构建临时 estimator（仅用于调用 _estimate_gaussian）
        import random

        _tmp = OpponentEstimator.__new__(OpponentEstimator)
        _tmp._options = opts
        _tmp._rng = random.Random(0)
        _tmp._vpip_prior = vpip_prior
        _tmp._pfr_prior = pfr_prior
        _tmp._aggression_prior = agg_prior
        _tmp._wtp_prior = wtp_prior

        # 逐批计算并回写
        update_sql = """
            UPDATE player_metrics_summary
            SET vpip_mean=?, vpip_sigma=?,
                pfr_mean=?,  pfr_sigma=?,
                agg_mean=?,  agg_sigma=?,
                wtp_mean=?,  wtp_sigma=?
            WHERE player_name=? AND table_type=?
        """
        write_cursor = self.conn.cursor()

        batch: list[tuple[float, ...]] = []
        for row in rows:
            vt = row["vpip_total"]
            if vt <= 0:
                # 样本不足：写 NULL，load 时会在内存中重建
                continue
            vg = OpponentEstimator._estimate_gaussian(
                _tmp, vpip_prior, row["vpip_pos"], vt
            )
            pg = OpponentEstimator._estimate_gaussian(
                _tmp, pfr_prior, row["pfr_pos"], row["pfr_total"]
            )
            ag = OpponentEstimator._estimate_gaussian(
                _tmp, agg_prior, row["agg_pos"], row["agg_total"]
            )
            wg = OpponentEstimator._estimate_gaussian(
                _tmp, wtp_prior, row["wtp_pos"], row["wtp_total"]
            )
            batch.append(
                (
                    vg.mean,
                    vg.sigma,
                    pg.mean,
                    pg.sigma,
                    ag.mean,
                    ag.sigma,
                    wg.mean,
                    wg.sigma,
                    row["player_name"],
                    int(table_type),
                )
            )
            if len(batch) >= batch_size:
                self.conn.execute("BEGIN IMMEDIATE")
                try:
                    write_cursor.executemany(update_sql, batch)
                    self.conn.commit()
                except Exception:
                    self.conn.rollback()
                    raise
                batch.clear()

        if batch:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                write_cursor.executemany(update_sql, batch)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def load_summary_for_estimator(
        self,
        table_type: TableType,
    ) -> list[PlayerMetricsSummary]:
        """读取估计器初始化所需的轻量指标 summary（含预计算 BaseModel 高斯参数）.

        Args:
            table_type: 桌型过滤条件.

        Returns:
            轻量指标列表. 若 summary 表不存在则返回空列表.
            若 base_model 列已预计算，返回的 summary 携带高斯参数，
            估计器可跳过 _estimate_gaussian 直接构建 BaseModel.
        """

        if not self.summary_table_exists():
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                player_name,
                total_hands,
                vpip_pos,
                vpip_total,
                pfr_pos,
                pfr_total,
                agg_pos,
                agg_total,
                wtp_pos,
                wtp_total,
                vpip_mean,
                vpip_sigma,
                pfr_mean,
                pfr_sigma,
                agg_mean,
                agg_sigma,
                wtp_mean,
                wtp_sigma
            FROM player_metrics_summary
            WHERE table_type = ?
              AND player_name NOT LIKE 'aggregated_%'
            ORDER BY player_name
            """,
            (int(table_type),),
        )

        def _float_or_none(val: object) -> float | None:
            return float(val) if val is not None else None

        return [
            PlayerMetricsSummary(
                player_name=str(row["player_name"]),
                table_type=table_type,
                total_hands=int(row["total_hands"]),
                vpip_pos=int(row["vpip_pos"]),
                vpip_total=int(row["vpip_total"]),
                pfr_pos=int(row["pfr_pos"]),
                pfr_total=int(row["pfr_total"]),
                agg_pos=int(row["agg_pos"]),
                agg_total=int(row["agg_total"]),
                wtp_pos=int(row["wtp_pos"]),
                wtp_total=int(row["wtp_total"]),
                vpip_mean=_float_or_none(row["vpip_mean"]),
                vpip_sigma=_float_or_none(row["vpip_sigma"]),
                pfr_mean=_float_or_none(row["pfr_mean"]),
                pfr_sigma=_float_or_none(row["pfr_sigma"]),
                agg_mean=_float_or_none(row["agg_mean"]),
                agg_sigma=_float_or_none(row["agg_sigma"]),
                wtp_mean=_float_or_none(row["wtp_mean"]),
                wtp_sigma=_float_or_none(row["wtp_sigma"]),
            )
            for row in cursor.fetchall()
        ]

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
