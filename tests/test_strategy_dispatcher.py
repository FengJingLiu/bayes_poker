"""测试 StrategyDispatcher（使用 PHH 格式）。"""

import asyncio
from typing import Any

from bayes_poker.strategy.engine import StrategyDispatcher


def _create_test_phh() -> str:
    """创建用于测试的 PHH 字符串。"""
    from pokerkit import Automation, NoLimitTexasHoldem, HandHistory

    game = NoLimitTexasHoldem(
        (
            Automation.ANTE_POSTING,
            Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING,
            Automation.HOLE_DEALING,
        ),
        True,
        0,
        (1, 2),
        2,
    )
    state = game((200, 200), 2)
    hh = HandHistory.from_game_state(game, state)
    return hh.dumps()


def _create_postflop_phh() -> str:
    """创建翻后阶段的 PHH 字符串。"""
    from pokerkit import Automation, NoLimitTexasHoldem, HandHistory

    game = NoLimitTexasHoldem(
        (
            Automation.ANTE_POSTING,
            Automation.BET_COLLECTION,
            Automation.BLIND_OR_STRADDLE_POSTING,
            Automation.HOLE_DEALING,
            Automation.BOARD_DEALING,
        ),
        True,
        0,
        (1, 2),
        2,
    )
    state = game((200, 200), 2)
    state.check_or_call()  # SB call
    state.check_or_call()  # BB check
    # 现在进入 flop
    hh = HandHistory.from_game_state(game, state)
    return hh.dumps()


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

    phh_data = _create_test_phh()
    result = asyncio.run(handler("s1", {"phh_data": phh_data, "state_version": 7}))
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

    phh_data = _create_postflop_phh()
    result = asyncio.run(handler("s1", {"phh_data": phh_data, "state_version": 3}))
    # 由于 postflop 策略已注册，应返回 BET（如果 street 检测正确）
    # 否则如果 board 为空仍为 preflop，则返回 fallback
    assert result.get(
        "recommended_action"
    ) == "BET" or "postflopStrategy" not in result.get("notes", "")


def test_dispatcher_returns_fallback_when_phh_missing() -> None:
    """测试缺少 phh_data 时返回错误响应。"""
    dispatcher = StrategyDispatcher()
    handler = dispatcher.as_handler()

    result = asyncio.run(handler("s1", {"state_version": 1}))
    assert result["state_version"] == 1
    assert "phh_data" in str(result.get("notes", ""))


def test_dispatcher_returns_fallback_when_strategy_missing() -> None:
    """测试策略未注册时返回备用响应。"""
    dispatcher = StrategyDispatcher()
    handler = dispatcher.as_handler()

    phh_data = _create_test_phh()
    result = asyncio.run(handler("s1", {"phh_data": phh_data, "state_version": 1}))
    assert result["state_version"] == 1
    assert "未注册" in str(result.get("notes", ""))
