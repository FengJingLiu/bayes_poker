from __future__ import annotations

import math
from pathlib import Path
import random

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.strategy.strategy_engine.core_types import ActionFamily
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH
from bayes_poker.strategy.range.belief_adjustment import adjust_belief_range
from bayes_poker.strategy.strategy_engine.contracts import (
    RecommendationDecision,
    UnsupportedScenarioDecision,
)
from bayes_poker.strategy.strategy_engine.gto_policy import (
    GtoPriorAction,
    GtoPriorPolicy,
)
from bayes_poker.strategy.strategy_engine.hero_resolver import (
    HeroGtoResolver,
    _adjust_hero_policy,
    _compute_opponent_aggression_ratio,
    _is_aggressive_action,
)
from bayes_poker.strategy.strategy_engine.node_mapper import SyntheticTemplateKind
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
    call_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-C",
        history_actions="R-C",
        history_token_count=2,
        acting_position="CO",
        source_file="test.json",
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=6.5,
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


def _build_players_for_facing_3bet_reentry() -> list[Player]:
    """构造 Hero open 后 facing 3-bet 再次决策的玩家列表。"""

    return [
        Player(0, "btn", 100.0, 0.0, Position.BTN, is_folded=True),
        Player(1, "sb", 99.5, 0.5, Position.SB, is_folded=True),
        Player(2, "bb", 99.0, 1.0, Position.BB, is_folded=True),
        Player(3, "hero", 97.5, 2.5, Position.UTG),
        Player(4, "villain", 92.0, 8.0, Position.MP),
        Player(5, "co", 100.0, 0.0, Position.CO, is_folded=True),
    ]


def _build_hero_open_facing_3bet_state() -> ObservedTableState:
    """构造 Hero open 后遭遇 3-bet 并重新轮到 Hero 的状态。"""

    return ObservedTableState(
        table_id="t-reentry",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h-reentry",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=3,
        hero_seat=3,
        players=_build_players_for_facing_3bet_reentry(),
        action_history=[
            PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            PlayerAction(4, ActionType.RAISE, 8.0, Street.PREFLOP),
            PlayerAction(5, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(0, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(1, ActionType.FOLD, 0.0, Street.PREFLOP),
            PlayerAction(2, ActionType.FOLD, 0.0, Street.PREFLOP),
        ],
        state_version=1,
    )


def _make_strategy_repo_with_facing_3bet_node(
    tmp_path: Path,
) -> tuple[StrategyRepositoryAdapter, int]:
    """构造包含 facing 3-bet reentry 节点的最小策略仓库。"""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy_reentry.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="HeroFacing3Bet",
        source_dir="/tmp/HeroFacing3Bet",
        format_version=2,
    )
    matched_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2.5-R8-F-F-F-F",
        history_actions="R-R-F-F-F-F",
        history_token_count=6,
        acting_position="UTG",
        source_file="test.json",
        action_family=ActionFamily.OPEN,
        actor_position=Position.UTG,
        aggressor_position=Position.MP,
        call_count=0,
        limp_count=0,
        raise_time=2,
        pot_size=12.0,
        raise_size_bb=8.0,
        is_in_position=False,
    )
    unmatched_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="UNMATCHED_REENTRY",
        history_actions="",
        history_token_count=0,
        acting_position="UTG",
        source_file="test.json",
        action_family=ActionFamily.OPEN,
        actor_position=Position.UTG,
        aggressor_position=Position.MP,
        call_count=0,
        limp_count=0,
        raise_time=2,
        pot_size=12.0,
        raise_size_bb=8.0,
        is_in_position=False,
    )
    matched_node_id = repo.insert_node(source_id=source_id, node_record=matched_node)
    unmatched_node_id = repo.insert_node(
        source_id=source_id,
        node_record=unmatched_node,
    )
    for node_id in (matched_node_id, unmatched_node_id):
        repo.insert_actions(
            node_id=node_id,
            action_records=(
                ParsedStrategyActionRecord(
                    0,
                    "F",
                    "FOLD",
                    None,
                    False,
                    1.0,
                    "",
                    PreflopRange.zeros(),
                    0.0,
                    0.0,
                ),
            ),
        )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy_reentry.db")
    adapter.connect()
    return adapter, source_id


def _build_session_context() -> StrategySessionContext:
    return _build_session_context_with_posterior_seats()


