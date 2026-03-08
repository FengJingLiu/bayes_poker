"""翻前策略 runtime 测试（使用 ObservedTableState）。"""

import asyncio
from pathlib import Path
from typing import Any

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, Position as TablePosition
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.table.observed_state import ObservedTableState, create_observed_state
from bayes_poker.strategy.preflop_parse.models import (
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.preflop_engine.state import ActionFamily
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
    get_hand_key_to_169_index,
)
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.runtime.preflop import create_preflop_strategy


def _range_with_single_hand_probability(hand_key: str, prob: float) -> PreflopRange:
    """创建只有单手牌概率的范围。"""
    vec = [0.0] * RANGE_169_LENGTH
    vec[get_hand_key_to_169_index()[hand_key]] = prob
    return PreflopRange(strategy=vec, evs=[0.0] * RANGE_169_LENGTH)


def _create_observed_state_for_test(
    hero_seat: int = 0,
    btn_seat: int = 0,
    stack_bb: float = 100.0,
    hero_cards: tuple[str, str] = ("As", "Ks"),
    player_count: int = 6,
    action_history: list[tuple[int, ActionType, float]] | None = None,
) -> ObservedTableState:
    """创建用于测试的 ObservedTableState。

    Args:
        hero_seat: hero 座位索引
        btn_seat: 庄家座位索引
        stack_bb: hero 筹码（BB 单位）
        hero_cards: hero 底牌
        player_count: 玩家数量
        action_history: 动作历史列表 [(seat, action_type, amount), ...]

    Returns:
        ObservedTableState 实例
    """
    state = create_observed_state(
        player_count=player_count,
        small_blind=0.5,
        big_blind=1.0,
    )
    state.btn_seat = btn_seat
    state.hero_seat = hero_seat
    state.hero_cards = hero_cards

    # 设置玩家筹码
    state.players = [
        Player(
            seat_index=i,
            player_id=f"P{i}",
            stack=stack_bb,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=i == btn_seat,
            vpip=0,
        )
        for i in range(player_count)
    ]

    # 记录动作历史
    if action_history:
        for seat, action_type, amount in action_history:
            state.record_action(seat, action_type, amount)

    return state


def _build_runtime_repository(tmp_path: Path) -> tuple[PreflopStrategyRepository, int]:
    """构造供 runtime shared adapter 使用的 sqlite 仓库."""

    repository = PreflopStrategyRepository(tmp_path / "runtime_preflop.db")
    repository.connect()
    source_id = repository.upsert_source(
        strategy_name="RuntimeTest",
        source_dir="/tmp/runtime",
        format_version=1,
    )
    node_ids = repository.insert_nodes(
        source_id=source_id,
        node_records=(
            ParsedStrategyNodeRecord(
                stack_bb=100,
                history_full="R2",
                history_actions="R",
                history_token_count=1,
                acting_position="CO",
                source_file="test.json",
                action_family=ActionFamily.CALL_VS_OPEN,
                actor_position=TablePosition.CO,
                aggressor_position=TablePosition.UTG,
                call_count=0,
                limp_count=0,
                raise_size_bb=2.0,
                is_in_position=False,
            ),
        ),
    )
    repository.insert_actions(
        node_id=node_ids["R2"],
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.20,
                next_position="",
                preflop_range=_range_with_single_hand_probability("AKs", 0.0),
                total_ev=0.0,
                total_combos=10.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.30,
                next_position="",
                preflop_range=_range_with_single_hand_probability("AKs", 0.1),
                total_ev=0.0,
                total_combos=10.0,
            ),
            ParsedStrategyActionRecord(
                order_index=2,
                action_code="R9.5",
                action_type="RAISE",
                bet_size_bb=9.5,
                is_all_in=False,
                total_frequency=0.50,
                next_position="",
                preflop_range=_range_with_single_hand_probability("AKs", 1.0),
                total_ev=0.0,
                total_combos=10.0,
            ),
        ),
    )
    return repository, source_id


def test_preflop_strategy_uses_query_node_and_recommends_by_hero_hand() -> None:
    """测试策略查询并根据 hero 手牌推荐动作。"""
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

    # 创建观察者状态（无 history，hero 在 SB 位置 seat=1，btn_seat=0）
    observed_state = _create_observed_state_for_test(
        hero_seat=1,  # SB
        btn_seat=0,
        stack_bb=100.0,
        hero_cards=("As", "Ks"),
    )

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
            },
        )
    )

    assert result["recommended_action"] == "R2"
    assert result["recommended_amount"] == 2.0


