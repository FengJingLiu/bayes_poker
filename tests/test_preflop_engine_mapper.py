"""翻前 solver 节点映射与先验读取测试."""

from __future__ import annotations

import pytest

import bayes_poker.strategy.preflop_engine.mapper as mapper_module
from bayes_poker.strategy.preflop_engine.mapper import (
    MappedSolverContext,
    PreflopNodeMapper,
)
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
                    total_frequency=0.10,
                ),
                _make_action(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    total_frequency=0.80,
                ),
                _make_action(
                    order_index=2,
                    action_code="R9.5",
                    action_type="RAISE",
                    bet_size_bb=9.5,
                    total_frequency=0.10,
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
                    total_frequency=0.90,
                ),
                _make_action(
                    order_index=1,
                    action_code="R9.5",
                    action_type="RAISE",
                    bet_size_bb=9.5,
                    total_frequency=0.10,
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


def _build_open_only_strategy() -> PreflopStrategy:
    """构造只包含 open 候选的测试策略.

    Returns:
        不含 `CALL_VS_OPEN` 节点的测试策略.
    """

    strategy = PreflopStrategy(name="OpenOnlyStrategy", source_dir="/tmp")
    strategy.add_node(
        100,
        _make_node(
            history_full="F-F",
            history_actions="F-F",
            acting_position=TablePosition.CO,
            actions=(
                _make_action(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    total_frequency=0.20,
                ),
                _make_action(
                    order_index=1,
                    action_code="R2.5",
                    action_type="RAISE",
                    bet_size_bb=2.5,
                    total_frequency=0.80,
                ),
            ),
        ),
    )
    return strategy


def _build_limp_strategy() -> PreflopStrategy:
    """构造包含 limp family 候选的测试策略.

    Returns:
        至少包含一个可映射 limp 节点的测试策略.
    """

    strategy = PreflopStrategy(name="LimpStrategy", source_dir="/tmp")
    strategy.add_node(
        100,
        _make_node(
            history_full="F-C",
            history_actions="F-C",
            acting_position=TablePosition.CO,
            actions=(
                _make_action(
                    order_index=0,
                    action_code="F",
                    action_type="FOLD",
                    bet_size_bb=None,
                    total_frequency=0.20,
                ),
                _make_action(
                    order_index=1,
                    action_code="C",
                    action_type="CALL",
                    bet_size_bb=None,
                    total_frequency=0.50,
                ),
                _make_action(
                    order_index=2,
                    action_code="R4",
                    action_type="RAISE",
                    bet_size_bb=4.0,
                    total_frequency=0.30,
                ),
            ),
        ),
    )
    return strategy


def _build_state(*, raise_size_bb: float = 2.0) -> PreflopDecisionState:
    """构造 cold call vs open 的测试状态.

    Args:
        raise_size_bb: open 尺度.

    Returns:
        供映射器使用的共享决策状态.
    """

    return PreflopDecisionState(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=TablePosition.CO,
        aggressor_position=TablePosition.UTG,
        call_count=1,
        limp_count=0,
        raise_size_bb=raise_size_bb,
    )


def _build_limp_state() -> PreflopDecisionState:
    """构造 limp family 的测试状态.

    Returns:
        供 mapper synthetic fallback 使用的共享决策状态.
    """

    return PreflopDecisionState(
        action_family=ActionFamily.LIMP,
        actor_position=TablePosition.CO,
        aggressor_position=None,
        call_count=0,
        limp_count=1,
        raise_size_bb=None,
    )


def _limp_template_kind() -> object:
    """读取 limp family 对应的结构化模板枚举值.

    Returns:
        `SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3` 对应的枚举值.
    """

    return mapper_module.SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3


def _get_blended_frequency(policy: object, action_name: str) -> float:
    """读取指定动作的聚合频率.

    Args:
        policy: 聚合后的先验策略对象.
        action_name: 动作名称.

    Returns:
        对应动作的聚合频率.

    Raises:
        AssertionError: 当目标动作不存在时抛出.
    """

    for action in policy.actions:
        if action.action_name == action_name:
            return action.blended_frequency
    raise AssertionError(f"未找到动作: {action_name}")


def test_mapper_prefers_same_family_and_ip_structure() -> None:
    """测试映射器优先选择同动作族且位置结构一致的近邻节点."""

    mapper = PreflopNodeMapper(strategy=_build_strategy(), stack_bb=100)

    context = mapper.map_state(_build_state())

    assert context.matched_level == 2
    assert context.matched_history == "R2-C"
    assert context.candidate_histories == ("R2-C", "R2.5-C")
    assert context.candidate_distances[0] < context.candidate_distances[1]


def test_mapper_prefers_closer_raise_size_within_same_family() -> None:
    """测试同动作族节点会优先匹配尺度更接近的候选."""

    mapper = PreflopNodeMapper(strategy=_build_strategy(), stack_bb=100)

    context = mapper.map_state(_build_state(raise_size_bb=2.45))

    assert context.matched_history == "R2.5-C"
    assert context.candidate_histories == ("R2.5-C", "R2-C")
    assert context.candidate_distances[0] < context.candidate_distances[1]


def test_mapper_applies_price_adjustment_for_larger_open_size() -> None:
    """测试更大的真实 open 尺度会触发最小价格修正标记."""

    mapper = PreflopNodeMapper(strategy=_build_strategy(), stack_bb=100)

    context = mapper.map_state(_build_state(raise_size_bb=3.0))

    assert context.matched_history == "R2.5-C"
    assert context.price_adjustment_applied is True
    assert context.price_adjustment_factor < 1.0


def test_mapper_raises_when_no_same_family_candidate_exists() -> None:
    """测试没有同动作族候选时映射器会拒绝映射."""

    mapper = PreflopNodeMapper(strategy=_build_open_only_strategy(), stack_bb=100)

    with pytest.raises(ValueError, match="同动作族"):
        mapper.map_state(_build_state())


def test_mapper_falls_back_to_synthetic_template_for_limp_family() -> None:
    """测试 limp family 在无同族 solver 节点时回退到 synthetic template."""

    mapper = PreflopNodeMapper(strategy=_build_open_only_strategy(), stack_bb=100)

    context = mapper.map_state(_build_limp_state())

    assert context.matched_level == 3
    assert (
        context.synthetic_template_kind
        is _limp_template_kind()
    )
    assert context.candidate_histories == ()


def test_mapper_prefers_real_limp_candidate_before_synthetic_fallback() -> None:
    """测试存在 limp 同族节点时应命中真实节点而非 synthetic."""

    mapper = PreflopNodeMapper(strategy=_build_limp_strategy(), stack_bb=100)

    context = mapper.map_state(_build_limp_state())

    assert context.matched_level == 2
    assert context.matched_history == "F-C"
    assert context.synthetic_template_kind is None


def test_solver_prior_blends_multiple_candidates_by_distance() -> None:
    """测试 solver 先验读取会根据真实距离加权而非候选顺序加权."""

    strategy = _build_strategy()
    solver_prior = SolverPriorBuilder(strategy=strategy, stack_bb=100)
    context = MappedSolverContext(
        matched_level=2,
        matched_history="R2-C",
        distance_score=0.0,
        candidate_histories=("R2.5-C", "R2-C"),
        candidate_distances=(5.0, 0.0),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=None,
    )
    policy = solver_prior.build_policy(context)

    assert policy.action_names == ("F", "C", "R9.5")
    assert _get_blended_frequency(policy, "C") > _get_blended_frequency(policy, "F")


def test_solver_prior_preserves_frequencies_and_exposes_price_signal() -> None:
    """测试 solver 先验透传价格修正 signal, 但不直接改动作频率."""

    strategy = _build_strategy()
    solver_prior = SolverPriorBuilder(strategy=strategy, stack_bb=100)
    base_context = MappedSolverContext(
        matched_level=2,
        matched_history="R2.5-C",
        distance_score=0.0,
        candidate_histories=("R2.5-C",),
        candidate_distances=(0.0,),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=None,
    )
    adjusted_context = MappedSolverContext(
        matched_level=2,
        matched_history="R2.5-C",
        distance_score=0.0,
        candidate_histories=("R2.5-C",),
        candidate_distances=(0.0,),
        price_adjustment_applied=True,
        price_adjustment_factor=0.75,
        synthetic_template_kind=None,
    )

    base_policy = solver_prior.build_policy(base_context)
    adjusted_policy = solver_prior.build_policy(adjusted_context)

    assert adjusted_policy.price_adjustment_applied is True
    assert adjusted_policy.price_adjustment_factor == pytest.approx(0.75)
    assert _get_blended_frequency(adjusted_policy, "R9.5") == pytest.approx(
        _get_blended_frequency(base_policy, "R9.5"),
    )
    assert _get_blended_frequency(adjusted_policy, "F") == pytest.approx(
        _get_blended_frequency(base_policy, "F"),
    )


def test_solver_prior_uses_synthetic_template_policy() -> None:
    """测试存在结构化 synthetic template 时直接返回模板先验策略."""

    solver_prior = SolverPriorBuilder(
        strategy=_build_open_only_strategy(),
        stack_bb=100,
    )
    context = MappedSolverContext(
        matched_level=3,
        matched_history="",
        distance_score=0.0,
        candidate_histories=(),
        candidate_distances=(),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=_limp_template_kind(),
    )

    policy = solver_prior.build_policy(context)

    assert policy.action_names == ("F", "C", "R4")
    assert policy.synthetic_template_kind is _limp_template_kind()
    assert _get_blended_frequency(policy, "C") == pytest.approx(0.5)
