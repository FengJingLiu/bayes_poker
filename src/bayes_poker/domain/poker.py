"""扑克领域基础类型。"""

from __future__ import annotations

from enum import Enum


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
