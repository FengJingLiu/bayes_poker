from bayes_poker.comm.messages import StrategyRequestPayload


def test_strategy_request_payload_supports_history_and_players_roundtrip() -> None:
    payload = StrategyRequestPayload(
        session_id="s1",
        state_version=1,
        history="F-R2",
        players=[{"seat_index": 1, "player_id": "Villain"}],
        btn_seat=3,
    )

    data = payload.to_dict()
    assert data["history"] == "F-R2"
    assert data["players"][0]["player_id"] == "Villain"
    assert data["btn_seat"] == 3

    parsed = StrategyRequestPayload.from_dict(data)
    assert parsed.history == "F-R2"
    assert parsed.players[0]["player_id"] == "Villain"
    assert parsed.btn_seat == 3

