from __future__ import annotations

from pathlib import Path

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.strategy.preflop_engine.state import ActionFamily as LegacyActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.contracts import (
    RecommendationDecision,
    UnsupportedScenarioDecision,
)
from bayes_poker.strategy.strategy_engine.hero_resolver import HeroGtoResolver
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.strategy.strategy_engine.session_context import StrategySessionContext
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.table.observed_state import ObservedTableState


def _make_strategy_repo(tmp_path: Path) -> tuple[StrategyRepositoryAdapter, int]:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="HeroStrategy",
        source_dir="/tmp/HeroStrategy",
        format_version=2,
    )
    open_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="",
        history_actions="",
        history_token_count=0,
        acting_position="UTG",
        source_file="test.json",
        action_family=LegacyActionFamily.OPEN,
        actor_position=Position.UTG,
        aggressor_position=None,
        call_count=0,
        limp_count=0,
        raise_size_bb=None,
        is_in_position=None,
    )
    call_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-C",
        history_actions="R-C",
        history_token_count=2,
        acting_position="CO",
        source_file="test.json",
        action_family=LegacyActionFamily.CALL_VS_OPEN,
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_size_bb=2.5,
        is_in_position=True,
    )
    open_node_id = repo.insert_node(source_id=source_id, node_record=open_node)
    call_node_id = repo.insert_node(source_id=source_id, node_record=call_node)
    repo.insert_actions(
        node_id=open_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0, "F", "FOLD", None, False, 0.1, "", PreflopRange.zeros(), 0.0, 0.0
            ),
            ParsedStrategyActionRecord(
                1, "R2.5", "RAISE", 2.5, False, 0.9, "", PreflopRange.zeros(), 0.0, 0.0
            ),
        ),
    )
    repo.insert_actions(
        node_id=call_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0, "F", "FOLD", None, False, 0.9, "", PreflopRange.zeros(), 0.0, 0.0
            ),
            ParsedStrategyActionRecord(
                1, "R9.5", "RAISE", 9.5, False, 0.1, "", PreflopRange.zeros(), 0.0, 0.0
            ),
        ),
    )
    repo.close()
    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    return adapter, source_id


def _build_players_for_open() -> list[Player]:
    return [
        Player(0, "btn", 100.0, 0.0, Position.BTN),
        Player(1, "sb", 100.0, 0.5, Position.SB),
        Player(2, "bb", 100.0, 1.0, Position.BB),
        Player(3, "hero", 100.0, 0.0, Position.UTG),
        Player(4, "mp", 100.0, 0.0, Position.MP),
        Player(5, "co", 100.0, 0.0, Position.CO),
    ]


def _build_players_for_call() -> list[Player]:
    return [
        Player(0, "btn", 100.0, 0.0, Position.BTN),
        Player(1, "sb", 100.0, 0.5, Position.SB),
        Player(2, "bb", 100.0, 1.0, Position.BB),
        Player(3, "utg", 100.0, 0.0, Position.UTG),
        Player(4, "mp", 100.0, 0.0, Position.MP),
        Player(5, "hero", 100.0, 0.0, Position.CO),
    ]


def _build_session_context() -> StrategySessionContext:
    context = StrategySessionContext(
        session_id="s1",
        table_id="t1",
        hand_id="h1",
        state_version=1,
    )
    context.player_ranges[1] = PreflopRange.ones()
    context.player_summaries[1] = {"status": "posterior"}
    return context


def test_hero_gto_recommendation_exact_match(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(repository_adapter=adapter, source_id=source_id)
    observed_state = ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_players_for_open(),
        action_history=[],
        state_version=1,
    )

    decision = resolver.resolve(
        observed_state=observed_state, session_context=_build_session_context()
    )

    assert isinstance(decision, RecommendationDecision)
    assert decision.action_code == "R2.5"
    assert decision.amount == 2.5
    assert "hero_posterior_deferred_v1" in decision.notes
    assert "seat_1" in decision.range_breakdown

    adapter.close()


def test_hero_gto_recommendation_nearest_match(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(repository_adapter=adapter, source_id=source_id)
    observed_state = ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=5,
        hero_seat=5,
        players=_build_players_for_call(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.6, Street.PREFLOP),
            PlayerAction(4, ActionType.CALL, 2.6, Street.PREFLOP),
        ],
        state_version=1,
    )

    decision = resolver.resolve(
        observed_state=observed_state, session_context=_build_session_context()
    )

    assert isinstance(decision, RecommendationDecision)
    assert decision.action_code == "F"
    assert "matched_history=R2.5-C" in decision.notes

    adapter.close()


def test_hero_no_match_returns_unsupported(tmp_path: Path) -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="Empty",
        source_dir="/tmp/Empty",
        format_version=2,
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    resolver = HeroGtoResolver(repository_adapter=adapter, source_id=source_id)
    observed_state = ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=5,
        hero_seat=5,
        players=_build_players_for_call(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            PlayerAction(4, ActionType.CALL, 2.5, Street.PREFLOP),
        ],
        state_version=1,
    )

    decision = resolver.resolve(
        observed_state=observed_state, session_context=_build_session_context()
    )

    assert isinstance(decision, UnsupportedScenarioDecision)

    adapter.close()