def test_preflop_strategy_uses_shared_engine_for_non_standard_open_size(
    tmp_path: Path,
) -> None:
    """测试 runtime 会用共享映射处理非标准 open 尺度。"""
    strategy = PreflopStrategy(name="Test", source_dir="/tmp")

    fold_action = StrategyAction(
        order_index=0,
        action_code="F",
        action_type="FOLD",
        bet_size_bb=None,
        is_all_in=False,
        total_frequency=0.20,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 0.0),
    )
    call_action = StrategyAction(
        order_index=1,
        action_code="C",
        action_type="CALL",
        bet_size_bb=None,
        is_all_in=False,
        total_frequency=0.30,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 0.1),
    )
    raise_action = StrategyAction(
        order_index=2,
        action_code="R9.5",
        action_type="RAISE",
        bet_size_bb=9.5,
        is_all_in=False,
        total_frequency=0.50,
        next_position="",
        range=_range_with_single_hand_probability("AKs", 1.0),
    )
    node = StrategyNode(
        history_full="R2",
        history_actions="R",
        history_token_count=1,
        acting_position="MP",
        source_file="test.json",
        actions=(fold_action, call_action, raise_action),
    )
    strategy.add_node(100, node)

    repository, source_id = _build_runtime_repository(tmp_path)
    handler = create_preflop_strategy(
        strategy=strategy,
        strategy_repository=repository,
        strategy_source_id=source_id,
    )
    observed_state = _create_observed_state_for_test(
        hero_seat=4,  # MP
        btn_seat=5,
        stack_bb=90.0,
        hero_cards=("As", "Ks"),
        action_history=[
            (2, ActionType.RAISE, 3.0),  # UTG open 3bb
        ],
    )

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
            },
        )
    )

    assert result.get("recommended_action") == "R9.5"
    assert result.get("recommended_amount") == 9.5
    explanation = result.get("explanation", {})
    assert explanation.get("mapped_level") == 2
    assert explanation.get("matched_history") == "R2"
    assert explanation.get("price_adjustment_applied") is True
    repository.close()


def test_preflop_strategy_falls_back_when_table_state_is_incomplete() -> None:
    """测试不完整 table_state 会回退到旧 payload 字段。"""
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
    strategy.add_node(
        100,
        StrategyNode(
            history_full="",
            history_actions="",
            history_token_count=0,
            acting_position="SB",
            source_file="test.json",
            actions=(fold_action, raise_action),
        ),
    )

    handler = create_preflop_strategy(strategy=strategy)
    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "table_state": {
                    "btn_seat": 0,
                    "hero_seat": 1,
                    "hero_cards": ["As", "Ks"],
                    "players": [],
                    "player_count": 6,
                    "big_blind": 1.0,
                    "small_blind": 0.5,
                    "action_history": [],
                    "street": "preflop",
                },
                "hero_stack_bb": 100,
                "hero_cards": ["As", "Ks"],
                "action_history": "",
                "hero_position": "SB",
            },
        )
    )

    assert result["recommended_action"] == "R2"
    assert result["recommended_amount"] == 2.0


def test_preflop_strategy_skips_shared_adapter_for_overcall_spot() -> None:
    """测试 open 后已有 caller 的 overcall 场景不会命中 shared adapter。"""
    strategy = PreflopStrategy(name="Test", source_dir="/tmp")
    strategy.add_node(
        100,
        StrategyNode(
            history_full="R2-F-F",
            history_actions="R-F-F",
            history_token_count=3,
            acting_position="BTN",
            source_file="test.json",
            actions=(
                StrategyAction(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    is_all_in=False,
                    total_frequency=0.4,
                    next_position="",
                    range=_range_with_single_hand_probability("AKs", 0.0),
                ),
                StrategyAction(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    is_all_in=False,
                    total_frequency=0.6,
                    next_position="",
                    range=_range_with_single_hand_probability("AKs", 1.0),
                ),
            ),
        ),
    )

    handler = create_preflop_strategy(strategy=strategy)
    observed_state = _create_observed_state_for_test(
        hero_seat=0,  # BTN
        btn_seat=0,
        stack_bb=100.0,
        hero_cards=("As", "Ks"),
        action_history=[
            (3, ActionType.RAISE, 2.0),  # UTG open
            (4, ActionType.CALL, 2.0),  # MP cold call
            (5, ActionType.FOLD, 0.0),  # CO fold
        ],
    )

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
            },
        )
    )

    assert "preflopStrategy[shared]" not in result["notes"]


