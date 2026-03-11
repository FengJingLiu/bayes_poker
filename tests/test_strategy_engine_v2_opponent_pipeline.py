from __future__ import annotations

from pathlib import Path
import struct
import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats, StatValue
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.preflop_engine.state import ActionFamily as LegacyActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.opponent_pipeline import OpponentPipeline
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.strategy.strategy_engine.stats_adapter import PlayerNodeStatsAdapter
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.table.observed_state import ObservedTableState


def _make_strategy_repo(tmp_path: Path) -> tuple[StrategyRepositoryAdapter, int]:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="TestStrategy",
        source_dir="/tmp/TestStrategy",
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
        raise_time=0,
        pot_size=1.5,
        raise_size_bb=None,
        is_in_position=None,
    )
    open_node_far = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="X",
        history_actions="X",
        history_token_count=1,
        acting_position="UTG",
        source_file="test.json",
        action_family=LegacyActionFamily.OPEN,
        actor_position=Position.UTG,
        aggressor_position=None,
        call_count=0,
        limp_count=0,
        raise_time=0,
        pot_size=8.0,
        raise_size_bb=None,
        is_in_position=None,
    )
    node_record = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5",
        history_actions="R",
        history_token_count=1,
        acting_position="HJ",
        source_file="test.json",
        action_family=LegacyActionFamily.CALL_VS_OPEN,
        actor_position=Position.MP,
        aggressor_position=Position.UTG,
        call_count=0,
        limp_count=0,
        raise_time=1,
        pot_size=4.0,
        raise_size_bb=2.5,
        is_in_position=False,
    )
    sb_prior_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-C-SB",
        history_actions="R-C-C",
        history_token_count=3,
        acting_position="SB",
        source_file="test.json",
        action_family=LegacyActionFamily.CALL_VS_OPEN,
        actor_position=Position.SB,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=6.5,
        raise_size_bb=2.5,
        is_in_position=False,
    )
    bb_prior_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-C-BB",
        history_actions="R-C-C",
        history_token_count=3,
        acting_position="BB",
        source_file="test.json",
        action_family=LegacyActionFamily.CALL_VS_OPEN,
        actor_position=Position.BB,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=6.5,
        raise_size_bb=2.5,
        is_in_position=False,
    )
    open_node_id = repo.insert_node(source_id=source_id, node_record=open_node)
    open_node_far_id = repo.insert_node(source_id=source_id, node_record=open_node_far)
    node_id = repo.insert_node(source_id=source_id, node_record=node_record)
    sb_prior_node_id = repo.insert_node(source_id=source_id, node_record=sb_prior_node)
    bb_prior_node_id = repo.insert_node(source_id=source_id, node_record=bb_prior_node)
    repo.insert_actions(
        node_id=open_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.1,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="R2.5",
                action_type="RAISE",
                bet_size_bb=2.5,
                is_all_in=False,
                total_frequency=0.9,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=open_node_far_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.6,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="R2.5",
                action_type="RAISE",
                bet_size_bb=2.5,
                is_all_in=False,
                total_frequency=0.4,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.2,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.5,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=2,
                action_code="R6",
                action_type="RAISE",
                bet_size_bb=6.0,
                is_all_in=False,
                total_frequency=0.3,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=sb_prior_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.4,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.6,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=bb_prior_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.5,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.5,
                next_position="",
                preflop_range=PreflopRange.zeros(),
                total_ev=0.0,
                total_combos=0.0,
            ),
        ),
    )
    repo.close()
    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    return adapter, source_id


def _insert_player_stats(repo: PlayerStatsRepository, stats: PlayerStats) -> None:
    repo.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            table_type INTEGER NOT NULL,
            vpip_positive INTEGER NOT NULL DEFAULT 0,
            vpip_total INTEGER NOT NULL DEFAULT 0,
            stats_binary BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_name, table_type)
        )
        """
    )
    repo.conn.execute(
        """
        INSERT INTO player_stats (
            player_name,
            table_type,
            vpip_positive,
            vpip_total,
            stats_binary,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            stats.player_name,
            int(stats.table_type),
            stats.vpip.positive,
            stats.vpip.total,
            _serialize_player_stats(stats),
        ),
    )
    repo.conn.commit()


def _serialize_action_stats(action_stats) -> bytes:
    return struct.pack(
        "<7i",
        int(action_stats.bet_0_40),
        int(action_stats.bet_40_80),
        int(action_stats.bet_80_120),
        int(action_stats.bet_over_120),
        int(action_stats.raise_samples),
        int(action_stats.check_call_samples),
        int(action_stats.fold_samples),
    )


def _serialize_player_stats(stats: PlayerStats) -> bytes:
    name_bytes = stats.player_name.encode("utf-8")
    payload = bytearray()
    payload.extend(struct.pack("<I", len(name_bytes)))
    payload.extend(name_bytes)
    payload.extend(struct.pack("<B", int(stats.table_type)))
    payload.extend(struct.pack("<2i", stats.vpip.positive, stats.vpip.total))
    payload.extend(struct.pack("<I", len(stats.preflop_stats)))
    for action_stats in stats.preflop_stats:
        payload.extend(_serialize_action_stats(action_stats))
    payload.extend(struct.pack("<I", len(stats.postflop_stats)))
    for action_stats in stats.postflop_stats:
        payload.extend(_serialize_action_stats(action_stats))
    return bytes(payload)


