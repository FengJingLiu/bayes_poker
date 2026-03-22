"""动作族枚举（独立模块避免循环导入）。"""

from enum import Enum


class ActionFamily(str, Enum):
    """动作族枚举。"""

    FOLD = "fold"
    LIMP = "limp"
    OVERLIMP = "overlimp"
    OPEN = "open"
    ISO_RAISE = "iso_raise"
    CALL_VS_OPEN = "call_vs_open"
    CALL_VS_3BET = "call_vs_3bet"
    THREE_BET = "three_bet"
    SQUEEZE = "squeeze"
    FOUR_BET = "four_bet"
    JAM = "jam"
