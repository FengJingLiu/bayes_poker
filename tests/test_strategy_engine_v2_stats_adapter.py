from __future__ import annotations

from pathlib import Path
import struct

from bayes_poker.domain.table import Player, Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.strategy_engine.core_types import (
    ActionFamily,
    NodeContext,
    PlayerNodeContext,
)
from bayes_poker.strategy.strategy_engine.stats_adapter import (
    PlayerNodeStatsAdapter,
    PlayerNodeStatsAdapterConfig,
)


def _serialize_action_stats(action_stats: ActionStats) -> bytes:
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


def _make_node_context() -> PlayerNodeContext:
    params = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=MetricsPosition.CO,
        num_callers=1,
        num_raises=0,
        num_active_players=6,
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=False,
    )
    return PlayerNodeContext(
        actor_seat=5,
        actor_position=Position.CO,
        query_history="C-F",
        node_context=NodeContext(
            action_family=ActionFamily.LIMP,
            actor_position=Position.CO,
            aggressor_position=None,
            call_count=0,
            limp_count=1,
            raise_size_bb=None,
        ),
        params=params,
        action_order=(3, 4),
    )


def _make_player_stats(*, player_name: str, params: PreFlopParams) -> PlayerStats:
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


def test_player_stats_hit(tmp_path: Path) -> None:
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo, _make_player_stats(player_name="villain", params=context.params)
        )
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100",
                params=context.params,
            ),
        )

        adapter = PlayerNodeStatsAdapter(repo)
        stats = adapter.load(
            player_name="villain",
            table_type=TableType.SIX_MAX,
            node_context=context,
        )

    assert stats.source_kind == "player"
    assert stats.raise_probability == 0.5
    assert stats.call_probability == 0.3
    assert stats.fold_probability == 0.2
    assert stats.bet_0_40_probability == 0.25
    assert stats.bet_40_80_probability == 0.25
    assert stats.bet_80_120_probability == 0.25
    assert stats.bet_over_120_probability == 0.25
    assert stats.confidence == 30 / 50


def test_population_fallback_when_player_missing(tmp_path: Path) -> None:
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100",
                params=context.params,
            ),
        )

        adapter = PlayerNodeStatsAdapter(repo)
        stats = adapter.load(
            player_name="missing-player",
            table_type=TableType.SIX_MAX,
            node_context=context,
        )

    assert stats.source_kind == "population"
    assert stats.raise_probability == 0.75
    assert stats.call_probability == 0.15
    assert stats.fold_probability == 0.1


def test_population_fallback_when_player_name_missing(tmp_path: Path) -> None:
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        _insert_player_stats(
            repo,
            _make_player_stats(
                player_name="aggregated_sixmax_100",
                params=context.params,
            ),
        )

        adapter = PlayerNodeStatsAdapter(repo)
        stats = adapter.load(
            player_name=None,
            table_type=TableType.SIX_MAX,
            node_context=context,
        )

    assert stats.source_kind == "population"
    assert stats.raise_probability == 0.75


def test_uniform_population_fallback_without_aggregated_stats(tmp_path: Path) -> None:
    context = _make_node_context()
    with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
        adapter = PlayerNodeStatsAdapter(
            repo,
            config=PlayerNodeStatsAdapterConfig(
                pool_prior_strength=20.0, confidence_k=20.0
            ),
        )
        stats = adapter.load(
            player_name=None,
            table_type=TableType.SIX_MAX,
            node_context=context,
        )

    assert stats.source_kind == "population"
    assert stats.raise_probability == 1 / 3
    assert stats.call_probability == 1 / 3
    assert stats.fold_probability == 1 / 3
    assert stats.bet_0_40_probability == 0.25
    assert stats.confidence == 0.0
