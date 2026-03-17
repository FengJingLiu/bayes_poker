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
from bayes_poker.strategy.strategy_engine.core_types import ActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.gto_policy import (
    GtoPriorAction,
    GtoPriorPolicy,
)
from bayes_poker.strategy.strategy_engine.opponent_pipeline import (
    OpponentPipeline,
    _adjust_belief_with_stats_and_ev,
    _calibrate_policy,
    _build_prior_only_range_from_policy,
    _build_prior_range_from_policy,
    _resolve_action_prior_range,
    _select_matching_prior_action,
)
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.strategy.strategy_engine.stats_adapter import (
    PlayerNodeStats,
    PlayerNodeStatsAdapter,
)
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.table.observed_state import ObservedTableState


def _constant_range(probability: float, ev: float) -> PreflopRange:
    """构造固定概率与固定 EV 的 169 手范围。"""

    return PreflopRange(
        strategy=[probability] * 169,
        evs=[ev] * 169,
    )


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
        action_family=ActionFamily.OPEN,
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
        action_family=ActionFamily.OPEN,
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
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=Position.HJ,
        aggressor_position=Position.UTG,
        call_count=0,
        limp_count=0,
        raise_time=1,
        pot_size=4.0,
        raise_size_bb=2.5,
        is_in_position=True,
    )
    sb_prior_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-C-SB",
        history_actions="R-C-C",
        history_token_count=3,
        acting_position="SB",
        source_file="test.json",
        action_family=ActionFamily.CALL_VS_OPEN,
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
        action_family=ActionFamily.CALL_VS_OPEN,
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
                preflop_range=_constant_range(0.1, 0.0),
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
                preflop_range=_constant_range(0.9, 0.0),
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
                preflop_range=_constant_range(0.6, 0.0),
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
                preflop_range=_constant_range(0.4, 0.0),
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
                preflop_range=_constant_range(0.2, 0.0),
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
                preflop_range=_constant_range(0.5, 0.0),
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
                preflop_range=_constant_range(0.3, 0.0),
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
                preflop_range=_constant_range(0.4, 0.0),
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
                preflop_range=_constant_range(0.6, 0.0),
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
                preflop_range=_constant_range(0.5, 0.0),
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
                preflop_range=_constant_range(0.5, 0.0),
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
    assert context.player_summaries[1]["status"] == "prior_only_deferred"
    assert 3 in context.player_ranges and 4 in context.player_ranges
    assert 1 not in context.player_ranges

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

    prior_policy = pipeline._build_initial_prior_range(
        player=player,
        observed_state=state,
        decision_prefix=[],
    )
    prior = _build_prior_range_from_policy(prior_policy, action_name="R2.5")

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
    unmatched_prefix = [
        PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
        PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
    ]

    with pytest.raises(ValueError):
        pipeline._build_initial_prior_range(
            player=player,
            observed_state=state,
            decision_prefix=unmatched_prefix,
        )

    stats_repo.close()
    repository_adapter.close()


def test_build_prior_range_from_policy_returns_selected_action_range() -> None:
    """应返回目标动作对应的 hand-level 范围。"""

    policy = GtoPriorPolicy(
        action_names=("F", "C", "R6"),
        actions=(
            GtoPriorAction(
                action_name="F",
                blended_frequency=0.30,
                belief_range=_constant_range(0.30, -0.20),
            ),
            GtoPriorAction(
                action_name="C",
                blended_frequency=0.30,
                belief_range=_constant_range(0.30, 0.40),
            ),
            GtoPriorAction(
                action_name="R6",
                blended_frequency=0.40,
                belief_range=_constant_range(0.40, 1.60),
            ),
        ),
    )

    prior = _build_prior_range_from_policy(policy, action_name="R6")

    assert prior.strategy[0] == pytest.approx(0.40)
    assert prior.evs[0] == pytest.approx(1.60)


def test_build_prior_range_from_policy_missing_action_raises() -> None:
    """目标动作不存在时应抛出异常。"""

    policy = GtoPriorPolicy(
        action_names=("F", "C"),
        actions=(
            GtoPriorAction(
                action_name="F",
                blended_frequency=0.30,
                belief_range=_constant_range(0.30, -0.20),
            ),
            GtoPriorAction(
                action_name="C",
                blended_frequency=0.70,
                belief_range=_constant_range(0.70, 0.40),
            ),
        ),
    )

    with pytest.raises(ValueError, match="不存在目标动作"):
        _build_prior_range_from_policy(policy, action_name="R6")


