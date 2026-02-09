"""翻前行动前缀工具。

提供翻前分层推断、limper 计数与场景分类能力, 供 runtime 与范围预测模块复用.
"""

from __future__ import annotations

from enum import Enum


class PreflopLayer(str, Enum):
    """翻前分层枚举。"""

    RFI = "rfi"
    THREE_BET = "3bet"
    FOUR_BET = "4bet"
    UNKNOWN = "unknown"


class PreflopScenario(str, Enum):
    """翻前场景枚举。"""

    RFI_NO_LIMPER = "rfi_no_limper"
    RFI_FACE_LIMPER = "rfi_face_limper"
    THREE_BET = "three_bet"
    FOUR_BET = "four_bet"
    UNKNOWN = "unknown"


def split_history_tokens(history: str) -> list[str]:
    """分割并标准化翻前前缀 token。

    Args:
        history: 翻前行动前缀字符串。

    Returns:
        标准化后的 token 列表。
    """
    return [token.strip().upper() for token in history.split("-") if token.strip()]


def infer_preflop_layer(history: str) -> PreflopLayer:
    """从行动前缀推断翻前分层。

    Args:
        history: 翻前行动前缀字符串。

    Returns:
        翻前分层。
    """
    if not history:
        return PreflopLayer.RFI

    tokens = split_history_tokens(history)
    raise_count = sum(1 for token in tokens if token == "RAI" or token.startswith("R"))

    if raise_count <= 0:
        return PreflopLayer.RFI
    if raise_count == 1:
        return PreflopLayer.THREE_BET
    if raise_count == 2:
        return PreflopLayer.FOUR_BET
    return PreflopLayer.UNKNOWN


def count_limpers_in_history(history: str) -> int:
    """计算历史中的 limper 数量。

    Args:
        history: 翻前行动前缀字符串。

    Returns:
        limper 数量。
    """
    if not history:
        return 0

    tokens = split_history_tokens(history)
    if any(token.startswith("R") for token in tokens):
        return 0
    return sum(1 for token in tokens if token == "C")


def is_open_no_limper(history: str) -> bool:
    """判断是否为无 limper 的 open 场景。

    Args:
        history: 翻前行动前缀字符串。

    Returns:
        是否为无 limper open。
    """
    if not history:
        return True

    tokens = split_history_tokens(history)
    return not any(token == "C" or token.startswith("R") for token in tokens)


def classify_preflop_scenario(history: str) -> PreflopScenario:
    """根据翻前前缀分类场景。

    Args:
        history: 翻前行动前缀字符串。

    Returns:
        翻前场景枚举值。
    """
    layer = infer_preflop_layer(history)
    if layer == PreflopLayer.RFI:
        if count_limpers_in_history(history) > 0:
            return PreflopScenario.RFI_FACE_LIMPER
        return PreflopScenario.RFI_NO_LIMPER
    if layer == PreflopLayer.THREE_BET:
        return PreflopScenario.THREE_BET
    if layer == PreflopLayer.FOUR_BET:
        return PreflopScenario.FOUR_BET
    return PreflopScenario.UNKNOWN
