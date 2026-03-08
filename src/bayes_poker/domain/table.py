"""牌桌业务公共类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bayes_poker.domain.poker import ActionType, Street


class Position(Enum):
    """玩家业务位置。"""

    SB = "SB"
    BB = "BB"
    UTG = "UTG"
    UTG1 = "UTG+1"
    MP = "MP"
    MP1 = "MP+1"
    HJ = "HJ"
    CO = "CO"
    BTN = "BTN"


SEAT_ORDER_6MAX: list[Position] = [
    Position.BTN,
    Position.SB,
    Position.BB,
    Position.UTG,
    Position.MP,
    Position.CO,
]

SEAT_ORDER_9MAX: list[Position] = [
    Position.BTN,
    Position.SB,
    Position.BB,
    Position.UTG,
    Position.UTG1,
    Position.MP,
    Position.MP1,
    Position.HJ,
    Position.CO,
]


def get_position_by_seat(
    seat_index: int,
    btn_seat: int,
    player_count: int,
) -> Position:
    """根据屏幕座位索引和庄家位置，计算玩家逻辑位置。

    Args:
        seat_index: 屏幕座位索引。
        btn_seat: 庄家在屏幕上的座位索引。
        player_count: 玩家总数, 目前支持 6 或 9 人桌。

    Returns:
        对应的业务位置枚举。
    """

    seat_order = SEAT_ORDER_6MAX if player_count == 6 else SEAT_ORDER_9MAX
    offset = (seat_index - btn_seat) % player_count
    return seat_order[offset]


@dataclass
class PlayerAction:
    """玩家动作记录。"""

    player_index: int
    action_type: ActionType
    amount: float = 0.0
    street: Street = Street.PREFLOP

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。

        Returns:
            包含动作信息的字典。
        """

        return {
            "player_index": self.player_index,
            "action_type": self.action_type.value,
            "amount": self.amount,
            "street": self.street.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerAction":
        """从字典反序列化。

        Args:
            data: 动作字典。

        Returns:
            玩家动作实例。
        """

        return cls(
            player_index=data["player_index"],
            action_type=ActionType(data["action_type"]),
            amount=data.get("amount", 0.0),
            street=Street(data.get("street", "preflop")),
        )


@dataclass
class Player:
    """玩家业务状态。"""

    seat_index: int
    player_id: str = ""
    stack: float = 0.0
    bet: float = 0.0
    position: Position | None = None
    is_folded: bool = False
    is_thinking: bool = False
    is_button: bool = False
    vpip: int = 0
    action_history: list[PlayerAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。

        Returns:
            包含玩家状态信息的字典。
        """

        return {
            "seat_index": self.seat_index,
            "player_id": self.player_id,
            "stack": self.stack,
            "bet": self.bet,
            "position": self.position.value if self.position is not None else None,
            "is_folded": self.is_folded,
            "is_thinking": self.is_thinking,
            "is_button": self.is_button,
            "vpip": self.vpip,
            "action_history": [action.to_dict() for action in self.action_history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        """从字典反序列化。

        Args:
            data: 玩家状态字典。

        Returns:
            玩家实例。
        """

        action_history = [
            PlayerAction.from_dict(action)
            for action in data.get("action_history", [])
        ]
        position = _coerce_position(data.get("position"))
        return cls(
            seat_index=data.get("seat_index", 0),
            player_id=data.get("player_id", ""),
            stack=data.get("stack", 0.0),
            bet=data.get("bet", 0.0),
            position=position,
            is_folded=data.get("is_folded", False),
            is_thinking=data.get("is_thinking", False),
            is_button=data.get("is_button", False),
            vpip=data.get("vpip", 0),
            action_history=action_history,
        )

    def get_stack_bb(self, big_blind: float) -> float:
        """获取筹码量（BB 单位）。

        Args:
            big_blind: 大盲注金额。

        Returns:
            筹码量（以大盲注为单位）。
        """

        if big_blind <= 0:
            return self.stack
        return self.stack / big_blind

    def record_action(self, action: PlayerAction) -> None:
        """记录该玩家的动作。

        Args:
            action: 玩家动作。
        """

        self.action_history.append(action)


def _coerce_position(value: object) -> Position | None:
    """将输入值归一化为业务位置。

    Args:
        value: 任意位置输入。

    Returns:
        归一化后的位置, 无法识别时返回 `None`。
    """

    if isinstance(value, Position):
        return value
    if isinstance(value, str):
        try:
            return Position(value)
        except ValueError:
            return None
    return None


__all__ = [
    "Player",
    "PlayerAction",
    "Position",
    "SEAT_ORDER_6MAX",
    "SEAT_ORDER_9MAX",
    "get_position_by_seat",
]
