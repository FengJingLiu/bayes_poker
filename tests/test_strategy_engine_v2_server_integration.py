from __future__ import annotations

import asyncio

from bayes_poker.comm.protocol import MessageEnvelope, MessageType
from bayes_poker.comm.server import ServerConfig, WebSocketServer
from bayes_poker.comm.session import ClientSession, TableSession
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.strategy.strategy_engine.contracts import (
    NoResponseDecision,
    RecommendationDecision,
    SafeFallbackDecision,
    UnsupportedScenarioDecision,
)
from bayes_poker.table.observed_state import ObservedTableState


def _build_players() -> list[Player]:
    return [
        Player(0, "hero", 100.0, 0.0, Position.BTN),
        Player(1, "sb", 100.0, 0.5, Position.SB),
        Player(2, "bb", 100.0, 1.0, Position.BB),
        Player(3, "utg", 100.0, 0.0, Position.UTG),
        Player(4, "mp", 100.0, 0.0, Position.MP),
        Player(5, "co", 100.0, 0.0, Position.CO),
    ]


def _build_state(*, actor_seat: int) -> ObservedTableState:
    return ObservedTableState(
        table_id="table-1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="hand-1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=actor_seat,
        hero_seat=0,
        players=_build_players(),
        action_history=[PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP)],
        state_version=1,
    )


async def _setup_server(handler):
    server = WebSocketServer(ServerConfig(), strategy_handler=handler)
    client_session = ClientSession(client_id="client-1")
    server.session_manager._table_sessions["table-1"] = TableSession(
        session_id="table-1",
        client_id="client-1",
    )
    captured: list[MessageEnvelope] = []

    async def fake_send(_client_session, msg: MessageEnvelope) -> None:
        captured.append(msg)

    server._send_to_client = fake_send  # type: ignore[assignment]
    return server, client_session, captured


def test_hero_turn_sends_payload() -> None:
    async def handler(_session_id: str, _observed_state):
        return RecommendationDecision(
            state_version=1,
            action_code="R2.5",
            amount=2.5,
            confidence=0.9,
            ev=None,
            notes="hero_posterior_deferred_v1",
        )

    async def run() -> None:
        server, client_session, captured = await _setup_server(handler)
        msg = MessageEnvelope(
            type=MessageType.TABLE_SNAPSHOT,
            session_id="table-1",
            payload=_build_state(actor_seat=0).to_dict(),
        )
        await server._handle_table_snapshot(client_session, msg)

        assert len(captured) == 1
        payload = captured[0].payload
        assert payload["session_id"] == "table-1"
        assert payload["recommended_action"] == "R2.5"
        assert payload["notes"] == "hero_posterior_deferred_v1"

    asyncio.run(run())


def test_non_hero_does_not_call_handler() -> None:
    called = False

    async def handler(_session_id: str, _observed_state):
        nonlocal called
        called = True
        return NoResponseDecision(state_version=1, reason="not_hero_turn")

    async def run() -> None:
        server, client_session, captured = await _setup_server(handler)
        msg = MessageEnvelope(
            type=MessageType.TABLE_SNAPSHOT,
            session_id="table-1",
            payload=_build_state(actor_seat=3).to_dict(),
        )
        await server._handle_table_snapshot(client_session, msg)

        assert called is False
        assert captured == []

    asyncio.run(run())


def test_unsupported_and_fallback_map_to_transport_payload() -> None:
    decisions = [
        UnsupportedScenarioDecision(state_version=1, reason="unsupported"),
        SafeFallbackDecision(
            state_version=1, error_code="hero_resolver_error", notes="fallback"
        ),
    ]

    async def run() -> None:
        last_notes = ""
        for decision in decisions:

            async def handler(_session_id: str, _observed_state, decision=decision):
                return decision

            server, client_session, captured = await _setup_server(handler)
            msg = MessageEnvelope(
                type=MessageType.TABLE_SNAPSHOT,
                session_id="table-1",
                payload=_build_state(actor_seat=0).to_dict(),
            )
            await server._handle_table_snapshot(client_session, msg)

            assert len(captured) == 1
            assert captured[0].payload["recommended_action"] == ""
            last_notes = captured[0].payload["notes"]
        assert last_notes == "fallback"

    asyncio.run(run())
