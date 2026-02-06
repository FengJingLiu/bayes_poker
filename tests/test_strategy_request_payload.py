"""测试新的 StrategyRequestPayload（基于 ObservedTableState 格式）。"""

from bayes_poker.comm.messages import StrategyRequestPayload


def test_strategy_request_payload_table_state_format_roundtrip() -> None:
    """测试 ObservedTableState 格式的 StrategyRequestPayload 往返序列化。"""
    table_state = {
        "street": "preflop",
        "pot": 1.5,
        "btn_seat": 2,
        "hero_seat": 0,
        "hero_cards": ["Ah", "Kd"],
        "players": [],
    }

    payload = StrategyRequestPayload(
        session_id="s1",
        table_state=table_state,
        hero_seat=0,
        hero_cards=["Ah", "Kd"],
        state_version=5,
    )

    data = payload.to_dict()
    assert data["session_id"] == "s1"
    assert data["table_state"]["street"] == "preflop"
    assert data["hero_seat"] == 0
    assert data["hero_cards"] == ["Ah", "Kd"]
    assert data["state_version"] == 5

    parsed = StrategyRequestPayload.from_dict(data)
    assert parsed.session_id == "s1"
    assert parsed.table_state["street"] == "preflop"
    assert parsed.hero_seat == 0
    assert parsed.hero_cards == ["Ah", "Kd"]
    assert parsed.state_version == 5
