"""策略处理器基础类型和工具函数。

提供策略处理器的类型定义和通用响应生成函数。
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable


StrategyHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
"""策略处理器类型：接收 session_id 和 payload，返回策略响应。"""


def _base_response(state_version: int, notes: str) -> dict[str, Any]:
    """生成最小可用的策略响应结构。

    Args:
        state_version: 状态版本号。
        notes: 响应备注信息。

    Returns:
        策略响应字典。
    """
    return {
        "state_version": state_version,
        "recommended_action": "",
        "recommended_amount": 0.0,
        "confidence": 0.0,
        "ev": 0.0,
        "action_evs": {},
        "range_breakdown": {},
        "notes": notes,
        "is_stale": False,
    }
