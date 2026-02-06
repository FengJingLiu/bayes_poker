"""业务消息类型定义。

定义各种消息的 payload 结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bayes_poker.comm.payload_base import PayloadBase
from bayes_poker.domain.poker import ActionType, Street


@dataclass
class PlayerState(PayloadBase):
    """玩家状态。"""

    seat_index: int
    player_id: str = ""
    stack: float = 0.0
    bet: float = 0.0
    is_folded: bool = False
    is_all_in: bool = False
    is_button: bool = False
    is_hero: bool = False
    position: str = ""


@dataclass
class HelloPayload(PayloadBase):
    """客户端 Hello 消息。"""

    client_version: str = "1.0.0"
    parser_version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)


@dataclass
class AuthPayload(PayloadBase):
    """认证消息。"""

    api_key: str = ""
    token: str = ""
    timestamp: int = 0
    signature: str = ""


@dataclass
class AuthResponsePayload(PayloadBase):
    """认证响应。"""

    success: bool = False
    client_id: str = ""
    expires_at: int = 0
    message: str = ""


@dataclass
class SubscribePayload(PayloadBase):
    """订阅牌桌。"""

    session_id: str
    table_type: str = "6max"
    small_blind: float = 0.5
    big_blind: float = 1.0


@dataclass
class ResumePayload(PayloadBase):
    """断线重连恢复。"""

    session_id: str
    last_ack_seq: int


@dataclass
class TableSnapshotPayload(PayloadBase):
    """牌桌全量快照。"""

    session_id: str
    hand_id: str = ""
    street: str = "preflop"
    pot: float = 0.0
    board: list[str] = field(default_factory=list)
    hero_cards: list[str] = field(default_factory=list)
    players: list[dict[str, Any]] = field(default_factory=list)
    btn_seat: int = 0
    actor_seat: int | None = None
    state_version: int = 0


@dataclass
class TableStateUpdatePayload(PayloadBase):
    """牌桌增量更新。"""

    session_id: str
    changes: dict[str, Any] = field(default_factory=dict)
    state_version: int = 0


@dataclass
class ActionEventPayload(PayloadBase):
    """玩家动作事件。"""

    session_id: str
    seat_index: int
    action: str
    amount: float = 0.0
    state_version: int = 0


@dataclass
class StrategyRequestPayload(PayloadBase):
    """策略请求（基于 ObservedTableState）。

    使用 ObservedTableState 的序列化格式传输游戏状态。

    Attributes:
        session_id: 会话 ID
        table_state: ObservedTableState.to_dict() 序列化结果
        hero_seat: Hero 座位索引
        hero_cards: Hero 手牌（如 ["Ah", "Kd"]）
        state_version: 状态版本号
    """

    session_id: str
    table_state: dict[str, Any] = field(default_factory=dict)
    hero_seat: int = 0
    hero_cards: list[str] = field(default_factory=list)
    state_version: int = 0


@dataclass
class StrategyResponsePayload(PayloadBase):
    """策略响应。"""

    session_id: str
    state_version: int
    request_id: str = ""

    recommended_action: str = ""
    recommended_amount: float = 0.0
    confidence: float = 0.0
    ev: float = 0.0

    action_evs: dict[str, float] = field(default_factory=dict)
    range_breakdown: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    is_stale: bool = False
    compute_time_ms: int = 0


@dataclass
class AckPayload(PayloadBase):
    """消息确认。"""

    last_seq: int


@dataclass
class ErrorPayload(PayloadBase):
    """错误消息。"""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerNoticePayload(PayloadBase):
    """服务器通知。"""

    notice_type: str
    message: str
    severity: str = "info"
