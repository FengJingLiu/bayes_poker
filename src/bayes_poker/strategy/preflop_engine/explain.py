"""Hero 决策解释输出工具."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    """Hero 决策解释.

    Attributes:
        summary: 面向调用方的简短摘要.
        reasons: 组成摘要的原因列表.
    """

    summary: str
    reasons: tuple[str, ...] = ()


def build_summary(*, recommended_action: str, reasons: Sequence[str]) -> str:
    """构建 Hero 决策摘要.

    Args:
        recommended_action: 推荐动作名称.
        reasons: 解释原因列表.

    Returns:
        面向调用方的单行摘要.
    """

    if not reasons:
        return f"推荐 {recommended_action}, 当前保持基础策略."

    return f"推荐 {recommended_action}, {'; '.join(reasons)}."


__all__ = [
    "DecisionExplanation",
    "build_summary",
]
