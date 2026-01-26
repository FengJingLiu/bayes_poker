"""测试 PHH 序列化模块。"""

import pytest


def test_state_to_phh_and_back() -> None:
    """测试 State 到 PHH 的往返序列化。"""
    from pokerkit import Automation, NoLimitTexasHoldem
    from bayes_poker.comm.phh_serializer import state_to_phh, phh_to_state

    # 创建游戏和状态
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
    state = game((200, 200, 200, 200, 200, 200), 6)

    # 执行一些动作
    state.complete_bet_or_raise_to(6)  # UTG raise
    state.fold()  # HJ fold
    state.fold()  # CO fold

    # 序列化
    result = state_to_phh(game, state)
    assert result.success
    assert result.phh_str
    assert "cbr 6" in result.phh_str

    # 反序列化
    restored = phh_to_state(result.phh_str)
    assert restored.success
    assert restored.state is not None
    assert restored.state.actor_index == state.actor_index
    assert float(restored.state.total_pot_amount) == float(state.total_pot_amount)


def test_phh_to_state_with_invalid_data() -> None:
    """测试无效 PHH 数据的处理。"""
    from bayes_poker.comm.phh_serializer import phh_to_state

    result = phh_to_state("invalid phh data")
    assert not result.success
    assert result.error is not None


def test_extract_state_info() -> None:
    """测试从 State 提取信息。"""
    from pokerkit import Automation, NoLimitTexasHoldem
    from bayes_poker.comm.phh_serializer import extract_state_info

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

    info = extract_state_info(state)
    assert info["street"] == "preflop"
    assert info["pot"] > 0
    assert len(info["stacks"]) == 2


def test_strategy_request_payload_with_phh() -> None:
    """测试新的 StrategyRequestPayload 格式。"""
    from bayes_poker.comm.messages import StrategyRequestPayload

    payload = StrategyRequestPayload(
        session_id="s1",
        phh_data="variant = 'NT'\nactions = []",
        hero_seat=0,
        hero_cards=["Ah", "Kd"],
        state_version=1,
    )

    data = payload.to_dict()
    assert data["phh_data"] == "variant = 'NT'\nactions = []"
    assert data["hero_cards"] == ["Ah", "Kd"]

    parsed = StrategyRequestPayload.from_dict(data)
    assert parsed.phh_data == payload.phh_data
    assert parsed.hero_cards == payload.hero_cards