def test_resolve_action_prior_range_missing_belief_raises() -> None:
    """动作缺失 belief_range 时应抛出异常。"""

    action = GtoPriorAction(
        action_name="C",
        blended_frequency=1.0,
        belief_range=None,
    )

    with pytest.raises(ValueError, match="缺少 belief_range"):
        _resolve_action_prior_range(action)


def test_select_matching_prior_action_requires_type_match() -> None:
    """真实动作类型找不到匹配先验动作时应抛异常。"""

    prior_policy = GtoPriorPolicy(
        action_names=("C",),
        actions=(
            GtoPriorAction(
                action_name="C",
                action_type="CALL",
                blended_frequency=1.0,
                belief_range=_constant_range(1.0, 0.1),
            ),
        ),
    )
    observed_action = PlayerAction(
        player_index=3,
        action_type=ActionType.RAISE,
        amount=6.0,
        street=Street.PREFLOP,
    )

    with pytest.raises(ValueError, match="类型匹配"):
        _select_matching_prior_action(
            prior_policy=prior_policy,
            action=observed_action,
            big_blind=1.0,
        )


def test_select_matching_prior_action_chooses_nearest_size() -> None:
    """同类型多动作时应选择尺度最接近者。"""

    prior_policy = GtoPriorPolicy(
        action_names=("R4", "R8"),
        actions=(
            GtoPriorAction(
                action_name="R4",
                action_type="RAISE",
                bet_size_bb=4.0,
                blended_frequency=0.5,
                belief_range=_constant_range(0.5, 0.1),
            ),
            GtoPriorAction(
                action_name="R8",
                action_type="RAISE",
                bet_size_bb=8.0,
                blended_frequency=0.5,
                belief_range=_constant_range(0.5, 0.2),
            ),
        ),
    )
    observed_action = PlayerAction(
        player_index=3,
        action_type=ActionType.RAISE,
        amount=7.2,
        street=Street.PREFLOP,
    )

    matched = _select_matching_prior_action(
        prior_policy=prior_policy,
        action=observed_action,
        big_blind=1.0,
    )

    assert matched.action_name == "R8"


def test_adjust_belief_with_stats_and_ev_biases_high_ev() -> None:
    """当 stats 频率高于 GTO 时应更偏向高 EV 手牌。"""

    prior_range = PreflopRange(
        strategy=[0.2, 0.2] + [0.0] * 167,
        evs=[2.0, -2.0] + [0.0] * 167,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.60,
        call_probability=0.20,
        fold_probability=0.20,
        bet_0_40_probability=0.0,
        bet_40_80_probability=0.0,
        bet_80_120_probability=1.0,
        bet_over_120_probability=0.0,
        confidence=1.0,
        global_pfr=0.0,
        global_vpip=0.0,
        total_hands=0,
        source_kind="test",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
    )

    assert posterior.strategy[0] > posterior.strategy[1]
    assert posterior.total_frequency() == pytest.approx(0.60, abs=1e-6)


def test_adjust_belief_with_stats_and_ev_uses_next_ev_bucket_when_top_saturated() -> (
    None
):
    """高 EV 顶端已饱和时应继续调整后续 EV 组合。"""

    prior_range = PreflopRange(
        strategy=[1.0, 1.0, 0.0] + [0.0] * 166,
        evs=[3.0, 2.5, 2.0] + [0.0] * 166,
    )
    current_frequency = prior_range.total_frequency()
    target_raise_frequency = min(current_frequency + 0.003, 1.0)
    node_stats = PlayerNodeStats(
        raise_probability=target_raise_frequency,
        call_probability=0.200,
        fold_probability=1.0 - target_raise_frequency - 0.200,
        bet_0_40_probability=0.0,
        bet_40_80_probability=0.0,
        bet_80_120_probability=1.0,
        bet_over_120_probability=0.0,
        confidence=1.0,
        global_pfr=0.0,
        global_vpip=0.0,
        total_hands=0,
        source_kind="test",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
    )

    assert posterior.strategy[0] == pytest.approx(1.0)
    assert posterior.strategy[1] == pytest.approx(1.0)
    assert posterior.strategy[2] > 0.0
    assert posterior.total_frequency() == pytest.approx(
        target_raise_frequency,
        abs=1e-6,
    )


def test_adjust_belief_blends_global_pfr_for_raise() -> None:
    """aggressive action 应混合节点级 stats 和全局 PFR。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.2] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
    )

    assert posterior.total_frequency() == pytest.approx(0.41, abs=0.01)


def test_adjust_belief_no_blend_for_fold() -> None:
    """fold action 不应混合全局信号, 继续用节点级。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.5] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.FOLD,
        node_stats=node_stats,
    )

    assert posterior.total_frequency() == pytest.approx(0.5, abs=0.01)


