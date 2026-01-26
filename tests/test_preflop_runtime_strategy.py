import asyncio

from bayes_poker.strategy.preflop.models import PreflopStrategy, StrategyAction, StrategyNode
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
    get_hand_key_to_169_index,
)
from bayes_poker.strategy.runtime.preflop import create_preflop_strategy


def _range_with_single_hand_probability(hand_key: str, prob: float) -> PreflopRange:
    vec = [0.0] * RANGE_169_LENGTH
    vec[get_hand_key_to_169_index()[hand_key]] = prob
    return PreflopRange(strategy=vec, evs=[0.0] * RANGE_169_LENGTH)


def test_preflop_strategy_uses_query_node_and_recommends_by_hero_hand() -> None:
    strategy = PreflopStrategy(name="Test", source_dir="/tmp")

    fold_action = StrategyAction(
        order_index=0,
        action_code="F",
        action_type="FOLD",
        bet_size_bb=None,
        is_all_in=False,
        total_frequency=0.5,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 0.0),
    )
    raise_action = StrategyAction(
        order_index=1,
        action_code="R2",
        action_type="RAISE",
        bet_size_bb=2.0,
        is_all_in=False,
        total_frequency=0.5,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 1.0),
    )

    node = StrategyNode(
        history_full="",
        history_actions="",
        history_token_count=0,
        acting_position="SB",
        source_file="test.json",
        actions=(fold_action, raise_action),
    )
    strategy.add_node(100, node)

    handler = create_preflop_strategy(strategy=strategy)
    result = asyncio.run(
        handler(
            "s1",
            {
                "street": "preflop",
                "state_version": 1,
                "stack_bb": 100,
                "history": "",
                "hero_cards": ["As", "Ks"],
            },
        )
    )

    assert result["recommended_action"] == "R2"
    assert result["recommended_amount"] == 2.0


def test_preflop_strategy_adjusts_iso_raise_size_by_num_limpers() -> None:
    strategy = PreflopStrategy(name="Test", source_dir="/tmp")

    raise_action = StrategyAction(
        order_index=0,
        action_code="R3",
        action_type="RAISE",
        bet_size_bb=3.0,
        is_all_in=False,
        total_frequency=0.2,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 1.0),
    )
    node_no_limper = StrategyNode(
        history_full="F",
        history_actions="F",
        history_token_count=1,
        acting_position="UTG",
        source_file="test.json",
        actions=(raise_action,),
    )
    strategy.add_node(100, node_no_limper)

    handler = create_preflop_strategy(strategy=strategy)
    result = asyncio.run(
        handler(
            "s1",
            {
                "street": "preflop",
                "state_version": 1,
                "stack_bb": 100,
                "history": "C",
                "hero_cards": ["As", "Ks"],
            },
        )
    )

    assert result["recommended_action"] == "R3"
    assert result["recommended_amount"] == 4.0


def test_preflop_strategy_adjusts_sb_open_frequency_by_bb_stats() -> None:
    from bayes_poker.player_metrics.enums import TableType
    from bayes_poker.player_metrics.models import PlayerStats
    from bayes_poker.storage.player_stats_repository import PlayerStatsRepository

    class StubRepo(PlayerStatsRepository):
        def __init__(self) -> None:
            pass

        def get(self, player_name: str, table_type: TableType) -> PlayerStats | None:  # type: ignore[override]
            _ = player_name, table_type
            stats = PlayerStats(player_name="BB", table_type=TableType.SIX_MAX)
            for s in stats.preflop_stats:
                s.fold_samples = 100
                s.check_call_samples = 0
                s.raise_samples = 0
            return stats

    strategy = PreflopStrategy(name="Test", source_dir="/tmp")

    fold_action = StrategyAction(
        order_index=0,
        action_code="F",
        action_type="FOLD",
        bet_size_bb=None,
        is_all_in=False,
        total_frequency=0.8,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 0.6),
    )
    raise_action = StrategyAction(
        order_index=1,
        action_code="R2",
        action_type="RAISE",
        bet_size_bb=2.0,
        is_all_in=False,
        total_frequency=0.2,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 0.4),
    )
    node_sb = StrategyNode(
        history_full="",
        history_actions="",
        history_token_count=0,
        acting_position="SB",
        source_file="test.json",
        actions=(fold_action, raise_action),
    )
    strategy.add_node(100, node_sb)

    node_bb = StrategyNode(
        history_full="R2",
        history_actions="R",
        history_token_count=1,
        acting_position="BB",
        source_file="test.json",
        actions=(
            StrategyAction(
                order_index=0,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.3,
                next_position="",
                range=_range_with_single_hand_probability("AKs", 0.0),
            ),
            StrategyAction(
                order_index=1,
                action_code="R6",
                action_type="RAISE",
                bet_size_bb=6.0,
                is_all_in=False,
                total_frequency=0.2,
                next_position="",
                range=_range_with_single_hand_probability("AKs", 0.0),
            ),
            StrategyAction(
                order_index=2,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.5,
                next_position="",
                range=_range_with_single_hand_probability("AKs", 0.0),
            ),
        ),
    )
    strategy.add_node(100, node_bb)

    handler = create_preflop_strategy(strategy=strategy, stats_repo=StubRepo())
    result = asyncio.run(
        handler(
            "s1",
            {
                "street": "preflop",
                "state_version": 1,
                "stack_bb": 100,
                "history": "",
                "hero_cards": ["As", "Ks"],
                "hero_position": "SB",
                "btn_seat": 5,
                "players": [
                    {"seat_index": 0, "player_id": "Hero"},
                    {"seat_index": 1, "player_id": "BB"},
                    {"seat_index": 2, "player_id": ""},
                    {"seat_index": 3, "player_id": ""},
                    {"seat_index": 4, "player_id": ""},
                    {"seat_index": 5, "player_id": ""},
                ],
            },
        )
    )

    assert result["recommended_action"] == "R2"