def test_preflop_strategy_skips_shared_adapter_outside_preflop() -> None:
    """测试翻后状态不会误命中 shared preflop adapter。"""
    strategy = PreflopStrategy(name="Test", source_dir="/tmp")
    strategy.add_node(
        100,
        StrategyNode(
            history_full="R2-C",
            history_actions="R-C",
            history_token_count=2,
            acting_position="CO",
            source_file="test.json",
            actions=(
                StrategyAction(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    is_all_in=False,
                    total_frequency=0.4,
                    next_position="",
                    range=_range_with_single_hand_probability("AKs", 0.0),
                ),
                StrategyAction(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    is_all_in=False,
                    total_frequency=0.6,
                    next_position="",
                    range=_range_with_single_hand_probability("AKs", 1.0),
                ),
            ),
        ),
    )

    handler = create_preflop_strategy(strategy=strategy)
    observed_state = _create_observed_state_for_test(
        hero_seat=5,  # CO
        btn_seat=0,
        stack_bb=100.0,
        hero_cards=("As", "Ks"),
        action_history=[
            (3, ActionType.RAISE, 2.0),  # UTG open 2bb
            (4, ActionType.CALL, 2.0),  # MP call
        ],
    )
    observed_state.street = Street.FLOP
    observed_state.record_action(0, ActionType.CALL, 0.0)

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
            },
        )
    )

    assert "preflopStrategy[shared]" not in result["notes"]
    assert "未找到策略节点" in result["notes"]


def test_preflop_strategy_adjusts_iso_raise_size_by_num_limpers() -> None:
    """测试 ISO 加注尺度根据 limper 数量调整。"""
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

    # 创建观察者状态（有 1 个 limper，即 history = "C"）
    # btn_seat=5，hero_seat=4 (MP)
    # UTG (seat 2) 做了 CALL
    observed_state = _create_observed_state_for_test(
        hero_seat=4,  # MP
        btn_seat=5,
        stack_bb=100.0,
        hero_cards=("As", "Ks"),
        action_history=[
            (2, ActionType.CALL, 1.0),  # UTG call (limp)
        ],
    )

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
            },
        )
    )

    assert result["recommended_action"] == "R3"
    # 有 1 个 limper 应该 +1bb = 4.0
    assert result["recommended_amount"] == 4.0


def test_preflop_strategy_adjusts_sb_open_frequency_by_bb_stats() -> None:
    """测试 SB open 根据 BB 统计调整频率。"""
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

    # 创建观察者状态（SB 位置，无 history）
    # btn_seat=0，hero_seat=1 (SB)
    observed_state = _create_observed_state_for_test(
        hero_seat=1,  # SB
        btn_seat=0,
        stack_bb=100.0,
        hero_cards=("As", "Ks"),
    )

    # 更新玩家列表添加 BB 信息
    observed_state.players = [
        Player(
            seat_index=0,
            player_id="BTN",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=True,
            vpip=0,
        ),
        Player(
            seat_index=1,
            player_id="Hero",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=True,
            is_button=False,
            vpip=0,
        ),
        Player(
            seat_index=2,
            player_id="BB",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=False,
            vpip=0,
        ),
        Player(
            seat_index=3,
            player_id="",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=False,
            vpip=0,
        ),
        Player(
            seat_index=4,
            player_id="",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=False,
            vpip=0,
        ),
        Player(
            seat_index=5,
            player_id="",
            stack=100.0,
            bet=0.0,
            position=None,
            is_folded=False,
            is_thinking=False,
            is_button=False,
            vpip=0,
        ),
    ]

    result = asyncio.run(
        handler(
            "s1",
            {
                "state_version": 1,
                "observed_state": observed_state,
                "btn_seat": 0,
                "players": observed_state.players,
            },
        )
    )

    assert result["recommended_action"] == "R2"
