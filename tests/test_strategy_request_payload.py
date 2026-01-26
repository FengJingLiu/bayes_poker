"""测试新的 StrategyRequestPayload（基于 PHH 格式）。"""

from bayes_poker.comm.messages import StrategyRequestPayload


def test_strategy_request_payload_phh_format_roundtrip() -> None:
    """测试 PHH 格式的 StrategyRequestPayload 往返序列化。"""
    payload = StrategyRequestPayload(
        session_id="s1",
        phh_data="variant = 'NT'\nantes = [0, 0]\nactions = ['p1 cbr 6']",
        hero_seat=0,
        hero_cards=["Ah", "Kd"],
        state_version=5,
    )

    data = payload.to_dict()
    assert data["session_id"] == "s1"
    assert data["phh_data"].startswith("variant")
    assert data["hero_seat"] == 0
    assert data["hero_cards"] == ["Ah", "Kd"]
    assert data["state_version"] == 5

    parsed = StrategyRequestPayload.from_dict(data)
    assert parsed.session_id == "s1"
    assert parsed.phh_data == payload.phh_data
    assert parsed.hero_seat == 0
    assert parsed.hero_cards == ["Ah", "Kd"]
    assert parsed.state_version == 5
