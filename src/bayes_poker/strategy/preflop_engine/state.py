"""翻前共享状态模型."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from bayes_poker.domain.poker import ActionType
from bayes_poker.domain.table import Position


class ActionFamily(str, Enum):
    """翻前决策动作族."""

    FOLD = "fold"
    OPEN = "open"
    CALL_VS_OPEN = "call_vs_open"
    CALL_VS_3BET = "call_vs_3bet"
    LIMP = "limp"
    OVERLIMP = "overlimp"
    ISO_RAISE = "iso_raise"
    THREE_BET = "three_bet"
    SQUEEZE = "squeeze"
    FOUR_BET = "four_bet"
    JAM = "jam"


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
        aggressor_position: 最后一次激进行动玩家位置.
        call_count: 最后一次激进行动后的跟注人数.
        limp_count: 首个激进行动前的 limp 人数.
        raise_time: 当前节点前出现的加注次数.
        pot_size: 当前节点前底池大小, 单位 BB.
        raise_size_bb: 最后一次激进行动的总尺度, 单位 BB.
    """

    action_family: ActionFamily
    actor_position: Position
    aggressor_position: Position | None
    call_count: int
    limp_count: int
    raise_time: int
    pot_size: float
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
    raise_time = 0
    pot_size = 1.5
    current_to_call_bb = 1.0
    contribution_by_position: dict[Position, float] = {
        Position.SB: 0.5,
        Position.BB: 1.0,
    }
    raise_size_bb: float | None = None

    for action in actions:
        if action.action_type == ActionType.CALL:
            current_contribution_bb = contribution_by_position.get(action.position, 0.0)
            call_delta_bb = max(current_to_call_bb - current_contribution_bb, 0.0)
            contribution_by_position[action.position] = (
                current_contribution_bb + call_delta_bb
            )
            pot_size += call_delta_bb
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
            raise_to_bb = action.raise_size_bb
            if raise_to_bb is None:
                raise ValueError("激进行动缺少 raise_size_bb.")
            current_contribution_bb = contribution_by_position.get(action.position, 0.0)
            raise_delta_bb = max(raise_to_bb - current_contribution_bb, 0.0)
            contribution_by_position[action.position] = (
                current_contribution_bb + raise_delta_bb
            )
            pot_size += raise_delta_bb
            current_to_call_bb = max(current_to_call_bb, raise_to_bb)
            raise_time += 1
            aggressor_position = action.position
            raise_size_bb = raise_to_bb
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
            raise_time=0,
            pot_size=pot_size,
            raise_size_bb=None,
        )

    return PreflopDecisionState(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_time=raise_time,
        pot_size=pot_size,
        raise_size_bb=raise_size_bb,
    )


__all__ = [
    "ActionFamily",
    "ObservedAction",
    "PreflopDecisionState",
    "build_preflop_decision_state",
]
