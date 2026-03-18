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
from typing import TYPE_CHECKING, Sequence, cast

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import (
    ActionStats,
    PlayerMetricsSummary,
    PlayerStats,
)
from bayes_poker.player_metrics.params import PostFlopParams
from bayes_poker.player_metrics.posterior import (
    ActionSpaceKind,
    ActionSpaceSpec,
    BET_0_40_FIELD,
    BET_40_80_FIELD,
    BET_80_120_FIELD,
    BET_OVER_120_FIELD,
    CHECK_CALL_FIELD,
    FOLD_FIELD,
    RAISE_FIELD,
    classify_postflop_action_space,
    smooth_binary_counts,
    smooth_multinomial_counts,
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

_DEFAULT_MULTINOMIAL_ACTION_SPACE = ActionSpaceSpec(
    kind=ActionSpaceKind.MULTINOMIAL,
    total_fields=(
        FOLD_FIELD,
        CHECK_CALL_FIELD,
        RAISE_FIELD,
    ),
)

_BINARY_FOLD_RAISE_ACTION_SPACE = ActionSpaceSpec(
    kind=ActionSpaceKind.BINARY,
    total_fields=(
        FOLD_FIELD,
        RAISE_FIELD,
    ),
    positive_field=RAISE_FIELD,
)

_BINARY_CHECK_RAISE_ACTION_SPACE = ActionSpaceSpec(
    kind=ActionSpaceKind.BINARY,
    total_fields=(
        CHECK_CALL_FIELD,
        RAISE_FIELD,
    ),
    positive_field=RAISE_FIELD,
)


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
        *,
        smooth_with_pool: bool = False,
        pool_prior_strength: float = 20.0,
    ) -> PlayerStats | None:
        """查询单个玩家的统计数据。

        Args:
            player_name: 玩家名称。
            table_type: 桌型。
            smooth_with_pool: 是否按玩家池做后验平滑。
            pool_prior_strength: 玩家池先验强度。

        Returns:
            PlayerStats 实例。
            当目标玩家不存在且存在桌型聚合玩家时，返回聚合玩家统计。
            两者都不存在时返回 None。

        Raises:
            ValueError: 当先验强度不为正时抛出。
        """
        raw_stats = self._get_raw(player_name, table_type)
        if raw_stats is None:
            pool_player_name = _POOL_PRIOR_PLAYER_NAMES.get(table_type)
            if not pool_player_name or player_name == pool_player_name:
                return None
            return self._get_raw(pool_player_name, table_type)

        if not smooth_with_pool:
            return raw_stats

        if pool_prior_strength <= 0.0:
            raise ValueError("pool_prior_strength 必须大于 0.")

        pool_player_name = _POOL_PRIOR_PLAYER_NAMES.get(table_type)
        if not pool_player_name or player_name == pool_player_name:
            return raw_stats

        pool_stats = self._get_raw(pool_player_name, table_type)
        if pool_stats is None:
            return raw_stats

        return self._smooth_player_stats_with_pool(
            raw_stats=raw_stats,
            pool_stats=pool_stats,
            pool_prior_strength=pool_prior_strength,
        )

    def get_with_raw(
        self,
        player_name: str,
        table_type: TableType,
        *,
        pool_prior_strength: float = 20.0,
    ) -> tuple[PlayerStats | None, PlayerStats | None]:
        """一次读取, 同时返回 (raw_stats, smoothed_stats).

        避免 stats_adapter 需要两次调用 get() 的性能问题.
        内部复用 _get_raw() 和 _smooth_player_stats_with_pool().

        Args:
            player_name: 玩家名称.
            table_type: 桌型.
            pool_prior_strength: 平滑时使用的先验强度.

        Returns:
            元组 (raw_stats, smoothed_stats).
            若玩家不存在则返回 (None, None).

        Raises:
            ValueError: 当先验强度不为正时抛出.
        """
        raw_stats = self._get_raw(player_name, table_type)
        if raw_stats is None:
            return None, None

        if pool_prior_strength <= 0.0:
            raise ValueError("pool_prior_strength 必须大于 0.")

        pool_player_name = _POOL_PRIOR_PLAYER_NAMES.get(table_type)
        if not pool_player_name or player_name == pool_player_name:
            return raw_stats, raw_stats

        pool_stats = self._get_raw(pool_player_name, table_type)
        if pool_stats is None:
            return raw_stats, raw_stats

        smoothed = self._smooth_player_stats_with_pool(
            raw_stats=raw_stats,
            pool_stats=pool_stats,
            pool_prior_strength=pool_prior_strength,
        )
        return raw_stats, smoothed

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

    def _smooth_player_stats_with_pool(
        self,
        *,
        raw_stats: PlayerStats,
        pool_stats: PlayerStats,
        pool_prior_strength: float,
    ) -> PlayerStats:
        """按玩家池构造后验平滑后的统计视图。

        Args:
            raw_stats: 玩家原始统计。
            pool_stats: 玩家池统计。
            pool_prior_strength: 玩家池先验强度。

        Returns:
            平滑后的 `PlayerStats` 副本。
        """

        smoothed_stats = PlayerStats(
            player_name=raw_stats.player_name,
            table_type=raw_stats.table_type,
        )
        smoothed_stats.vpip = raw_stats.vpip
        smoothed_stats.preflop_stats = self._smooth_preflop_stats(
            raw_stats=raw_stats.preflop_stats,
            pool_stats=pool_stats.preflop_stats,
            table_type=raw_stats.table_type,
            pool_prior_strength=pool_prior_strength,
        )
        smoothed_stats.postflop_stats = self._smooth_postflop_stats(
            raw_stats=raw_stats.postflop_stats,
            pool_stats=pool_stats.postflop_stats,
            table_type=raw_stats.table_type,
            pool_prior_strength=pool_prior_strength,
        )
        return smoothed_stats

    def _smooth_preflop_stats(
        self,
        *,
        raw_stats: Sequence[ActionStats],
        pool_stats: Sequence[ActionStats],
        table_type: TableType,
        pool_prior_strength: float,
    ) -> list[ActionStats]:
        """平滑翻前统计数组。"""

        action_spaces = self._build_preflop_action_spaces(
            table_type=table_type,
            stats_count=len(raw_stats),
        )
        smoothed_stats: list[ActionStats] = []

        for index, raw_action_stats in enumerate(raw_stats):
            if index >= len(pool_stats):
                smoothed_stats.append(raw_action_stats)
                continue

            smoothed_stats.append(
                self._smooth_action_stats(
                    raw_action_stats=raw_action_stats,
                    pool_action_stats=pool_stats[index],
                    action_space=action_spaces[index],
                    pool_prior_strength=pool_prior_strength,
                )
            )

        return smoothed_stats

    def _build_preflop_action_spaces(
        self,
        *,
        table_type: TableType,
        stats_count: int,
    ) -> tuple[ActionSpaceSpec, ...]:
        """构造与 Rust preflop 桶索引对齐的动作空间定义。

        Args:
            table_type: 桌型。
            stats_count: 当前统计数组长度。

        Returns:
            与统计数组等长的动作空间定义元组。
        """

        if stats_count <= 0:
            return ()

        if table_type == TableType.HEADS_UP:
            return tuple(
                self._resolve_heads_up_preflop_action_space(index)
                for index in range(stats_count)
            )

        return tuple(
            self._resolve_six_max_preflop_action_space(index)
            for index in range(stats_count)
        )

    def _resolve_heads_up_preflop_action_space(self, index: int) -> ActionSpaceSpec:
        """返回与 HU preflop 索引对应的动作空间。"""

        if index == 5:
            return _BINARY_CHECK_RAISE_ACTION_SPACE
        return _DEFAULT_MULTINOMIAL_ACTION_SPACE

    def _resolve_six_max_preflop_action_space(self, index: int) -> ActionSpaceSpec:
        """返回与 6-max preflop 索引对应的动作空间。

        这里显式复刻 Rust `PreFlopParams::to_index()` 的 54 桶布局:
        - `0..29`: `previous_action == Fold` 的 6 个位置 * 5 个 spot。
        - `30..53`: 其余“已投入/已行动后再次决策”的 24 个 spot。

        其中只有以下 spot 是二元节点:
        - 非盲位无人入池首动: `fold / bet_raise`
        - BB 在无人加注时的过牌位: `check_call / bet_raise`
        - BB 在 limp pot 中的过牌位: `check_call / bet_raise`
        其余 preflop 桶统一视为三元 `fold / check_call / bet_raise`。
        """

        if index >= 30:
            return _DEFAULT_MULTINOMIAL_ACTION_SPACE

        position_index = index // 5
        spot_index = index % 5
        is_small_blind = position_index == 0
        is_big_blind = position_index == 1

        if spot_index == 0:
            if is_big_blind:
                return _BINARY_CHECK_RAISE_ACTION_SPACE
            if not is_small_blind:
                return _BINARY_FOLD_RAISE_ACTION_SPACE
            return _DEFAULT_MULTINOMIAL_ACTION_SPACE

        if spot_index == 1 and is_big_blind:
            return _BINARY_CHECK_RAISE_ACTION_SPACE

        return _DEFAULT_MULTINOMIAL_ACTION_SPACE

    def _smooth_postflop_stats(
        self,
        *,
        raw_stats: Sequence[ActionStats],
        pool_stats: Sequence[ActionStats],
        table_type: TableType,
        pool_prior_strength: float,
    ) -> list[ActionStats]:
        """平滑翻后统计数组。"""

        params_list = PostFlopParams.get_all_params(table_type)
        smoothed_stats: list[ActionStats] = []

        for index, raw_action_stats in enumerate(raw_stats):
            if index >= len(pool_stats):
                smoothed_stats.append(raw_action_stats)
                continue

            action_space = (
                classify_postflop_action_space(
                    params_list[index],
                    raw_field_counts=self._extract_field_counts(raw_action_stats),
                    pool_field_counts=self._extract_field_counts(pool_stats[index]),
                )
                if index < len(params_list)
                else _DEFAULT_MULTINOMIAL_ACTION_SPACE
            )
            smoothed_stats.append(
                self._smooth_action_stats(
                    raw_action_stats=raw_action_stats,
                    pool_action_stats=pool_stats[index],
                    action_space=action_space,
                    pool_prior_strength=pool_prior_strength,
                )
            )

        return smoothed_stats

    def _smooth_action_stats(
        self,
        *,
        raw_action_stats: ActionStats,
        pool_action_stats: ActionStats,
        action_space: ActionSpaceSpec,
        pool_prior_strength: float,
    ) -> ActionStats:
        """平滑单个 `ActionStats`。"""

        raw_counts = self._extract_field_counts(raw_action_stats)
        pool_counts = self._extract_field_counts(pool_action_stats)
        prior_probabilities = self._build_prior_probabilities(
            total_fields=action_space.total_fields,
            field_counts=pool_counts,
        )

        smoothed_field_counts: dict[str, float]
        if action_space.kind == ActionSpaceKind.BINARY:
            positive_field = action_space.positive_field
            assert positive_field is not None
            total_count = sum(
                raw_counts[field_name] for field_name in action_space.total_fields
            )
            positive_count = raw_counts[positive_field]
            positive_index = action_space.total_fields.index(positive_field)
            positive_probability = prior_probabilities[positive_index]
            posterior_counts = smooth_binary_counts(
                prior_probability=positive_probability,
                prior_strength=pool_prior_strength,
                positive_count=positive_count,
                total_count=total_count,
            )
            negative_field = next(
                field_name
                for field_name in action_space.total_fields
                if field_name != positive_field
            )
            smoothed_field_counts = {
                positive_field: posterior_counts.positive,
                negative_field: posterior_counts.total - posterior_counts.positive,
            }
        else:
            pseudo_counts = smooth_multinomial_counts(
                prior_probabilities=prior_probabilities,
                prior_strength=pool_prior_strength,
                counts=tuple(
                    raw_counts[field_name] for field_name in action_space.total_fields
                ),
            )
            smoothed_field_counts = {
                field_name: pseudo_count
                for field_name, pseudo_count in zip(
                    action_space.total_fields,
                    pseudo_counts,
                    strict=True,
                )
            }

        return self._build_action_stats_from_field_counts(
            smoothed_field_counts=smoothed_field_counts,
        )

    def _extract_field_counts(
        self,
        action_stats: ActionStats,
    ) -> dict[str, float]:
        """提取 `ActionStats` 的叶子字段计数。"""

        return {
            BET_0_40_FIELD: float(action_stats.bet_0_40),
            BET_40_80_FIELD: float(action_stats.bet_40_80),
            BET_80_120_FIELD: float(action_stats.bet_80_120),
            BET_OVER_120_FIELD: float(action_stats.bet_over_120),
            RAISE_FIELD: float(action_stats.raise_samples),
            CHECK_CALL_FIELD: float(action_stats.check_call_samples),
            FOLD_FIELD: float(action_stats.fold_samples),
        }

    def _build_prior_probabilities(
        self,
        *,
        total_fields: tuple[str, ...],
        field_counts: dict[str, float],
    ) -> tuple[float, ...]:
        """根据玩家池计数构造先验概率向量。"""

        total_count = sum(field_counts[field_name] for field_name in total_fields)
        if total_count <= 0.0:
            uniform_probability = 1.0 / float(len(total_fields))
            return tuple(uniform_probability for _ in total_fields)

        return tuple(
            field_counts[field_name] / total_count for field_name in total_fields
        )

    def _build_action_stats_from_field_counts(
        self,
        *,
        smoothed_field_counts: dict[str, float],
    ) -> ActionStats:
        """按平滑后的叶子动作字段回填 `ActionStats`。"""

        return ActionStats(
            bet_0_40=cast(int, smoothed_field_counts.get(BET_0_40_FIELD, 0.0)),
            bet_40_80=cast(int, smoothed_field_counts.get(BET_40_80_FIELD, 0.0)),
            bet_80_120=cast(int, smoothed_field_counts.get(BET_80_120_FIELD, 0.0)),
            bet_over_120=cast(int, smoothed_field_counts.get(BET_OVER_120_FIELD, 0.0)),
            raise_samples=cast(int, smoothed_field_counts.get(RAISE_FIELD, 0.0)),
            check_call_samples=cast(
                int,
                smoothed_field_counts.get(CHECK_CALL_FIELD, 0.0),
            ),
            fold_samples=cast(int, smoothed_field_counts.get(FOLD_FIELD, 0.0)),
        )

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
                            None, None, None, None, None, None, None, None,
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
            batch.append((
                vg.mean, vg.sigma,
                pg.mean, pg.sigma,
                ag.mean, ag.sigma,
                wg.mean, wg.sigma,
                row["player_name"], int(table_type),
            ))
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
