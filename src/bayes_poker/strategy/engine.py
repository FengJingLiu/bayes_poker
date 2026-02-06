"""策略引擎与分发器。

该模块为 WebSocket 服务器的 `StrategyHandler` 提供可注册的分发框架：
- 将策略拆分为 `preflop` 与 `postflop` 两条执行链路
- 基于 `ObservedTableState.street` 做路由

当前仅搭建框架，具体策略逻辑后续补充。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from bayes_poker.domain.poker import Street

LOGGER = logging.getLogger(__name__)


StrategyHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


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
        """注册翻前策略处理器。

        Args:
            handler: 翻前策略处理器。
        """
        self.preflop_strategy = handler

    def register_postflop(self, handler: StrategyHandler) -> None:
        """注册翻后策略处理器。

        Args:
            handler: 翻后策略处理器。
        """
        self.postflop_strategy = handler

    def as_handler(self) -> StrategyHandler:
        """导出为 server 需要的 `StrategyHandler`。

        Returns:
            可用于 WebSocket 服务器的策略处理器。
        """

        async def _handler(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            return await self.handle(session_id, payload)

        return _handler

    async def handle(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """处理策略请求并返回响应 payload。

        从 payload 中提取 table_state，反序列化为 ObservedTableState，
        然后根据当前街道分发到对应的策略处理器。

        Args:
            session_id: 会话 ID。
            payload: 请求 payload。

        Returns:
            策略响应 payload。
        """
        from bayes_poker.table.observed_state import ObservedTableState

        state_version = int(payload.get("state_version", 0) or 0)
        table_state_dict = payload.get("table_state")

        if not table_state_dict:
            return _base_response(state_version, "缺少 table_state 字段")

        # 从字典恢复 ObservedTableState
        try:
            observed_state = ObservedTableState.from_dict(table_state_dict)
        except Exception as e:
            LOGGER.warning("ObservedTableState 反序列化失败: %s", e)
            return _base_response(
                state_version,
                f"table_state 反序列化失败: {e}",
            )

        street = observed_state.street

        # 将 ObservedTableState 对象和提取的信息添加到 payload
        enriched_payload = {
            **payload,
            "observed_state": observed_state,
            "street": street.value,
            "pot": observed_state.pot,
            "board": observed_state.board_cards,
            "hero_cards": list(observed_state.hero_cards)
            if observed_state.hero_cards
            else [],
            "hero_position": observed_state.get_hero_position(),
            "hero_stack_bb": observed_state.get_hero_stack_bb(),
            "action_history": observed_state.get_action_history_string(),
        }

        LOGGER.debug(
            "状态解析成功: street=%s, pot=%s, hero_position=%s",
            street.value,
            observed_state.pot,
            observed_state.get_hero_position(),
        )

        if street == Street.PREFLOP:
            if not self.preflop_strategy:
                return _base_response(state_version, "preflopStrategy 未注册")
            return await self.preflop_strategy(session_id, enriched_payload)

        if not self.postflop_strategy:
            return _base_response(
                state_version,
                f"postflopStrategy 未注册 (street={street.value})",
            )
        return await self.postflop_strategy(session_id, enriched_payload)