def _build_session_context_with_posterior_seats(
    *,
    posterior_seats: tuple[int, ...] = (1,),
    prior_only_seats: tuple[int, ...] = (),
) -> StrategySessionContext:
    context = StrategySessionContext(
        session_id="s1",
        table_id="t1",
        hand_id="h1",
        state_version=1,
    )
    for seat in posterior_seats:
        context.player_ranges[seat] = PreflopRange.ones()
        context.player_summaries[seat] = {"status": "posterior"}
    for seat in prior_only_seats:
        context.player_summaries[seat] = {"status": "prior_only_deferred"}
    return context


def test_hero_gto_recommendation_exact_match(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
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
    assert decision.confidence == 0.9
    assert "hero_posterior_deferred_v1" in decision.notes
    assert "seat_1" in decision.range_breakdown
    assert decision.selected_node_id is not None
    assert decision.selected_source_id == source_id
    assert decision.sampling_random is not None
    assert 0.0 <= decision.sampling_random < 1.0
    assert sum(decision.action_distribution.values()) == 1.0

    adapter.close()


def test_hero_gto_recommendation_nearest_match(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
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
        observed_state=observed_state,
        session_context=_build_session_context_with_posterior_seats(
            posterior_seats=(3, 4),
        ),
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
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
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
        observed_state=observed_state,
        session_context=_build_session_context_with_posterior_seats(
            posterior_seats=(3, 4),
        ),
    )

    assert isinstance(decision, UnsupportedScenarioDecision)

    adapter.close()


def test_hero_resolver_supports_facing_3bet_reentry(tmp_path: Path) -> None:
    """Hero reentry 到 facing 3-bet 节点时应匹配完整翻前历史。"""

    adapter, source_id = _make_strategy_repo_with_facing_3bet_node(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
    observed_state = _build_hero_open_facing_3bet_state()
    session_context = _build_session_context_with_posterior_seats(
        posterior_seats=(4,),
    )

    decision = resolver.resolve(
        observed_state=observed_state,
        session_context=session_context,
    )

    assert isinstance(decision, RecommendationDecision)
    assert "matched_history=R2.5-R8-F-F-F-F" in decision.notes

    adapter.close()


def test_hero_requires_posterior_for_acted_live_opponents(tmp_path: Path) -> None:
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
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

    with pytest.raises(ValueError, match="未完成后验范围计算"):
        resolver.resolve(
            observed_state=observed_state,
            session_context=_build_session_context_with_posterior_seats(
                posterior_seats=(3,),
                prior_only_seats=(4,),
            ),
        )

    adapter.close()


def test_hero_resolver_prefers_runtime_source_ids_order(tmp_path: Path) -> None:
    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    first_source_id = repo.upsert_source(
        strategy_name="First",
        source_dir="/tmp/First",
        format_version=2,
    )
    second_source_id = repo.upsert_source(
        strategy_name="Second",
        source_dir="/tmp/Second",
        format_version=2,
    )
    first_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="FIRST_OPEN",
        history_actions="",
        history_token_count=1,
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
    second_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="SECOND_OPEN",
        history_actions="",
        history_token_count=1,
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
    first_node_id = repo.insert_node(source_id=first_source_id, node_record=first_node)
    second_node_id = repo.insert_node(
        source_id=second_source_id,
        node_record=second_node,
    )
    repo.insert_actions(
        node_id=first_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0,
                "F",
                "FOLD",
                None,
                False,
                0.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
            ParsedStrategyActionRecord(
                1,
                "C",
                "CALL",
                None,
                False,
                0.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
            ParsedStrategyActionRecord(
                2,
                "R2.5",
                "RAISE",
                2.5,
                False,
                1.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=second_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0,
                "F",
                "FOLD",
                None,
                False,
                0.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
            ParsedStrategyActionRecord(
                1,
                "C",
                "CALL",
                None,
                False,
                1.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
            ParsedStrategyActionRecord(
                2,
                "R2.5",
                "RAISE",
                2.5,
                False,
                0.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
        ),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=(first_source_id, second_source_id),
        random_generator=random.Random(0),
    )
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
        observed_state=observed_state,
        session_context=_build_session_context(),
        source_ids=(second_source_id, first_source_id),
    )

    assert isinstance(decision, RecommendationDecision)
    assert decision.selected_source_id == second_source_id
    assert decision.selected_node_id == second_node_id
    assert decision.action_code == "C"

    adapter.close()


def test_hero_resolver_matches_acted_history_actions_first(tmp_path: Path) -> None:
    """当候选节点存在多条行动线时, 应优先命中与已行动线一致的候选。"""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="HeroStrategy",
        source_dir="/tmp/HeroStrategy",
        format_version=2,
    )

    matched_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="MATCHED_RC",
        history_actions="R-C",
        history_token_count=2,
        acting_position="CO",
        source_file="test.json",
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=6.5,
        raise_size_bb=2.5,
        is_in_position=True,
    )
    unmatched_node = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="UNMATCHED_RR",
        history_actions="R-R",
        history_token_count=2,
        acting_position="CO",
        source_file="test.json",
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=Position.CO,
        aggressor_position=Position.UTG,
        call_count=1,
        limp_count=0,
        raise_time=1,
        pot_size=6.5,
        raise_size_bb=2.5,
        is_in_position=True,
    )
    matched_node_id = repo.insert_node(source_id=source_id, node_record=matched_node)
    unmatched_node_id = repo.insert_node(
        source_id=source_id, node_record=unmatched_node
    )
    repo.insert_actions(
        node_id=matched_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0,
                "C",
                "CALL",
                None,
                False,
                1.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
        ),
    )
    repo.insert_actions(
        node_id=unmatched_node_id,
        action_records=(
            ParsedStrategyActionRecord(
                0,
                "F",
                "FOLD",
                None,
                False,
                1.0,
                "",
                PreflopRange.zeros(),
                0.0,
                0.0,
            ),
        ),
    )
    repo.close()

    adapter = StrategyRepositoryAdapter(tmp_path / "preflop_strategy.db")
    adapter.connect()
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
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
        observed_state=observed_state,
        session_context=_build_session_context_with_posterior_seats(
            posterior_seats=(3, 4),
        ),
    )

    assert isinstance(decision, RecommendationDecision)
    assert decision.selected_node_id == matched_node_id
    assert decision.action_code == "C"
    assert decision.selected_node_id != unmatched_node_id

    adapter.close()


