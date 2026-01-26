import asyncio
from typing import Any

from bayes_poker.strategy.engine import StrategyDispatcher


def test_dispatcher_routes_preflop_to_preflop_strategy() -> None:
    async def preflop_strategy(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _ = session_id
        return {
            "state_version": int(payload.get("state_version", 0) or 0),
            "recommended_action": "RFI",
            "notes": "ok",
        }

    dispatcher = StrategyDispatcher(preflop_strategy=preflop_strategy)
    handler = dispatcher.as_handler()

    result = asyncio.run(handler("s1", {"street": "preflop", "state_version": 7}))
    assert result["recommended_action"] == "RFI"


def test_dispatcher_routes_postflop_to_postflop_strategy() -> None:
    async def postflop_strategy(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _ = session_id
        return {
            "state_version": int(payload.get("state_version", 0) or 0),
            "recommended_action": "BET",
            "notes": "ok",
        }

    dispatcher = StrategyDispatcher(postflop_strategy=postflop_strategy)
    handler = dispatcher.as_handler()

    result = asyncio.run(handler("s1", {"street": "flop", "state_version": 3}))
    assert result["recommended_action"] == "BET"


def test_dispatcher_returns_fallback_when_strategy_missing() -> None:
    dispatcher = StrategyDispatcher()
    handler = dispatcher.as_handler()

    result = asyncio.run(handler("s1", {"street": "preflop", "state_version": 1}))
    assert result["state_version"] == 1
    assert "未注册" in str(result.get("notes", ""))
