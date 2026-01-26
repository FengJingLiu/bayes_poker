"""翻后（postflop）策略执行骨架。

仅提供可注册处理器，具体 flop/turn/river 逻辑后续补充。
"""

from __future__ import annotations

from typing import Any

from bayes_poker.strategy.engine import StrategyHandler, _base_response


def create_postflop_strategy() -> StrategyHandler:
    """创建可注册到 server 的 postflopStrategy 处理器。"""

    async def _handler(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _ = session_id
        state_version = int(payload.get("state_version", 0) or 0)
        street = str(payload.get("street", "")).lower()
        return _base_response(state_version, f"postflopStrategy 未实现 (street={street})")

    return _handler