# ---------------------------------------------------------------------------
# 单元测试: _is_aggressive_action
# ---------------------------------------------------------------------------


class TestIsAggressiveAction:
    """_is_aggressive_action 判断动作编码是否属于激进动作."""

    def test_raise_with_size(self) -> None:
        assert _is_aggressive_action("R2.5") is True

    def test_raise_all_in(self) -> None:
        assert _is_aggressive_action("RAI") is True

    def test_raise_lowercase(self) -> None:
        assert _is_aggressive_action("r3.0") is True

    def test_fold(self) -> None:
        assert _is_aggressive_action("F") is False

    def test_call(self) -> None:
        assert _is_aggressive_action("C") is False

    def test_check(self) -> None:
        assert _is_aggressive_action("X") is False


# ---------------------------------------------------------------------------
# 单元测试: _compute_opponent_aggression_ratio
# ---------------------------------------------------------------------------


def _build_observed_state_for_aggression(
    *,
    hero_seat: int,
    action_history: list[PlayerAction],
    players: list[Player] | None = None,
) -> ObservedTableState:
    """构造用于测试 aggression ratio 的简化 ObservedTableState.

    Args:
        hero_seat: hero 座位号.
        action_history: 行动历史.
        players: 玩家列表, 默认为 6 人桌.

    Returns:
        ObservedTableState 实例.
    """
    if players is None:
        players = [
            Player(0, "btn", 100.0, 0.0, Position.BTN),
            Player(1, "sb", 100.0, 0.5, Position.SB),
            Player(2, "bb", 100.0, 1.0, Position.BB),
            Player(3, "utg", 100.0, 0.0, Position.UTG),
            Player(4, "mp", 100.0, 0.0, Position.MP),
            Player(5, "co", 100.0, 0.0, Position.CO),
        ]
    return ObservedTableState(
        table_id="t1",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id="h1",
        street=Street.PREFLOP,
        btn_seat=0,
        actor_seat=hero_seat,
        hero_seat=hero_seat,
        players=players,
        action_history=action_history,
        state_version=1,
    )


def _build_session_with_opponent_data(
    *,
    seat: int,
    prior_frequency: float,
    matched_action_type: str,
    posterior_total_freq: float,
) -> StrategySessionContext:
    """构造包含对手 prior/posterior 数据的 session context.

    Args:
        seat: 对手座位号.
        prior_frequency: GTO 先验频率.
        matched_action_type: 匹配的动作类型字符串.
        posterior_total_freq: 后验范围总频率.

    Returns:
        StrategySessionContext 实例.
    """
    ctx = StrategySessionContext(
        session_id="s1",
        table_id="t1",
        hand_id="h1",
        state_version=1,
    )
    # 使用均匀策略再缩放到目标频率
    strategy = [posterior_total_freq] * RANGE_169_LENGTH
    ctx.player_ranges[seat] = PreflopRange(
        strategy=strategy,
        evs=[0.0] * RANGE_169_LENGTH,
    )
    ctx.player_summaries[seat] = {
        "status": "posterior",
        "prior_frequency": prior_frequency,
        "matched_action_type": matched_action_type,
    }
    return ctx