def test_feature_flag_disabled_no_blend() -> None:
    """enable_global_raise_blending=False 时行为与旧逻辑一致。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.2] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
        enable_global_raise_blending=False,
    )

    assert posterior.total_frequency() == pytest.approx(0.2, abs=0.01)


def test_build_prior_only_range_from_policy_aggregates_continue_actions() -> None:
    """prior-only 场景应聚合非弃牌动作。"""

    policy = GtoPriorPolicy(
        action_names=("F", "C", "R6"),
        actions=(
            GtoPriorAction(
                action_name="F",
                blended_frequency=0.30,
                belief_range=_constant_range(0.30, -0.20),
            ),
            GtoPriorAction(
                action_name="C",
                blended_frequency=0.30,
                belief_range=_constant_range(0.30, 0.40),
            ),
            GtoPriorAction(
                action_name="R6",
                blended_frequency=0.40,
                belief_range=_constant_range(0.40, 1.60),
            ),
        ),
    )

    prior = _build_prior_only_range_from_policy(policy)
    expected_ev = (0.30 * 0.40 + 0.40 * 1.60) / 0.70

    assert prior.strategy[0] == pytest.approx(0.70)
    assert prior.evs[0] == pytest.approx(expected_ev)


def test_calibrate_policy_preserves_hand_level_belief_evs() -> None:
    """校准策略时应保留先验动作中的 hand-level EV。"""

    prior_policy = GtoPriorPolicy(
        action_names=("C", "R6"),
        actions=(
            GtoPriorAction(
                action_name="C",
                blended_frequency=0.50,
                belief_range=_constant_range(0.50, 0.30),
            ),
            GtoPriorAction(
                action_name="R6",
                blended_frequency=0.50,
                belief_range=_constant_range(0.50, 1.80),
            ),
        ),
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.50,
        call_probability=0.50,
        fold_probability=0.00,
        bet_0_40_probability=0.00,
        bet_40_80_probability=0.00,
        bet_80_120_probability=1.00,
        bet_over_120_probability=0.00,
        confidence=1.00,
        global_pfr=0.0,
        global_vpip=0.0,
        total_hands=0,
        source_kind="test",
    )

    calibrated = _calibrate_policy(
        prior_policy=prior_policy,
        node_stats=node_stats,
    )
    action_by_name = {action.action_name: action for action in calibrated.actions}

    assert action_by_name["C"].range.evs[0] == pytest.approx(0.30)
    assert action_by_name["R6"].range.evs[0] == pytest.approx(1.80)


@pytest.mark.parametrize("action_type", [ActionType.BET, ActionType.ALL_IN])
def test_adjust_belief_blends_global_pfr_for_bet_and_all_in(
    action_type: ActionType,
) -> None:
    """BET 和 ALL_IN 类型应与 RAISE 一样触发全局 PFR 混合。

    Args:
        action_type: 参数化的动作类型 (BET 或 ALL_IN)。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.2] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=action_type,
        node_stats=node_stats,
    )

    assert posterior.total_frequency() == pytest.approx(0.41, abs=0.01)


def test_adjust_belief_no_blend_when_total_hands_zero() -> None:
    """total_hands == 0 时不应混合全局 PFR, 即使是激进动作。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.2] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.5,
        global_vpip=0.6,
        total_hands=0,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
    )

    assert posterior.total_frequency() == pytest.approx(0.2, abs=0.01)


def test_adjust_belief_global_pfr_zero_fallback() -> None:
    """global_pfr = 0.0 时混合不应出错, 频率应低于纯 stats_frequency。

    Returns:
        None.
    """

    prior_range = PreflopRange(
        strategy=[0.2] * 169,
        evs=[1.0] * 169,
    )
    node_stats = PlayerNodeStats(
        raise_probability=0.2,
        call_probability=0.3,
        fold_probability=0.5,
        bet_0_40_probability=0.25,
        bet_40_80_probability=0.25,
        bet_80_120_probability=0.25,
        bet_over_120_probability=0.25,
        confidence=0.3,
        global_pfr=0.0,
        global_vpip=0.6,
        total_hands=100,
        source_kind="player",
    )

    posterior = _adjust_belief_with_stats_and_ev(
        prior=prior_range,
        observed_action_type=ActionType.RAISE,
        node_stats=node_stats,
    )

    # global_pfr = 0.0 将拉低混合后的频率至低于 stats_frequency (0.2)
    assert posterior.total_frequency() == pytest.approx(0.06, abs=0.01)
