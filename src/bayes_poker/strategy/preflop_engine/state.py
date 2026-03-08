"""翻前共享状态模型."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from bayes_poker.domain.poker import ActionType
from bayes_poker.domain.table import Position


class ActionFamily(str, Enum):
    """翻前决策动作族."""

    OPEN = "open"
    CALL_VS_OPEN = "call_vs_open"
    LIMP = "limp"


@dataclass(frozen=True, slots=True)
class ObservedAction:
    """真实翻前动作事实.

    Attributes:
        position: 动作者位置.
        action_type: 动作类型.
        raise_size_bb: 动作总尺度, 单位 BB. 非激进行动为 None.
    """

    position: Position
    action_type: ActionType
    raise_size_bb: float | None = None


@dataclass(frozen=True, slots=True)
class PreflopDecisionState:
    """翻前决策共享状态.

    Attributes:
        action_family: 当前决策所属的动作族.
        actor_position: 当前待行动玩家位置.
        aggressor_position: 首个激进行动玩家位置.
        call_count: 首个激进行动后的跟注人数.
        limp_count: 首个激进行动前的 limp 人数.
        raise_size_bb: 首个激进行动的总尺度, 单位 BB.
    """

    action_family: ActionFamily
    actor_position: Position
    aggressor_position: Position | None
    call_count: int
    limp_count: int
    raise_size_bb: float | None = None


def _is_aggressive_action(action_type: ActionType) -> bool:
    """判断是否为激进行动.

    Args:
        action_type: 动作类型.

    Returns:
        是否为下注, 加注或全下.
    """

    return action_type in (
        ActionType.BET,
        ActionType.RAISE,
        ActionType.ALL_IN,
    )


def build_preflop_decision_state(
    *,
    actor_position: Position,
    actions: Sequence[ObservedAction],
) -> PreflopDecisionState:
    """根据翻前动作前缀构建共享决策状态.

    当前最小实现只覆盖两类状态:
    1. 无人入池时的 first-in open.
    2. 无 limp 的单次 open 后继续决策, 并统计 cold call 数量.

    Args:
        actor_position: 当前待行动玩家位置.
        actions: 当前玩家行动前的翻前动作序列.

    Returns:
        构建得到的翻前决策状态.

    Raises:
        ValueError: 当动作序列属于当前最小实现未覆盖的场景时抛出.
    """

    aggressor_position: Position | None = None
    call_count = 0
    limp_count = 0
    raise_size_bb: float | None = None

    for action in actions:
        if action.action_type == ActionType.CALL:
            if aggressor_position is None:
                limp_count += 1
            else:
                call_count += 1
            continue

        if action.action_type in (ActionType.FOLD, ActionType.CHECK):
            continue

        if _is_aggressive_action(action.action_type):
            if limp_count > 0:
                raise ValueError("当前最小实现暂不支持 limp 场景.")
            if aggressor_position is not None:
                raise ValueError("当前最小实现暂不支持多次加注场景.")
            aggressor_position = action.position
            raise_size_bb = action.raise_size_bb
            continue

        raise ValueError(f"不支持的动作类型: {action.action_type}")

    if aggressor_position is None:
        if limp_count > 0:
            raise ValueError("当前最小实现暂不支持 limp 场景.")
        return PreflopDecisionState(
            action_family=ActionFamily.OPEN,
            actor_position=actor_position,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_size_bb=None,
        )

    return PreflopDecisionState(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_size_bb=raise_size_bb,
    )


__all__ = [
    "ActionFamily",
    "ObservedAction",
    "PreflopDecisionState",
    "build_preflop_decision_state",
]
