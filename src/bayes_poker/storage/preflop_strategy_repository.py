"""翻前策略 sqlite 仓库."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bayes_poker.domain.table import Position
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.preflop_parse.serialization import (
    decode_preflop_range,
    encode_preflop_range,
)
from bayes_poker.strategy.range import PreflopRange

if TYPE_CHECKING:
    from collections.abc import Sequence

CREATE_STRATEGY_SOURCES_TABLE = """
CREATE TABLE IF NOT EXISTS strategy_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    source_dir TEXT NOT NULL,
    format_version INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(strategy_name, source_dir)
)
"""

CREATE_SOLVER_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS solver_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    stack_bb INTEGER NOT NULL,
    history_full TEXT NOT NULL,
    history_actions TEXT NOT NULL,
    history_token_count INTEGER NOT NULL,
    acting_position TEXT NOT NULL,
    source_file TEXT NOT NULL,
    actor_position TEXT,
    aggressor_position TEXT,
    call_count INTEGER NOT NULL,
    limp_count INTEGER NOT NULL,
    raise_time INTEGER NOT NULL,
    pot_size REAL NOT NULL,
    raise_size_bb REAL,
    is_in_position INTEGER,
    UNIQUE(source_id, stack_bb, history_full),
    FOREIGN KEY(source_id) REFERENCES strategy_sources(source_id)
)
"""

CREATE_SOLVER_ACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS solver_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    action_code TEXT NOT NULL,
    action_type TEXT NOT NULL,
    bet_size_bb REAL,
    is_all_in INTEGER NOT NULL,
    total_frequency REAL NOT NULL,
    next_position TEXT NOT NULL,
    strategy_blob BLOB NOT NULL,
    ev_blob BLOB NOT NULL,
    total_ev REAL NOT NULL,
    total_combos REAL NOT NULL,
    UNIQUE(node_id, order_index),
    FOREIGN KEY(node_id) REFERENCES solver_nodes(node_id)
)
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_solver_nodes_primary_match
ON solver_nodes(source_id, stack_bb, actor_position);

CREATE INDEX IF NOT EXISTS idx_solver_nodes_secondary_match
ON solver_nodes(source_id, stack_bb, actor_position, aggressor_position, call_count, limp_count, raise_time);

