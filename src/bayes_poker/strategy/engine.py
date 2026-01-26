"""策略引擎与分发器。

该模块为 WebSocket 服务器的 `StrategyHandler` 提供可注册的分发框架：
- 将策略拆分为 `preflop` 与 `postflop` 两条执行链路
- 基于 `StrategyRequestPayload.street` 做路由

当前仅搭建框架，具体策略逻辑后续补充。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

LOGGER = logging.getLogger(__name__)


StrategyHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def _base_response(state_version: int, notes: str) -> dict[str, Any]:
    """生成最小可用的策略响应结构。"""
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


@dataclass(slots=True)
class StrategyDispatcher:
    """策略分发器。

    用于在 server 层注册单一 `StrategyHandler`，但内部按街道分流到不同策略实现：
        - preflopStrategy: `street == "preflop"`
        - postflopStrategy: 其它街道（flop/turn/river/postflop 等）

    用法示例：
        dispatcher = StrategyDispatcher()
        dispatcher.register_preflop(preflop_strategy)
        dispatcher.register_postflop(postflop_strategy)
        server.set_strategy_handler(dispatcher.as_handler())

    最小接入示例：

    from bayes_poker.comm.server import create_server
    from bayes_poker.strategy import (
        StrategyDispatcher,
        create_postflop_strategy,
        create_preflop_strategy_from_directory,
    )

    dispatcher = StrategyDispatcher()
    dispatcher.register_preflop(
        create_preflop_strategy_from_directory(
            strategy_dir="path/to/preflop/strategy-dir",
        )
    )
    dispatcher.register_postflop(create_postflop_strategy())

    server = create_server(strategy_handler=dispatcher.as_handler())
    """

    preflop_strategy: StrategyHandler | None = None
    postflop_strategy: StrategyHandler | None = None

    def register_preflop(self, handler: StrategyHandler) -> None:
        """注册翻前策略处理器。"""
        self.preflop_strategy = handler

    def register_postflop(self, handler: StrategyHandler) -> None:
        """注册翻后策略处理器。"""
        self.postflop_strategy = handler

    def as_handler(self) -> StrategyHandler:
        """导出为 server 需要的 `StrategyHandler`。"""

        async def _handler(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            return await self.handle(session_id, payload)

        return _handler

    async def handle(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """处理策略请求并返回响应 payload。

        从 payload 中提取 phh_data，反序列化为 pokerkit State，
        然后根据当前街道分发到对应的策略处理器。
        """
        from bayes_poker.comm.phh_serializer import phh_to_state, extract_state_info

        state_version = int(payload.get("state_version", 0) or 0)
        phh_data = payload.get("phh_data", "")

        if not phh_data:
            return _base_response(state_version, "缺少 phh_data 字段")

        # 从 PHH 恢复 pokerkit State
        result = phh_to_state(phh_data)
        if not result.success or result.state is None:
            return _base_response(
                state_version,
                f"PHH 反序列化失败: {result.error}",
            )

        # 提取状态信息用于路由
        state_info = extract_state_info(result.state)
        street = state_info["street"]

        # 将 State 对象和提取的信息添加到 payload
        enriched_payload = {
            **payload,
            "pokerkit_game": result.game,
            "pokerkit_state": result.state,
            "hand_history": result.hand_history,
            "street": street,
            "pot": state_info["pot"],
            "board": state_info["board"],
            "stacks": state_info["stacks"],
            "actor_index": state_info["actor_index"],
        }

        LOGGER.debug(
            "PHH 解析成功，street=%s, pot=%s, actor=%s",
            street,
            state_info["pot"],
            state_info["actor_index"],
        )

        if street == "preflop":
            if not self.preflop_strategy:
                return _base_response(state_version, "preflopStrategy 未注册")
            return await self.preflop_strategy(session_id, enriched_payload)

        if not self.postflop_strategy:
            return _base_response(
                state_version,
                f"postflopStrategy 未注册 (street={street})",
            )
        return await self.postflop_strategy(session_id, enriched_payload)
