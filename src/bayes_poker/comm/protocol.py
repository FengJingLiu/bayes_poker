"""通信协议定义。

定义 Windows ↔ Linux 通信的消息格式和类型。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


PROTOCOL_VERSION = 1


class MessageType(str, Enum):
    """消息类型。"""

    HELLO = "hello"
    AUTH = "auth"
    AUTH_RESPONSE = "auth_response"

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    RESUME = "resume"

    TABLE_SNAPSHOT = "table_snapshot"
    TABLE_STATE_UPDATE = "table_state_update"
    ACTION_EVENT = "action_event"

    STRATEGY_REQUEST = "strategy_request"
    STRATEGY_RESPONSE = "strategy_response"
    CANCEL_REQUEST = "cancel_request"

    ACK = "ack"
    PING = "ping"
    PONG = "pong"

    ERROR = "error"
    SERVER_NOTICE = "server_notice"


class ErrorCode(str, Enum):
    """错误码。"""

    AUTH_FAILED = "auth_failed"
    AUTH_EXPIRED = "auth_expired"
    SESSION_NOT_FOUND = "session_not_found"
    OUT_OF_SYNC = "out_of_sync"
    SCHEMA_INVALID = "schema_invalid"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    NOT_AUTHORIZED = "not_authorized"


@dataclass
class MessageEnvelope:
    """消息信封。

    所有消息的统一外层结构。
    """

    type: MessageType
    payload: dict[str, Any]
    session_id: str | None = None
    client_id: str | None = None
    seq: int | None = None
    request_id: str | None = None
    v: int = field(default=PROTOCOL_VERSION)
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        result = {
            "v": self.v,
            "type": self.type.value
            if isinstance(self.type, MessageType)
            else self.type,
            "ts_ms": self.ts_ms,
            "payload": self.payload,
        }
        if self.session_id is not None:
            result["session_id"] = self.session_id
        if self.client_id is not None:
            result["client_id"] = self.client_id
        if self.seq is not None:
            result["seq"] = self.seq
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MessageEnvelope:
        """从字典创建。"""
        msg_type = data.get("type", "")
        try:
            msg_type = MessageType(msg_type)
        except ValueError:
            pass

        return cls(
            v=data.get("v", PROTOCOL_VERSION),
            type=msg_type,
            session_id=data.get("session_id"),
            client_id=data.get("client_id"),
            seq=data.get("seq"),
            ts_ms=data.get("ts_ms", int(time.time() * 1000)),
            request_id=data.get("request_id"),
            payload=data.get("payload", {}),
        )


def generate_request_id() -> str:
    """生成请求 ID。"""
    return str(uuid.uuid4())


def generate_client_id() -> str:
    """生成客户端 ID。"""
    return f"client-{uuid.uuid4().hex[:12]}"


def generate_session_id() -> str:
    """生成会话 ID（牌桌）。"""
    return f"table-{uuid.uuid4().hex[:12]}"
