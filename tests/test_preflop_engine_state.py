"""翻前共享状态模型测试."""

from __future__ import annotations

import pytest

from bayes_poker.domain.poker import ActionType
from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    ObservedAction,
    build_preflop_decision_state,
)
from bayes_poker.domain.table import Position as TablePosition


def test_build_preflop_decision_state_for_open_plus_cold_call() -> None:
    """测试 open 后跟 cold call 时的决策状态构建."""
    state = build_preflop_decision_state(
        actor_position=TablePosition.CO,
        actions=(
            ObservedAction(
                position=TablePosition.UTG,
                action_type=ActionType.RAISE,
                raise_size_bb=2.5,
            ),
            ObservedAction(
                position=TablePosition.MP,
                action_type=ActionType.CALL,
            ),
        ),
    )

    assert state.action_family == ActionFamily.CALL_VS_OPEN
    assert state.call_count == 1
    assert state.aggressor_position == TablePosition.UTG
    assert state.raise_size_bb == 2.5


def test_build_preflop_decision_state_for_first_in_open() -> None:
    """测试无人入池时返回 first-in open 状态."""
    state = build_preflop_decision_state(
        actor_position=TablePosition.UTG,
        actions=(),
    )

    assert state.action_family == ActionFamily.OPEN
    assert state.aggressor_position is None
    assert state.call_count == 0
    assert state.limp_count == 0
    assert state.raise_size_bb is None


def test_build_preflop_decision_state_rejects_limp() -> None:
    """测试单个 limp 场景会被当前最小实现拒绝."""
    with pytest.raises(ValueError, match="limp"):
        build_preflop_decision_state(
            actor_position=TablePosition.CO,
            actions=(
                ObservedAction(
                    position=TablePosition.UTG,
                    action_type=ActionType.CALL,
                ),
            ),
        )


def test_build_preflop_decision_state_rejects_limp_then_raise() -> None:
    """测试 limp 后再 raise 场景会被当前最小实现拒绝."""
    with pytest.raises(ValueError, match="limp"):
        build_preflop_decision_state(
            actor_position=TablePosition.CO,
            actions=(
                ObservedAction(
                    position=TablePosition.UTG,
                    action_type=ActionType.CALL,
                ),
                ObservedAction(
                    position=TablePosition.MP,
                    action_type=ActionType.RAISE,
                ),
            ),
        )


def test_build_preflop_decision_state_rejects_multiple_raises() -> None:
    """测试多次加注场景会被当前最小实现拒绝."""
    with pytest.raises(ValueError, match="多次加注"):
        build_preflop_decision_state(
            actor_position=TablePosition.BTN,
            actions=(
                ObservedAction(
                    position=TablePosition.UTG,
                    action_type=ActionType.RAISE,
                ),
                ObservedAction(
                    position=TablePosition.MP,
                    action_type=ActionType.RAISE,
                ),
            ),
        )
