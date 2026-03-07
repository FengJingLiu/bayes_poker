"""翻前共享状态模型测试。"""

from __future__ import annotations

from bayes_poker.domain.poker import ActionType
from bayes_poker.strategy.preflop_engine import (
    ActionFamily,
    ObservedAction,
    build_preflop_decision_state,
)
from bayes_poker.table.layout.base import Position as TablePosition


def test_build_preflop_decision_state_for_open_plus_cold_call() -> None:
    """测试 open 后跟 cold call 时的决策状态构建。"""
    state = build_preflop_decision_state(
        actor_position=TablePosition.CO,
        actions=(
            ObservedAction(
                position=TablePosition.UTG,
                action_type=ActionType.RAISE,
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