CREATE INDEX IF NOT EXISTS idx_solver_actions_node_id
ON solver_actions(node_id, order_index);
"""


@dataclass(frozen=True, slots=True)
class StrategySourceRecord:
    """策略源元信息记录.

    Attributes:
        source_id: 策略源主键。
        strategy_name: 策略名称。
        source_dir: 策略目录。
        format_version: 导入格式版本。
        imported_at: 导入时间戳。
    """

    source_id: int
    strategy_name: str
    source_dir: str
    format_version: int
    imported_at: str


@dataclass(frozen=True, slots=True)
class SolverNodeRecord:
    """sqlite 中的 solver 节点记录.

    Attributes:
        node_id: 节点主键。
        source_id: 所属策略源主键。
        stack_bb: 筹码深度（BB 数）。
        history_full: 完整历史。
        history_actions: 去量后的历史。
        history_token_count: 历史 token 数量。
        acting_position: 原始 acting position 字符串。
        source_file: 来源文件名。
        actor_position: 当前待行动位置。
        aggressor_position: 最后一次激进行动位置。
        call_count: 最后一次激进行动后的跟注人数。
        limp_count: 首个激进行动前的 limp 人数。
        raise_time: 当前节点前出现的加注次数。
        pot_size: 当前节点前底池大小（单位 BB）。
        raise_size_bb: 最后一次激进行动尺度。
        is_in_position: 当前待行动方相对 aggressor 是否有位置优势。
    """

    node_id: int
    source_id: int
    stack_bb: int
    history_full: str
    history_actions: str
    history_token_count: int
    acting_position: str
    source_file: str
    actor_position: Position | None
    aggressor_position: Position | None
    call_count: int
    limp_count: int
    raise_time: int
    pot_size: float
    raise_size_bb: float | None
    is_in_position: bool | None


@dataclass(frozen=True, slots=True)
class SolverActionRecord:
    """sqlite 中的 solver 动作记录.

    Attributes:
        node_id: 所属节点主键。
        order_index: 动作顺序索引。
        action_code: 动作代码。
        action_type: 动作类型。
        bet_size_bb: 动作尺度。
        is_all_in: 是否全下。
        total_frequency: 总体频率。
        next_position: 下一个行动位置。
        preflop_range: 解码后的 169 维策略范围。
        total_ev: 总 EV。
        total_combos: 总组合数。
    """

    node_id: int
    order_index: int
    action_code: str
    action_type: str
    bet_size_bb: float | None
    is_all_in: bool
    total_frequency: float
    next_position: str
    preflop_range: PreflopRange
    total_ev: float
    total_combos: float


class PreflopStrategyRepository:
    """翻前策略 sqlite 读写仓库."""

    def __init__(self, db_path: str | Path) -> None:
        """初始化仓库.

        Args:
            db_path: sqlite 数据库路径。
        """

        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """连接数据库并初始化 schema."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_tables()

    def close(self) -> None:
        """关闭数据库连接."""

        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PreflopStrategyRepository:
        """进入上下文并建立连接."""

        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """退出上下文并关闭连接."""

        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        """返回当前活动连接.

        Returns:
            活动中的 sqlite 连接。

        Raises:
            RuntimeError: 当仓库尚未连接时抛出。
        """

        if self._conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        return self._conn

    def _init_tables(self) -> None:
        """初始化表结构和索引."""

        cursor = self.conn.cursor()
        cursor.execute(CREATE_STRATEGY_SOURCES_TABLE)
        cursor.execute(CREATE_SOLVER_NODES_TABLE)
        cursor.execute(CREATE_SOLVER_ACTIONS_TABLE)
        cursor.executescript(CREATE_INDEXES)
        self.conn.commit()

    def upsert_source(
        self,
        *,
        strategy_name: str,
        source_dir: str,
        format_version: int,
    ) -> int:
        """写入或更新策略源.

        Args:
            strategy_name: 策略名称。
            source_dir: 策略目录。
            format_version: 导入格式版本。

        Returns:
            对应的 `source_id`。
        """

        imported_at = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO strategy_sources (
                strategy_name,
                source_dir,
                format_version,
                imported_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(strategy_name, source_dir) DO UPDATE SET
                format_version = excluded.format_version,
                imported_at = excluded.imported_at
            """,
            (
                strategy_name,
                source_dir,
                format_version,
                imported_at,
            ),
        )
        self.conn.commit()
        cursor.execute(
            """
            SELECT source_id
            FROM strategy_sources
            WHERE strategy_name = ? AND source_dir = ?
            """,
            (strategy_name, source_dir),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("写入策略源后未能读取回 source_id。")
        return int(row["source_id"])

    def list_sources(self) -> tuple[StrategySourceRecord, ...]:
        """列出所有策略源.

        Returns:
            策略源记录元组。
        """

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT source_id, strategy_name, source_dir, format_version, imported_at
            FROM strategy_sources
            ORDER BY source_id ASC
            """
        )
        return tuple(
            StrategySourceRecord(
                source_id=int(row["source_id"]),
                strategy_name=str(row["strategy_name"]),
                source_dir=str(row["source_dir"]),
                format_version=int(row["format_version"]),
                imported_at=str(row["imported_at"]),
            )
            for row in cursor.fetchall()
        )

    def insert_node(
        self,
        *,
        source_id: int,
        node_record: ParsedStrategyNodeRecord,
    ) -> int:
        """插入或覆盖单个节点.

        Args:
            source_id: 所属策略源主键。
            node_record: 节点记录。

        Returns:
            持久化后的 `node_id`。
        """

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO solver_nodes (
                source_id,
                stack_bb,
                history_full,
                history_actions,
                history_token_count,
                acting_position,
                source_file,
                actor_position,
                aggressor_position,
                call_count,
                limp_count,
                raise_time,
                pot_size,
                raise_size_bb,
                is_in_position
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, stack_bb, history_full) DO UPDATE SET
                history_actions = excluded.history_actions,
                history_token_count = excluded.history_token_count,
                acting_position = excluded.acting_position,
                source_file = excluded.source_file,
                actor_position = excluded.actor_position,
                aggressor_position = excluded.aggressor_position,
                call_count = excluded.call_count,
                limp_count = excluded.limp_count,
                raise_time = excluded.raise_time,
                pot_size = excluded.pot_size,
                raise_size_bb = excluded.raise_size_bb,
                is_in_position = excluded.is_in_position
            """,
            (
                source_id,
                node_record.stack_bb,
                node_record.history_full,
                node_record.history_actions,
                node_record.history_token_count,
                node_record.acting_position,
                node_record.source_file,
                _encode_position(node_record.actor_position),
                _encode_position(node_record.aggressor_position),
                node_record.call_count,
                node_record.limp_count,
                node_record.raise_time,
                node_record.pot_size,
                node_record.raise_size_bb,
                _encode_bool(node_record.is_in_position),
            ),
        )
        self.conn.commit()
        cursor.execute(
            """
            SELECT node_id
            FROM solver_nodes
            WHERE source_id = ? AND stack_bb = ? AND history_full = ?
            """,
            (source_id, node_record.stack_bb, node_record.history_full),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("节点写入后未能读取回 node_id。")
        return int(row["node_id"])

    def insert_nodes(
        self,
        *,
        source_id: int,
        node_records: Sequence[ParsedStrategyNodeRecord],
    ) -> dict[str, int]:
        """批量插入节点.

        Args:
            source_id: 所属策略源主键。
            node_records: 节点记录列表。

        Returns:
            以 `history_full` 为 key 的 `node_id` 映射。
        """

        inserted: dict[str, int] = {}
        for node_record in node_records:
            inserted[node_record.history_full] = self.insert_node(
                source_id=source_id,
                node_record=node_record,
            )
        return inserted

    def insert_actions(
        self,
        *,
        node_id: int,
        action_records: Sequence[ParsedStrategyActionRecord],
    ) -> None:
        """覆盖写入节点动作.

        Args:
            node_id: 所属节点主键。
            action_records: 动作记录序列。
        """

        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM solver_actions WHERE node_id = ?", (node_id,))
        if not action_records:
            self.conn.commit()
            return

        rows: list[tuple[object, ...]] = []
        for action_record in action_records:
            strategy_blob, ev_blob = encode_preflop_range(action_record.preflop_range)
            rows.append(
                (
                    node_id,
                    action_record.order_index,
                    action_record.action_code,
                    action_record.action_type,
                    action_record.bet_size_bb,
                    int(action_record.is_all_in),
                    action_record.total_frequency,
                    action_record.next_position,
                    strategy_blob,
                    ev_blob,
                    action_record.total_ev,
                    action_record.total_combos,
                )
            )

        cursor.executemany(
            """
            INSERT INTO solver_actions (
                node_id,
                order_index,
                action_code,
                action_type,
                bet_size_bb,
                is_all_in,
                total_frequency,
                next_position,
                strategy_blob,
                ev_blob,
                total_ev,
                total_combos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def list_candidates(
        self,
        *,
        source_id: int | None = None,
        source_ids: Sequence[int] | None = None,
        stack_bb: int | None = None,
        actor_position: Position | None = None,
        aggressor_position: Position | None = None,
        is_in_position: bool | None,
        raise_time: int,
        pot_size: float | None,
    ) -> list[SolverNodeRecord]:
        cursor = self.conn.cursor()

        query = """
            SELECT
                node_id,
                source_id,
                stack_bb,
                history_full,
                history_actions,
                history_token_count,
                acting_position,
                source_file,
                actor_position,
                aggressor_position,
                call_count,
                limp_count,
                raise_time,
                pot_size,
                raise_size_bb,
                is_in_position
            FROM solver_nodes
            WHERE raise_time = ?
              AND (
                    (actor_position IS NULL AND ? IS NULL)
                 OR actor_position = ?
              )
              AND (
                    (aggressor_position IS NULL AND ? IS NULL)
                 OR aggressor_position = ?
              )
              AND (
                    (is_in_position IS NULL AND ? IS NULL)
                 OR is_in_position = ?
              )
        """
        actor_position_value = (
            actor_position.value if actor_position is not None else None
        )
        aggressor_position_value = (
            aggressor_position.value if aggressor_position is not None else None
        )
        is_in_position_value = (
            int(is_in_position) if is_in_position is not None else None
        )
        params: list[Any] = [
            raise_time,
            actor_position_value,
            actor_position_value,
            aggressor_position_value,
            aggressor_position_value,
            is_in_position_value,
            is_in_position_value,
        ]

        if source_id is not None and source_ids is not None:
            raise ValueError("source_id 和 source_ids 不能同时指定。")

        if source_ids is not None:
            normalized_source_ids = tuple(source_ids)
            if not normalized_source_ids:
                raise ValueError("source_ids 不能为空。")
            placeholders = ",".join("?" for _ in normalized_source_ids)
            query += f" AND source_id IN ({placeholders})"
            params.extend(normalized_source_ids)
        if source_id is not None:
            query += " AND source_id = ?"
            params.append(source_id)
        if stack_bb is not None:
            query += " AND stack_bb = ?"
            params.append(stack_bb)

        query += """
            ORDER BY
                CASE
                    WHEN ? IS NULL THEN 0.0
                    ELSE ABS(pot_size - ?)
                END ASC,
                node_id ASC
        """
        params.extend([pot_size, pot_size])

        cursor.execute(query, tuple(params))
        return [_row_to_solver_node_record(row) for row in cursor.fetchall()]

    def list_limp_candidates(
        self,
        *,
        source_id: int | None = None,
        source_ids: Sequence[int] | None = None,
        stack_bb: int | None = None,
        actor_position: Position,
        pot_size: float | None,
    ) -> list[SolverNodeRecord]:
        cursor = self.conn.cursor()

        query = """
            SELECT
                node_id,
                source_id,
                stack_bb,
                history_full,
                history_actions,
                history_token_count,
                acting_position,
                source_file,
                actor_position,
                aggressor_position,
                call_count,
                limp_count,
                raise_time,
                pot_size,
                raise_size_bb,
                is_in_position
            FROM solver_nodes
            WHERE raise_time = 0
              AND actor_position = ?
        """
        params: list[Any] = [actor_position.value]

        if source_id is not None and source_ids is not None:
            raise ValueError("source_id 和 source_ids 不能同时指定。")

        if source_ids is not None:
            normalized_source_ids = tuple(source_ids)
            if not normalized_source_ids:
                raise ValueError("source_ids 不能为空。")
            placeholders = ",".join("?" for _ in normalized_source_ids)
            query += f" AND source_id IN ({placeholders})"
            params.extend(normalized_source_ids)
        if source_id is not None:
            query += " AND source_id = ?"
            params.append(source_id)
        if stack_bb is not None:
            query += " AND stack_bb = ?"
            params.append(stack_bb)

        query += """
            ORDER BY
                CASE
                    WHEN ? IS NULL THEN 0.0
                    ELSE ABS(pot_size - ?)
                END ASC,
                node_id ASC
        """
        params.extend([pot_size, pot_size])

        cursor.execute(query, tuple(params))
        return [_row_to_solver_node_record(row) for row in cursor.fetchall()]

    def get_actions_for_nodes(
        self,
        node_ids: Sequence[int],
    ) -> dict[int, tuple[SolverActionRecord, ...]]:
        """批量读取多个节点的动作.

        Args:
            node_ids: 节点主键序列。

        Returns:
            以 `node_id` 为 key 的动作元组映射。
        """

        if not node_ids:
            return {}

        placeholders = ",".join("?" for _ in node_ids)
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT
                node_id,
                order_index,
                action_code,
                action_type,
                bet_size_bb,
                is_all_in,
                total_frequency,
                next_position,
                strategy_blob,
                ev_blob,
                total_ev,
                total_combos
            FROM solver_actions
            WHERE node_id IN ({placeholders})
            ORDER BY node_id ASC, order_index ASC
            """,
            tuple(node_ids),
        )

        grouped: dict[int, list[SolverActionRecord]] = {}
        for row in cursor.fetchall():
            record = _row_to_solver_action_record(row)
            grouped.setdefault(record.node_id, []).append(record)
        return {node_id: tuple(records) for node_id, records in grouped.items()}

    def count_nodes(self) -> int:
        """返回节点总数."""

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM solver_nodes")
        row = cursor.fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def count_actions(self) -> int:
        """返回动作总数."""

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM solver_actions")
        row = cursor.fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def list_stack_bbs(self, *, source_id: int) -> list[int]:
        """列出策略源下可用的筹码深度.

        Args:
            source_id: 所属策略源主键。

        Returns:
            排序后的筹码深度列表。
        """

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT stack_bb
            FROM solver_nodes
            WHERE source_id = ?
            ORDER BY stack_bb ASC
            """,
            (source_id,),
        )
        return [int(row["stack_bb"]) for row in cursor.fetchall()]

    def resolve_stack_bb(
        self,
        *,
        source_id: int,
        requested_stack_bb: int,
    ) -> int:
        """解析最接近的可用筹码深度.

        Args:
            source_id: 所属策略源主键。
            requested_stack_bb: 当前请求中的有效筹码深度。

        Returns:
            仓库内最接近的可用 `stack_bb`。

        Raises:
            ValueError: 当策略源下没有任何可用 stack 时抛出。
        """

        available_stacks = self.list_stack_bbs(source_id=source_id)
        if not available_stacks:
            raise ValueError("当前策略源没有可用的 stack 配置。")
        if requested_stack_bb in available_stacks:
            return requested_stack_bb

        return min(
            available_stacks,
            key=lambda stack_bb: (
                abs(stack_bb - requested_stack_bb),
                stack_bb,
            ),
        )