class TestComputeOpponentAggressionRatio:
    """_compute_opponent_aggression_ratio 计算聚合激进度比值."""

    def test_no_acted_opponents_returns_one(self) -> None:
        """无已行动对手时返回 1.0."""
        observed = _build_observed_state_for_aggression(
            hero_seat=3,
            action_history=[],
        )
        ctx = StrategySessionContext(
            session_id="s1",
            table_id="t1",
            hand_id="h1",
            state_version=1,
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        assert ratio == 1.0
        assert details == []

    def test_aggressive_opponent_wide_range_hero_more_aggressive(self) -> None:
        """对手做 raise 且 posterior > prior => 范围宽(弱) => hero 更激进."""
        ctx = _build_session_with_opponent_data(
            seat=3,
            prior_frequency=0.10,
            matched_action_type="raise",
            posterior_total_freq=0.20,
        )
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            ],
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        posterior_freq = ctx.player_ranges[3].total_frequency()
        raw_ratio = posterior_freq / 0.10
        expected = raw_ratio**0.5
        assert ratio == pytest.approx(expected, rel=1e-4)
        assert ratio > 1.0
        assert len(details) == 1
        assert details[0]["seat"] == 3
        assert "dampened_ratio" in details[0]

    def test_passive_opponent_more_passive_than_gto(self) -> None:
        """对手做 call 且 posterior > prior => ratio>1 => hero 更激进."""
        ctx = _build_session_with_opponent_data(
            seat=3,
            prior_frequency=0.30,
            matched_action_type="call",
            posterior_total_freq=0.50,
        )
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.CALL, 2.5, Street.PREFLOP),
            ],
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        posterior_freq = ctx.player_ranges[3].total_frequency()
        raw_ratio = posterior_freq / 0.30
        expected = raw_ratio**0.5
        assert ratio == pytest.approx(expected, rel=1e-4)
        assert ratio > 1.0
        assert len(details) == 1

    def test_missing_prior_frequency_skipped(self) -> None:
        """player_summaries 缺少 prior_frequency 的对手被跳过."""
        ctx = StrategySessionContext(
            session_id="s1",
            table_id="t1",
            hand_id="h1",
            state_version=1,
        )
        ctx.player_ranges[3] = PreflopRange.ones()
        ctx.player_summaries[3] = {
            "status": "posterior",
            # 缺少 prior_frequency
            "matched_action_type": "raise",
        }
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            ],
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        assert ratio == 1.0
        assert details == []

    def test_multiple_opponents_multiplicative(self) -> None:
        """多个对手的比值取乘积."""
        ctx = StrategySessionContext(
            session_id="s1",
            table_id="t1",
            hand_id="h1",
            state_version=1,
        )
        # 对手 seat=3: raise, prior=0.10, posterior uniform 0.20
        strategy_3 = [0.20] * RANGE_169_LENGTH
        ctx.player_ranges[3] = PreflopRange(
            strategy=strategy_3,
            evs=[0.0] * RANGE_169_LENGTH,
        )
        ctx.player_summaries[3] = {
            "status": "posterior",
            "prior_frequency": 0.10,
            "matched_action_type": "raise",
        }
        # 对手 seat=4: call, prior=0.30, posterior uniform 0.50
        strategy_4 = [0.50] * RANGE_169_LENGTH
        ctx.player_ranges[4] = PreflopRange(
            strategy=strategy_4,
            evs=[0.0] * RANGE_169_LENGTH,
        )
        ctx.player_summaries[4] = {
            "status": "posterior",
            "prior_frequency": 0.30,
            "matched_action_type": "call",
        }
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
                PlayerAction(4, ActionType.CALL, 2.5, Street.PREFLOP),
            ],
        )
        result = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        freq_3 = ctx.player_ranges[3].total_frequency()
        freq_4 = ctx.player_ranges[4].total_frequency()
        raw_3 = freq_3 / 0.10
        raw_4 = freq_4 / 0.30
        dampened_3 = raw_3**0.5
        dampened_4 = raw_4**0.5
        expected = dampened_3 * dampened_4
        expected_clamped = max(0.1, min(expected, 5.0))
        assert result[0] == pytest.approx(expected_clamped, rel=1e-4)
        assert len(result[1]) == 2

    def test_clamp_upper_bound(self) -> None:
        """极端宽范围的仍存活对手比值被 clamp 到 5.0."""
        ctx = _build_session_with_opponent_data(
            seat=3,
            prior_frequency=0.01,
            matched_action_type="raise",
            posterior_total_freq=0.80,
        )
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            ],
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        assert ratio == 5.0
        assert len(details) == 1

    def test_clamp_lower_bound(self) -> None:
        """极端窄范围对手的比值被 clamp 到 0.1."""
        ctx = _build_session_with_opponent_data(
            seat=3,
            prior_frequency=0.90,
            matched_action_type="raise",
            posterior_total_freq=0.005,
        )
        observed = _build_observed_state_for_aggression(
            hero_seat=5,
            action_history=[
                PlayerAction(3, ActionType.RAISE, 2.5, Street.PREFLOP),
            ],
        )
        ratio, details = _compute_opponent_aggression_ratio(
            session_context=ctx,
            observed_state=observed,
        )
        assert ratio == 0.1
        assert len(details) == 1