def _make_player_stats(player_name: str, params: PreFlopParams) -> PlayerStats:
    stats = PlayerStats(player_name=player_name, table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=10, total=20)
    target = stats.get_preflop_stats(params)
    target.fold_samples = 2
    target.check_call_samples = 3
    target.raise_samples = 5
    target.bet_0_40 = 1
    target.bet_40_80 = 2
    target.bet_80_120 = 3
    target.bet_over_120 = 4
    return stats


def _build_players() -> list[Player]:
    return [
        Player(0, "hero", 100.0, 0.0, Position.BTN),
        Player(1, "sb", 100.0, 0.5, Position.SB),
        Player(2, "bb", 100.0, 1.0, Position.BB),
        Player(3, "opp-1", 100.0, 0.0, Position.UTG),
        Player(4, "", 100.0, 0.0, Position.MP),
        Player(5, "folded", 100.0, 0.0, Position.CO, is_folded=True),
    ]


def _build_state(*, hand_id: str) -> ObservedTableState:
    return ObservedTableState(
        table_id="table-1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id=hand_id,
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=0,
        hero_seat=0,
        players=_build_players(),
        action_history=[
            PlayerAction(
                player_index=3,
                action_type=ActionType.RAISE,
                amount=2.5,
                street=Street.PREFLOP,
            ),
            PlayerAction(
                player_index=4,
                action_type=ActionType.CALL,
                amount=2.5,
                street=Street.PREFLOP,
            ),
        ],
        state_version=1,
    )


def _build_stats_repo(tmp_path: Path) -> PlayerStatsRepository:
    repo = PlayerStatsRepository(tmp_path / "player_stats.db")
    repo.connect()
    params_open = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=MetricsPosition.UTG,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=False,
    )
    params_call_vs_open = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=MetricsPosition.HJ,
        num_callers=0,
        num_raises=1,
        num_active_players=6,
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=False,
    )
    _insert_player_stats(repo, _make_player_stats("opp-1", params_open))
    aggregated_stats = PlayerStats(
        player_name="aggregated_sixmax_100",
        table_type=TableType.SIX_MAX,
    )
    aggregated_stats.vpip = StatValue(positive=10, total=20)
    open_bucket = aggregated_stats.get_preflop_stats(params_open)
    open_bucket.fold_samples = 2
    open_bucket.check_call_samples = 3
    open_bucket.raise_samples = 5
    open_bucket.bet_0_40 = 1
    open_bucket.bet_40_80 = 2
    open_bucket.bet_80_120 = 3
    open_bucket.bet_over_120 = 4
    call_bucket = aggregated_stats.get_preflop_stats(params_call_vs_open)
    call_bucket.fold_samples = 2
    call_bucket.check_call_samples = 3
    call_bucket.raise_samples = 5
    call_bucket.bet_0_40 = 1
    call_bucket.bet_40_80 = 2
    call_bucket.bet_80_120 = 3
    call_bucket.bet_over_120 = 4
    _insert_player_stats(repo, aggregated_stats)
    return repo


def test_sequential_update_and_prior_only(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )

    context = pipeline.process_hero_snapshot(
        session_id="s1", observed_state=_build_state(hand_id="h1")
    )

    assert list(context.player_summaries)[:2] == [3, 4]
    assert context.player_summaries[3]["status"] == "posterior"
    assert context.player_summaries[4]["status"] == "posterior"
    assert context.player_summaries[1]["status"] == "prior_only"
    assert (
        3 in context.player_ranges
        and 4 in context.player_ranges
        and 1 in context.player_ranges
    )

    stats_repo.close()
    repository_adapter.close()


def test_idempotent_for_duplicate_hero_snapshot(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )
    state = _build_state(hand_id="h1")
    first = pipeline.process_hero_snapshot(session_id="s1", observed_state=state)
    second = pipeline.process_hero_snapshot(session_id="s1", observed_state=state)

    assert second.player_summaries == first.player_summaries
    assert second.last_action_fingerprint == first.last_action_fingerprint

    stats_repo.close()
    repository_adapter.close()


def test_new_hand_resets_context(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )
    first = pipeline.process_hero_snapshot(
        session_id="s1", observed_state=_build_state(hand_id="h1")
    )
    second = pipeline.process_hero_snapshot(
        session_id="s1", observed_state=_build_state(hand_id="h2")
    )

    assert first.hand_id == "h1"
    assert second.hand_id == "h2"
    assert second.last_action_fingerprint == "R2.5-C"

    stats_repo.close()
    repository_adapter.close()


def test_missing_player_uses_population_fallback(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )

    context = pipeline.process_hero_snapshot(
        session_id="s1", observed_state=_build_state(hand_id="h1")
    )

    assert context.player_summaries[4]["source_kind"] == "population"

    stats_repo.close()
    repository_adapter.close()


def test_initial_prior_uses_nearest_strategy_node(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )
    state = _build_state(hand_id="h1")
    player = state.players[3]

    prior = pipeline._build_initial_prior_range(
        player=player,
        observed_state=state,
        decision_prefix=[],
    )

    assert prior.strategy[0] == pytest.approx(0.9, abs=1e-6)

    stats_repo.close()
    repository_adapter.close()


def test_initial_prior_without_matching_node_raises_error(tmp_path: Path) -> None:
    repository_adapter, source_id = _make_strategy_repo(tmp_path)
    stats_repo = _build_stats_repo(tmp_path)
    pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=PlayerNodeStatsAdapter(stats_repo),
        source_id=source_id,
    )
    state = _build_state(hand_id="h1")
    player = state.players[2]

    with pytest.raises(ValueError):
        pipeline._build_initial_prior_range(
            player=player,
            observed_state=state,
            decision_prefix=[],
        )

    stats_repo.close()
    repository_adapter.close()