def _encode_position(position: Position | None) -> str | None:
    """将位置编码为 sqlite 文本."""

    if position is None:
        return None
    return position.value


def _encode_bool(value: bool | None) -> int | None:
    """将布尔值编码为 sqlite 整数."""

    if value is None:
        return None
    return int(value)


def _decode_position(value: str | None) -> Position | None:
    """将 sqlite 文本解码为位置枚举."""

    if value is None:
        return None
    return Position(value)


def _decode_bool(value: int | None) -> bool | None:
    """将 sqlite 整数解码为布尔值."""

    if value is None:
        return None
    return bool(value)


def _row_to_solver_node_record(row: sqlite3.Row) -> SolverNodeRecord:
    """将 sqlite 行转换为节点记录.

    Args:
        row: sqlite 返回行。

    Returns:
        结构化节点记录。
    """

    return SolverNodeRecord(
        node_id=int(row["node_id"]),
        source_id=int(row["source_id"]),
        stack_bb=int(row["stack_bb"]),
        history_full=str(row["history_full"]),
        history_actions=str(row["history_actions"]),
        history_token_count=int(row["history_token_count"]),
        acting_position=str(row["acting_position"]),
        source_file=str(row["source_file"]),
        actor_position=_decode_position(row["actor_position"]),
        aggressor_position=_decode_position(row["aggressor_position"]),
        call_count=int(row["call_count"]),
        limp_count=int(row["limp_count"]),
        raise_time=int(row["raise_time"]),
        pot_size=float(row["pot_size"]),
        raise_size_bb=float(row["raise_size_bb"])
        if row["raise_size_bb"] is not None
        else None,
        is_in_position=_decode_bool(row["is_in_position"]),
    )


def _row_to_solver_action_record(row: sqlite3.Row) -> SolverActionRecord:
    """将 sqlite 行转换为动作记录.

    Args:
        row: sqlite 返回行。

    Returns:
        结构化动作记录。
    """

    return SolverActionRecord(
        node_id=int(row["node_id"]),
        order_index=int(row["order_index"]),
        action_code=str(row["action_code"]),
        action_type=str(row["action_type"]),
        bet_size_bb=float(row["bet_size_bb"])
        if row["bet_size_bb"] is not None
        else None,
        is_all_in=bool(row["is_all_in"]),
        total_frequency=float(row["total_frequency"]),
        next_position=str(row["next_position"]),
        preflop_range=decode_preflop_range(
            bytes(row["strategy_blob"]),
            bytes(row["ev_blob"]),
        ),
        total_ev=float(row["total_ev"]),
        total_combos=float(row["total_combos"]),
    )


__all__ = [
    "PreflopStrategyRepository",
    "SolverActionRecord",
    "SolverNodeRecord",
    "StrategySourceRecord",
]