# ---------------------------------------------------------------------------
# 单元测试: adjust_belief_range
# ---------------------------------------------------------------------------


class TestAdjustHeroBeliefRange:
    """adjust_belief_range 按 EV 排序做约束式信念重分配."""

    def test_target_equals_current_no_change(self) -> None:
        """目标频率与当前频率相同时不调整."""
        br = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        current_freq = br.total_frequency()
        result = adjust_belief_range(
            belief_range=br,
            target_frequency=current_freq,
            low_mass_threshold=1e-9,
        )
        for i in range(RANGE_169_LENGTH):
            assert result.strategy[i] == pytest.approx(0.5, abs=1e-6)

    def test_increase_target_adds_to_high_ev(self) -> None:
        """目标频率 > 当前频率时, 优先向高 EV 手牌增加频率."""
        evs = [float(i) for i in range(RANGE_169_LENGTH)]
        br = PreflopRange(
            strategy=[0.3] * RANGE_169_LENGTH,
            evs=evs,
        )
        current_freq = br.total_frequency()
        target = current_freq + 0.05
        result = adjust_belief_range(
            belief_range=br,
            target_frequency=target,
            low_mass_threshold=1e-9,
        )
        # 高 EV 手牌 (index=168) 应比原来更高
        assert result.strategy[168] > 0.3
        # 总频率应接近目标
        assert result.total_frequency() == pytest.approx(target, abs=1e-4)

    def test_decrease_target_removes_from_low_ev(self) -> None:
        """目标频率 < 当前频率时, 优先从低 EV 手牌削减频率."""
        evs = [float(i) for i in range(RANGE_169_LENGTH)]
        br = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=evs,
        )
        current_freq = br.total_frequency()
        target = current_freq - 0.05
        result = adjust_belief_range(
            belief_range=br,
            target_frequency=target,
            low_mass_threshold=1e-9,
        )
        # 低 EV 手牌 (index=0) 应比原来更低
        assert result.strategy[0] < 0.5
        # 总频率应接近目标
        assert result.total_frequency() == pytest.approx(target, abs=1e-4)

    def test_all_zeros_range_stays_zero_when_no_ev_info(self) -> None:
        """全零策略且目标为零时保持不变."""
        br = PreflopRange.zeros()
        result = adjust_belief_range(
            belief_range=br,
            target_frequency=0.0,
            low_mass_threshold=1e-9,
        )
        assert all(v == 0.0 for v in result.strategy)


# ---------------------------------------------------------------------------
# 单元测试: _adjust_hero_policy
# ---------------------------------------------------------------------------


def _make_simple_policy(
    *,
    fold_freq: float = 0.4,
    raise_freq: float = 0.6,
    raise_name: str = "R2.5",
    fold_belief: PreflopRange | None = None,
    raise_belief: PreflopRange | None = None,
) -> GtoPriorPolicy:
    """构造包含一个被动动作和一个激进动作的简单 policy.

    Args:
        fold_freq: fold 频率.
        raise_freq: raise 频率.
        raise_name: raise 动作编码.
        fold_belief: fold 的 belief range.
        raise_belief: raise 的 belief range.

    Returns:
        GtoPriorPolicy 实例.
    """
    fold_action = GtoPriorAction(
        action_name="F",
        blended_frequency=fold_freq,
        belief_range=fold_belief,
        total_ev=-1.0,
    )
    raise_action = GtoPriorAction(
        action_name=raise_name,
        blended_frequency=raise_freq,
        belief_range=raise_belief,
        total_ev=2.0,
    )
    return GtoPriorPolicy(
        action_names=(raise_name, "F"),
        actions=(fold_action, raise_action),
    )


