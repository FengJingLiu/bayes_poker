"""会话管理模块。

管理客户端会话、消息重放缓存和状态存储。
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from bayes_poker.comm.protocol import MessageEnvelope

if TYPE_CHECKING:
    from bayes_poker.strategy.opponent_range.predictor import OpponentRangePredictor

LOGGER = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """会话配置。"""

    replay_buffer_size: int = 500
    replay_buffer_ttl: float = 60.0
    session_timeout: float = 300.0


@dataclass
class TableSession:
    """牌桌会话。

    存储单个牌桌的状态和消息缓存。

    Attributes:
        session_id: 会话 ID。
        client_id: 客户端 ID。
        table_type: 牌桌类型。
        small_blind: 小盲注。
        big_blind: 大盲注。
        replay_buffer_size: 重放缓存大小。
        state_version: 状态版本。
        last_snapshot: 最近快照。
        last_activity: 最后活动时间。
        range_predictor: 对手范围预测器（按牌桌隔离）。
        current_hand_id: 当前手牌 ID（用于检测新手牌）。
    """

    session_id: str
    client_id: str
    table_type: str = "6max"
    small_blind: float = 0.5
    big_blind: float = 1.0
    replay_buffer_size: int = 500

    state_version: int = 0
    last_snapshot: dict[str, Any] | None = None
    last_activity: float = field(default_factory=time.time)

    # 对手范围预测器（按牌桌隔离）
    range_predictor: "OpponentRangePredictor | None" = None
    current_hand_id: str = ""

    _replay_buffer: deque[tuple[int, float, MessageEnvelope]] = field(
        init=False, repr=False
    )
    _client_last_ack: int = 0

    def __post_init__(self) -> None:
        """初始化重放缓存。"""
        self._replay_buffer = deque(maxlen=self.replay_buffer_size)

    def update_activity(self) -> None:
        """更新最后活动时间。"""
        self.last_activity = time.time()

    def add_to_replay_buffer(self, seq: int, msg: MessageEnvelope) -> None:
        """添加消息到重放缓存。"""
        self._replay_buffer.append((seq, time.time(), msg))

    def get_messages_since(
        self, last_ack_seq: int, ttl: float = 60.0
    ) -> list[MessageEnvelope]:
        """获取指定 seq 之后的消息。"""
        now = time.time()
        result = []

        for seq, ts, msg in self._replay_buffer:
            if seq > last_ack_seq and (now - ts) < ttl:
                result.append(msg)

        return result

    def is_seq_in_buffer(self, seq: int) -> bool:
        """检查 seq 是否在缓存范围内。"""
        if not self._replay_buffer:
            return False

        oldest_seq = self._replay_buffer[0][0]
        newest_seq = self._replay_buffer[-1][0]

        return oldest_seq <= seq <= newest_seq

    def update_client_ack(self, ack_seq: int) -> None:
        """更新客户端确认的序号。"""
        self._client_last_ack = max(self._client_last_ack, ack_seq)

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        """设置最新快照。"""
        self.last_snapshot = snapshot
        self.state_version += 1
        self.update_activity()


@dataclass
class ClientSession:
    """客户端会话。

    管理单个客户端的连接状态。
    """

    client_id: str
    websocket: Any = None
    authenticated: bool = False
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    subscribed_sessions: set[str] = field(default_factory=set)

    _send_seq: int = 0
    _recv_seq: int = 0
    _last_ack_seq: int = 0

    def next_seq(self) -> int:
        """获取下一个发送序号。"""
        self._send_seq += 1
        return self._send_seq

    def update_recv_seq(self, seq: int) -> None:
        """更新接收序号。"""
        self._recv_seq = max(self._recv_seq, seq)

    def update_ack(self, ack_seq: int) -> None:
        """更新确认序号。"""
        self._last_ack_seq = max(self._last_ack_seq, ack_seq)


class SessionManager:
    """会话管理器。

    管理所有客户端会话和牌桌会话。
    """

    def __init__(self, config: SessionConfig | None = None) -> None:
        self._config = config or SessionConfig()
        self._client_sessions: dict[str, ClientSession] = {}
        self._table_sessions: dict[str, TableSession] = {}

    @property
    def client_count(self) -> int:
        """当前客户端数量。"""
        return len(self._client_sessions)

    @property
    def table_count(self) -> int:
        """当前牌桌会话数量。"""
        return len(self._table_sessions)

    def create_client_session(
        self, client_id: str, websocket: Any = None
    ) -> ClientSession:
        """创建客户端会话。"""
        if client_id in self._client_sessions:
            existing = self._client_sessions[client_id]
            existing.websocket = websocket
            existing.last_activity = time.time()
            return existing

        session = ClientSession(client_id=client_id, websocket=websocket)
        self._client_sessions[client_id] = session
        LOGGER.info("创建客户端会话: %s", client_id)
        return session

    def get_client_session(self, client_id: str) -> ClientSession | None:
        """获取客户端会话。"""
        return self._client_sessions.get(client_id)

    def remove_client_session(self, client_id: str) -> ClientSession | None:
        """移除客户端会话。"""
        session = self._client_sessions.pop(client_id, None)
        if session:
            LOGGER.info("移除客户端会话: %s", client_id)
        return session

    def create_table_session(
        self,
        session_id: str,
        client_id: str,
        table_type: str = "6max",
        blinds: tuple[float, float] = (0.5, 1.0),
    ) -> TableSession:
        """创建牌桌会话。"""
        if session_id in self._table_sessions:
            return self._table_sessions[session_id]

        session = TableSession(
            session_id=session_id,
            client_id=client_id,
            table_type=table_type,
            small_blind=blinds[0],
            big_blind=blinds[1],
            replay_buffer_size=self._config.replay_buffer_size,
        )
        self._table_sessions[session_id] = session
        LOGGER.info("创建牌桌会话: %s", session_id)
        return session

    def get_table_session(self, session_id: str) -> TableSession | None:
        """获取牌桌会话。"""
        return self._table_sessions.get(session_id)

    def remove_table_session(self, session_id: str) -> TableSession | None:
        """移除牌桌会话。"""
        session = self._table_sessions.pop(session_id, None)
        if session:
            LOGGER.info("移除牌桌会话: %s", session_id)
        return session

    def subscribe_client_to_table(self, client_id: str, session_id: str) -> bool:
        """订阅客户端到牌桌。"""
        client = self.get_client_session(client_id)
        table = self.get_table_session(session_id)

        if not client or not table:
            return False

        client.subscribed_sessions.add(session_id)
        return True

    def unsubscribe_client_from_table(self, client_id: str, session_id: str) -> bool:
        """取消订阅。"""
        client = self.get_client_session(client_id)
        if not client:
            return False

        client.subscribed_sessions.discard(session_id)
        return True

    def cleanup_expired(self) -> tuple[int, int]:
        """清理过期会话。

        Returns:
            (清理的客户端数, 清理的牌桌数)
        """
        now = time.time()
        timeout = self._config.session_timeout

        expired_clients = [
            cid
            for cid, session in self._client_sessions.items()
            if (now - session.last_activity) > timeout
        ]

        expired_tables = [
            sid
            for sid, session in self._table_sessions.items()
            if (now - session.last_activity) > timeout
        ]

        for cid in expired_clients:
            self.remove_client_session(cid)

        for sid in expired_tables:
            self.remove_table_session(sid)

        return len(expired_clients), len(expired_tables)

    def handle_resume(
        self, client_id: str, session_id: str, last_ack_seq: int
    ) -> tuple[bool, list[MessageEnvelope]]:
        """处理断线恢复。

        Returns:
            (是否成功, 需要重放的消息列表)
        """
        table = self.get_table_session(session_id)
        if not table:
            return False, []

        if last_ack_seq == 0 or table.is_seq_in_buffer(last_ack_seq):
            messages = table.get_messages_since(
                last_ack_seq, ttl=self._config.replay_buffer_ttl
            )
            LOGGER.info(
                "恢复会话: client=%s, session=%s, 重放 %d 条消息",
                client_id,
                session_id,
                len(messages),
            )
            return True, messages
        else:
            LOGGER.warning(
                "会话不同步: client=%s, session=%s, 需要全量快照",
                client_id,
                session_id,
            )
            return False, []
