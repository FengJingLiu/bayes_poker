"""玩家指标模块的枚举类型定义。

移植自 G5.Logic/Enums.cs，仅保留玩家指标构建所需的枚举。
"""

from __future__ import annotations

from enum import IntEnum, auto


class TableType(IntEnum):
    """桌型枚举。

    值等于该桌型的最大玩家数。
    """

    HEADS_UP = 2
    SIX_MAX = 6


class Street(IntEnum):
    """游戏阶段（街）。"""

    UNKNOWN = 0
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()


class Position(IntEnum):
    """玩家位置。

    索引顺序与 G5.Logic 保持一致：SB=0, BB=1, ...
    """

    SMALL_BLIND = 0
    BIG_BLIND = 1
    UTG = 2
    HJ = 3  # Hijack (MP in 6-max)
    CO = 4  # Cutoff
    BUTTON = 5
    EMPTY = 6


class ActionType(IntEnum):
    """玩家动作类型。"""

    FOLD = 0
    CHECK = auto()
    CALL = auto()
    BET = auto()
    RAISE = auto()
    ALL_IN = auto()
    WINS = auto()
    MONEY_RETURNED = auto()
    NO_ACTION = auto()

    @property
    def is_raise_action(self) -> bool:
        """是否为加注类动作（Bet/Raise/AllIn）。"""
        return self in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)

    @property
    def is_valid_action(self) -> bool:
        """是否为有效的博弈动作（排除 Wins/MoneyReturned/NoAction）。"""
        return self in (
            ActionType.FOLD,
            ActionType.CHECK,
            ActionType.CALL,
            ActionType.BET,
            ActionType.RAISE,
            ActionType.ALL_IN,
        )
