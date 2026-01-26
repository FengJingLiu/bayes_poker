"""业务消息类型定义。

定义各种消息的 payload 结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """玩家动作类型。"""

    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


class Street(str, Enum):
    """游戏阶段。"""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


@dataclass
class PlayerState:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlayerState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class HelloPayload:
    """客户端 Hello 消息。"""

    client_version: str = "1.0.0"
    parser_version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuthPayload:
    """认证消息。"""

    api_key: str = ""
    token: str = ""
    timestamp: int = 0
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuthResponsePayload:
    """认证响应。"""

    success: bool = False
    client_id: str = ""
    expires_at: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubscribePayload:
    """订阅牌桌。"""

    session_id: str
    table_type: str = "6max"
    small_blind: float = 0.5
    big_blind: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResumePayload:
    """断线重连恢复。"""

    session_id: str
    last_ack_seq: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TableSnapshotPayload:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableSnapshotPayload:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TableStateUpdatePayload:
    """牌桌增量更新。"""

    session_id: str
    changes: dict[str, Any] = field(default_factory=dict)
    state_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionEventPayload:
    """玩家动作事件。"""

    session_id: str
    seat_index: int
    action: str
    amount: float = 0.0
    state_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyRequestPayload:
    """策略请求。"""

    session_id: str
    state_version: int
    street: str = "preflop"
    pot: float = 0.0
    board: list[str] = field(default_factory=list)
    hero_cards: list[str] = field(default_factory=list)
    hero_seat: int = 0
    hero_stack: float = 0.0
    hero_position: str = ""
    effective_stack: float = 0.0
    btn_seat: int = 0
    players: list[dict[str, Any]] = field(default_factory=list)
    history: str = ""
    action_sequence: list[dict[str, Any]] = field(default_factory=list)
    opponent_ranges: dict[int, Any] = field(default_factory=dict)
    bet_sizes: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyRequestPayload:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StrategyResponsePayload:
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AckPayload:
    """消息确认。"""

    last_seq: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorPayload:
    """错误消息。"""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ServerNoticePayload:
    """服务器通知。"""

    notice_type: str
    message: str
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
