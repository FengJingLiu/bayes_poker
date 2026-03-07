"""翻前 solver 节点映射与先验读取测试."""

from __future__ import annotations

from bayes_poker.strategy.preflop_engine.mapper import PreflopNodeMapper
from bayes_poker.strategy.preflop_engine.solver_prior import SolverPriorBuilder
from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    PreflopDecisionState,
)
from bayes_poker.strategy.preflop_parse.models import (
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.table.layout.base import Position as TablePosition


def _make_action(
    *,
    order_index: int,
    action_code: str,
    action_type: str,
    bet_size_bb: float | None,
    total_frequency: float,
) -> StrategyAction:
    """构造测试用策略动作.

    Args:
        order_index: 动作序号.
        action_code: 动作编码.
        action_type: 动作类型.
        bet_size_bb: 动作尺度.
        total_frequency: 总体频率.

    Returns:
        最小可用的策略动作对象.
    """

    return StrategyAction(
        order_index=order_index,
        action_code=action_code,
        action_type=action_type,
        bet_size_bb=bet_size_bb,
        is_all_in=False,
        total_frequency=total_frequency,
        next_position="",
        range=PreflopRange.zeros(),
    )


def _make_node(
    *,
    history_full: str,
    history_actions: str,
    acting_position: TablePosition,
    actions: tuple[StrategyAction, ...],
) -> StrategyNode:
    """构造测试用策略节点.

    Args:
        history_full: 完整历史.
        history_actions: 归一化历史.
        acting_position: 当前行动位置.
        actions: 节点动作列表.

    Returns:
        最小可用的策略节点对象.
    """

    return StrategyNode(
        history_full=history_full,
        history_actions=history_actions,
        history_token_count=len([token for token in history_full.split("-") if token]),
        acting_position=acting_position.value,
        source_file="test.json",
        actions=actions,
    )


def _build_strategy() -> PreflopStrategy:
    """构造用于映射与先验读取的测试策略.

    Returns:
        包含多个近邻节点的测试策略.
    """

    strategy = PreflopStrategy(name="TestStrategy", source_dir="/tmp")

    strategy.add_node(
        100,
        _make_node(
            history_full="R2-C",
            history_actions="R-C",
            acting_position=TablePosition.CO,
            actions=(
                _make_action(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    total_frequency=0.30,
                ),
                _make_action(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    total_frequency=0.25,
                ),
                _make_action(
                    order_index=2,
                    action_code="R9.5",
                    action_type="RAISE",
                    bet_size_bb=9.5,
                    total_frequency=0.45,
                ),
            ),
        ),
    )
    strategy.add_node(
        100,
        _make_node(
            history_full="R2.5-C",
            history_actions="R-C",
            acting_position=TablePosition.CO,
            actions=(
                _make_action(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    total_frequency=0.35,
                ),
                _make_action(
                    order_index=1,
                    action_code="R9.5",
                    action_type="RAISE",
                    bet_size_bb=9.5,
                    total_frequency=0.65,
                ),
            ),
        ),
    )
    strategy.add_node(
        100,
        _make_node(
            history_full="F-F-F-R2",
            history_actions="F-F-F-R",
            acting_position=TablePosition.SB,
            actions=(
                _make_action(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    total_frequency=0.40,
                ),
                _make_action(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    total_frequency=0.60,
                ),
            ),
        ),
    )

    return strategy


def _build_state() -> PreflopDecisionState:
    """构造 cold call vs open 的测试状态.

    Returns:
        供映射器使用的共享决策状态.
    """

    return PreflopDecisionState(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=TablePosition.CO,
        aggressor_position=TablePosition.UTG,
        call_count=1,
        limp_count=0,
    )


def test_mapper_prefers_same_family_and_ip_structure() -> None:
    """测试映射器优先选择同动作族且位置结构一致的近邻节点."""

    mapper = PreflopNodeMapper(strategy=_build_strategy(), stack_bb=100)

    context = mapper.map_state(_build_state())

    assert context.matched_level == 2
    assert context.matched_history == "R2-C"
    assert context.candidate_histories == ("R2-C", "R2.5-C")


def test_solver_prior_blends_multiple_candidates_by_distance() -> None:
    """测试 solver 先验读取会合并多个近邻候选的动作集合."""

    strategy = _build_strategy()
    mapper = PreflopNodeMapper(strategy=strategy, stack_bb=100)
    solver_prior = SolverPriorBuilder(strategy=strategy, stack_bb=100)

    context = mapper.map_state(_build_state())
    policy = solver_prior.build_policy(context)

    assert policy.action_names == ("F", "C", "R9.5")
