"""测试 StrategyDispatcher（使用 ObservedTableState 格式）。"""

import asyncio
from typing import Any

from bayes_poker.strategy.engine import StrategyDispatcher


def _create_test_table_state(street: str = "preflop") -> dict[str, Any]:
    """创建用于测试的 table_state 字典。"""
    return {
        "table_id": "test",
        "player_count": 6,
        "small_blind": 0.5,
        "big_blind": 1.0,
        "hand_id": "test-001",
        "street": street,
        "pot": 1.5,
        "btn_seat": 2,
        "actor_seat": 0,
        "hero_seat": 0,
        "hero_cards": ["Ah", "Kd"],
        "board_cards": [] if street == "preflop" else ["As", "Ks", "Qs"],
        "players": [
            {
                "seat_index": i,
                "player_id": f"P{i}",
                "stack": 100.0,
                "bet": 0.0,
                "position": "",
                "is_folded": False,
                "is_thinking": False,
                "is_button": False,
                "vpip": 0,
                "action_history": [],
            }
            for i in range(6)
        ],
        "action_history": [],
        "state_version": 0,
        "timestamp": 0.0,
    }


def test_dispatcher_routes_preflop_to_preflop_strategy() -> None:
    """测试翻前动作路由到翻前策略。"""

    async def preflop_strategy(
        session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _ = session_id
        return {
            "state_version": int(payload.get("state_version", 0) or 0),
            "recommended_action": "RFI",
            "notes": "ok",
        }

    dispatcher = StrategyDispatcher(preflop_strategy=preflop_strategy)
    handler = dispatcher.as_handler()

    table_state = _create_test_table_state("preflop")
    result = asyncio.run(
        handler("s1", {"table_state": table_state, "state_version": 7})
    )
    assert result["recommended_action"] == "RFI"


def test_dispatcher_routes_postflop_to_postflop_strategy() -> None:
    """测试翻后动作路由到翻后策略。"""

    async def postflop_strategy(
        session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        _ = session_id
        return {
            "state_version": int(payload.get("state_version", 0) or 0),
            "recommended_action": "BET",
            "notes": "ok",
        }

    dispatcher = StrategyDispatcher(postflop_strategy=postflop_strategy)
    handler = dispatcher.as_handler()

    table_state = _create_test_table_state("flop")
    result = asyncio.run(
        handler("s1", {"table_state": table_state, "state_version": 3})
    )
    assert result["recommended_action"] == "BET"


def test_dispatcher_returns_fallback_when_table_state_missing() -> None:
    """测试缺少 table_state 时返回错误响应。"""
    dispatcher = StrategyDispatcher()
    handler = dispatcher.as_handler()

    result = asyncio.run(handler("s1", {"state_version": 1}))
    assert result["state_version"] == 1
    assert "table_state" in str(result.get("notes", ""))


def test_dispatcher_returns_fallback_when_strategy_missing() -> None:
    """测试策略未注册时返回备用响应。"""
    dispatcher = StrategyDispatcher()
    handler = dispatcher.as_handler()

    table_state = _create_test_table_state("preflop")
    result = asyncio.run(
        handler("s1", {"table_state": table_state, "state_version": 1})
    )
    assert result["state_version"] == 1
    assert "未注册" in str(result.get("notes", ""))