def _make_frc_policy(
    *,
    fold_freq: float = 0.3,
    call_freq: float = 0.3,
    raise_freq: float = 0.4,
    call_belief: PreflopRange | None = None,
    raise_belief: PreflopRange | None = None,
) -> GtoPriorPolicy:
    """构造包含 F/C/R 三个动作的 policy.

    Args:
        fold_freq: fold 频率.
        call_freq: call 频率.
        raise_freq: raise 频率.
        call_belief: call 的 belief range.
        raise_belief: raise 的 belief range.

    Returns:
        GtoPriorPolicy 实例.
    """
    fold_action = GtoPriorAction(
        action_name="F",
        blended_frequency=fold_freq,
        belief_range=None,
        total_ev=-1.0,
    )
    call_action = GtoPriorAction(
        action_name="C",
        blended_frequency=call_freq,
        belief_range=call_belief,
        total_ev=0.5,
    )
    raise_action = GtoPriorAction(
        action_name="R2.5",
        blended_frequency=raise_freq,
        belief_range=raise_belief,
        total_ev=2.0,
    )
    return GtoPriorPolicy(
        action_names=("R2.5", "C", "F"),
        actions=(fold_action, call_action, raise_action),
    )


class TestAdjustHeroPolicy:
    """_adjust_hero_policy 根据 aggression_ratio 调整 hero 策略."""

    def test_ratio_one_returns_same_policy(self) -> None:
        """aggression_ratio=1.0 时返回相同 policy."""
        policy = _make_simple_policy()
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.0)
        assert result is policy

    def test_ratio_greater_than_one_increases_aggressive(self) -> None:
        """ratio > 1 时激进动作频率增加, 被动动作频率减少."""
        policy = _make_simple_policy(fold_freq=0.4, raise_freq=0.6)
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)

        fold_new = None
        raise_new = None
        for a in result.actions:
            if a.action_name == "F":
                fold_new = a.blended_frequency
            elif a.action_name == "R2.5":
                raise_new = a.blended_frequency
        assert raise_new is not None and fold_new is not None
        assert raise_new > 0.6  # 激进频率增加
        assert fold_new < 0.4  # 被动频率减少
        assert raise_new + fold_new == pytest.approx(1.0, abs=1e-6)

    def test_ratio_less_than_one_decreases_aggressive(self) -> None:
        """ratio < 1 时激进动作频率减少, 被动动作频率增加."""
        policy = _make_simple_policy(fold_freq=0.4, raise_freq=0.6)
        result = _adjust_hero_policy(policy=policy, aggression_ratio=0.5)

        fold_new = None
        raise_new = None
        for a in result.actions:
            if a.action_name == "F":
                fold_new = a.blended_frequency
            elif a.action_name == "R2.5":
                raise_new = a.blended_frequency
        assert raise_new is not None and fold_new is not None
        assert raise_new < 0.6  # 激进频率减少
        assert fold_new > 0.4  # 被动频率增加
        assert raise_new + fold_new == pytest.approx(1.0, abs=1e-6)

    def test_no_aggressive_actions_returns_unchanged(self) -> None:
        """没有激进动作时返回原 policy."""
        fold_action = GtoPriorAction(action_name="F", blended_frequency=0.6)
        call_action = GtoPriorAction(action_name="C", blended_frequency=0.4)
        policy = GtoPriorPolicy(
            action_names=("F", "C"),
            actions=(fold_action, call_action),
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=2.0)
        assert result is policy

    def test_no_passive_actions_returns_unchanged(self) -> None:
        """没有被动动作时返回原 policy."""
        r1 = GtoPriorAction(action_name="R2.5", blended_frequency=0.7)
        r2 = GtoPriorAction(action_name="R5.0", blended_frequency=0.3)
        policy = GtoPriorPolicy(
            action_names=("R2.5", "R5.0"),
            actions=(r1, r2),
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=2.0)
        assert result is policy

    def test_frequencies_always_sum_to_one(self) -> None:
        """任意 ratio 下调整后频率总和为 1.0."""
        policy = _make_simple_policy(fold_freq=0.3, raise_freq=0.7)
        for ratio in [0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
            result = _adjust_hero_policy(policy=policy, aggression_ratio=ratio)
            total = sum(a.blended_frequency for a in result.actions)
            assert total == pytest.approx(1.0, abs=1e-6), f"ratio={ratio}"

    def test_belief_range_adjusted_for_aggressive_actions(self) -> None:
        """激进动作的 belief_range 随频率调整."""
        raise_belief = PreflopRange(
            strategy=[0.5] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )
        policy = _make_simple_policy(
            fold_freq=0.4,
            raise_freq=0.6,
            raise_belief=raise_belief,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)

        raise_action = None
        for a in result.actions:
            if a.action_name == "R2.5":
                raise_action = a
        assert raise_action is not None
        assert raise_action.belief_range is not None
        # belief_range 应被调整, 不再全部是 0.5
        original_freq = raise_belief.total_frequency()
        new_freq = raise_action.belief_range.total_frequency()
        assert new_freq != pytest.approx(original_freq, abs=1e-4)

    def test_preserves_synthetic_template_kind(self) -> None:
        """调整后保留 synthetic_template_kind 字段."""
        fold_action = GtoPriorAction(action_name="F", blended_frequency=0.4)
        raise_action = GtoPriorAction(
            action_name="R2.5",
            blended_frequency=0.6,
        )
        policy = GtoPriorPolicy(
            action_names=("R2.5", "F"),
            actions=(fold_action, raise_action),
            synthetic_template_kind=SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
        assert (
            result.synthetic_template_kind == SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3
        )

    def test_multiple_aggressive_actions_all_scaled(self) -> None:
        """多个激进动作按相同比例缩放."""
        fold = GtoPriorAction(action_name="F", blended_frequency=0.3)
        r1 = GtoPriorAction(action_name="R2.5", blended_frequency=0.5)
        r2 = GtoPriorAction(action_name="R5.0", blended_frequency=0.2)
        policy = GtoPriorPolicy(
            action_names=("R2.5", "R5.0", "F"),
            actions=(fold, r1, r2),
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=0.5)

        r1_new = None
        r2_new = None
        for a in result.actions:
            if a.action_name == "R2.5":
                r1_new = a.blended_frequency
            elif a.action_name == "R5.0":
                r2_new = a.blended_frequency

        assert r1_new is not None and r2_new is not None
        # 两个激进动作的比例应与原始一致 (5:2)
        assert r1_new / r2_new == pytest.approx(0.5 / 0.2, rel=1e-4)


class TestAdjustHeroPolicyCallBeliefLinkage:
    """_adjust_hero_policy 中 call belief_range 与 aggression_ratio 同向联动."""

    def _make_belief(self, base_strategy: float = 0.4) -> PreflopRange:
        """创建带 EV 梯度的 belief range.

        Args:
            base_strategy: 初始策略频率.

        Returns:
            带单调 EV 梯度的 PreflopRange.
        """
        return PreflopRange(
            strategy=[base_strategy] * RANGE_169_LENGTH,
            evs=[float(i) for i in range(RANGE_169_LENGTH)],
        )

    def test_ratio_gt1_call_belief_expands(self) -> None:
        """ratio > 1 时 call belief_range 总频率应增大."""
        call_belief = self._make_belief(0.4)
        raise_belief = self._make_belief(0.3)
        original_call_frequency = call_belief.total_frequency()

        policy = _make_frc_policy(
            fold_freq=0.3,
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=call_belief,
            raise_belief=raise_belief,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)

        call_action = next(action for action in result.actions if action.action_name == "C")
        assert call_action.belief_range is not None
        new_call_frequency = call_action.belief_range.total_frequency()
        assert new_call_frequency > original_call_frequency

    def test_ratio_lt1_call_belief_shrinks(self) -> None:
        """ratio < 1 时 call belief_range 总频率应减小."""
        call_belief = self._make_belief(0.4)
        raise_belief = self._make_belief(0.3)
        original_call_frequency = call_belief.total_frequency()

        policy = _make_frc_policy(
            fold_freq=0.3,
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=call_belief,
            raise_belief=raise_belief,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=0.5)

        call_action = next(action for action in result.actions if action.action_name == "C")
        assert call_action.belief_range is not None
        new_call_frequency = call_action.belief_range.total_frequency()
        assert new_call_frequency < original_call_frequency

    def test_ratio_one_call_belief_unchanged(self) -> None:
        """ratio = 1.0 时仍返回原 policy 对象."""
        call_belief = self._make_belief(0.4)
        policy = _make_frc_policy(
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=call_belief,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.0)
        assert result is policy

    def test_call_no_belief_range_passthrough(self) -> None:
        """call 动作没有 belief_range 时应保持 None."""
        policy = _make_frc_policy(
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=None,
            raise_belief=None,
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
        call_action = next(action for action in result.actions if action.action_name == "C")
        assert call_action.belief_range is None

    def test_fold_belief_not_adjusted(self) -> None:
        """fold 动作的 belief_range 不应被联动调整."""
        fold_belief = self._make_belief(0.5)
        fold_action = GtoPriorAction(
            action_name="F",
            blended_frequency=0.3,
            belief_range=fold_belief,
            total_ev=-1.0,
        )
        call_action = GtoPriorAction(
            action_name="C",
            blended_frequency=0.3,
            belief_range=self._make_belief(0.4),
            total_ev=0.5,
        )
        raise_action = GtoPriorAction(
            action_name="R2.5",
            blended_frequency=0.4,
            belief_range=self._make_belief(0.3),
            total_ev=2.0,
        )
        policy = GtoPriorPolicy(
            action_names=("R2.5", "C", "F"),
            actions=(fold_action, call_action, raise_action),
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
        fold_result = next(action for action in result.actions if action.action_name == "F")
        assert fold_result.belief_range is fold_belief

    def test_check_action_also_adjusted(self) -> None:
        """X(check) 动作也应按 call 类逻辑调整 belief_range."""
        check_belief = self._make_belief(0.4)
        original_frequency = check_belief.total_frequency()

        check_action = GtoPriorAction(
            action_name="X",
            blended_frequency=0.3,
            belief_range=check_belief,
            total_ev=0.2,
        )
        raise_action = GtoPriorAction(
            action_name="R2.5",
            blended_frequency=0.7,
            belief_range=self._make_belief(0.3),
            total_ev=2.0,
        )
        policy = GtoPriorPolicy(
            action_names=("R2.5", "X"),
            actions=(check_action, raise_action),
        )
        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
        check_result = next(action for action in result.actions if action.action_name == "X")
        assert check_result.belief_range is not None
        assert check_result.belief_range.total_frequency() > original_frequency

    def test_frequencies_still_sum_to_one(self) -> None:
        """增加 call belief 联动后 blended_frequency 总和仍应为 1.0."""
        policy = _make_frc_policy(
            fold_freq=0.3,
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=self._make_belief(0.4),
            raise_belief=self._make_belief(0.3),
        )
        for ratio in [0.2, 0.5, 0.8, 1.5, 2.0, 3.0]:
            result = _adjust_hero_policy(policy=policy, aggression_ratio=ratio)
            total_frequency = sum(action.blended_frequency for action in result.actions)
            assert total_frequency == pytest.approx(1.0, abs=1e-6), f"ratio={ratio}"

    def test_action_belief_ranges_remain_mutually_exclusive(self) -> None:
        """调整后同一手牌在各动作上的总频率不应超过 1.0."""
        policy = _make_frc_policy(
            fold_freq=0.3,
            call_freq=0.3,
            raise_freq=0.4,
            call_belief=self._make_belief(0.4),
            raise_belief=self._make_belief(0.4),
        )

        result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)

        belief_ranges = [
            action.belief_range
            for action in result.actions
            if action.belief_range is not None
        ]
        for index in range(RANGE_169_LENGTH):
            combo_total = sum(
                belief_range.strategy[index]
                for belief_range in belief_ranges
            )
            assert combo_total <= 1.0 + 1e-9, index


# ---------------------------------------------------------------------------
# 集成测试: resolve() 中的 hero 调整流程
# ---------------------------------------------------------------------------


def test_hero_resolve_with_aggressive_opponent_adjusts_notes(
    tmp_path: Path,
) -> None:
    """resolve() 在有对手后验数据时, notes 中包含 aggression_ratio."""
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
    ctx = StrategySessionContext(
        session_id="s1",
        table_id="t1",
        hand_id="h1",
        state_version=1,
    )
    # seat=1 (SB) 有后验数据: raise, prior=0.10
    strategy_sb = [0.20] * RANGE_169_LENGTH
    ctx.player_ranges[1] = PreflopRange(
        strategy=strategy_sb,
        evs=[0.0] * RANGE_169_LENGTH,
    )
    ctx.player_summaries[1] = {
        "status": "posterior",
        "prior_frequency": 0.10,
        "matched_action_type": "raise",
    }
    observed = ObservedTableState(
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
        observed_state=observed,
        session_context=ctx,
    )
    assert isinstance(decision, RecommendationDecision)
    assert "aggression_ratio=" in decision.notes
    adapter.close()


def test_hero_resolve_no_opponent_data_ratio_is_one(
    tmp_path: Path,
) -> None:
    """无对手后验数据时 aggression_ratio 应为 1.0."""
    adapter, source_id = _make_strategy_repo(tmp_path)
    resolver = HeroGtoResolver(
        repository_adapter=adapter,
        source_id=source_id,
        random_generator=random.Random(0),
    )
    ctx = StrategySessionContext(
        session_id="s1",
        table_id="t1",
        hand_id="h1",
        state_version=1,
    )
    observed = ObservedTableState(
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
        observed_state=observed,
        session_context=ctx,
    )
    assert isinstance(decision, RecommendationDecision)
    assert "aggression_ratio=1.0000" in decision.notes
    adapter.close()
