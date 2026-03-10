"""strategy_engine v2 的统一 context builder。"""

from __future__ import annotations

from bayes_poker.comm.strategy_history import build_preflop_history
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import (
    Player,
    PlayerAction,
    Position,
    get_position_by_seat,
)
from bayes_poker.player_metrics.enums import (
    ActionType as MetricsActionType,
    Position as MetricsPosition,
    TableType,
)
from bayes_poker.player_metrics.params import PreFlopParams
from .core_types import (
    ActionFamily,
    NodeContext,
    PlayerNodeContext,
)
from bayes_poker.table.observed_state import ObservedTableState


class UnsupportedContextError(ValueError):
    """表示当前观察状态无法构建 v1 context。"""


def _get_player_by_seat(
    observed_state: ObservedTableState, seat_index: int
) -> Player | None:
    for player in observed_state.players:
        if player.seat_index == seat_index:
            return player
    return None


def _resolve_actor_position(
    observed_state: ObservedTableState, actor_seat: int
) -> Position:
    player = _get_player_by_seat(observed_state, actor_seat)
    if player is None:
        raise UnsupportedContextError("找不到 actor 对应的玩家信息")
    try:
        position = get_position_by_seat(
            actor_seat, observed_state.btn_seat, observed_state.player_count
        )
        if position is None:
            if player.position is None:
                raise UnsupportedContextError("无法解析 actor 的位置")
            return player.position
        return position
    except ValueError:
        if player.position is None:
            raise UnsupportedContextError("无法解析 actor 的位置")
        return player.position


def _map_table_position_to_metrics(position: Position) -> MetricsPosition | None:
    mapping = {
        Position.SB: MetricsPosition.SMALL_BLIND,
        Position.BB: MetricsPosition.BIG_BLIND,
        Position.UTG: MetricsPosition.UTG,
        Position.MP: MetricsPosition.HJ,
        Position.HJ: MetricsPosition.HJ,
        Position.CO: MetricsPosition.CO,
        Position.BTN: MetricsPosition.BUTTON,
    }
    return mapping.get(position)


def _is_in_position_on_flop(position: Position, player_count: int) -> bool:
    if player_count == 2:
        return position == Position.SB
    return position == Position.BTN


def _filter_preflop_actions(action_history: list[PlayerAction]) -> list[PlayerAction]:
    return [action for action in action_history if action.street == Street.PREFLOP]


def _build_first_action_prefix(
    preflop_actions: list[PlayerAction],
    actor_seat: int,
) -> list[PlayerAction]:
    prefix: list[PlayerAction] = []
    for action in preflop_actions:
        if action.player_index == actor_seat:
            raise UnsupportedContextError("当前最小实现只支持 actor 的首次翻前行动")
        prefix.append(action)
    return prefix


def _classify_action_family(
    prefix_actions: list[PlayerAction], big_blind: float
) -> NodeContext:
    aggressive_actions = [
        action
        for action in prefix_actions
        if action.action_type in {ActionType.BET, ActionType.RAISE, ActionType.ALL_IN}
    ]
    if len(aggressive_actions) >= 2:
        raise UnsupportedContextError("当前最小实现暂不支持多次加注场景")

    limp_count = 0
    for action in prefix_actions:
        if (
            action.action_type in {ActionType.CHECK, ActionType.CALL}
            and not aggressive_actions
        ):
            limp_count += 1

    if not aggressive_actions:
        if limp_count == 0:
            return NodeContext(
                action_family=ActionFamily.OPEN,
                actor_position=Position.UTG,
                aggressor_position=None,
                call_count=0,
                limp_count=0,
                raise_size_bb=None,
            )
        return NodeContext(
            action_family=ActionFamily.LIMP,
            actor_position=Position.UTG,
            aggressor_position=None,
            call_count=0,
            limp_count=limp_count,
            raise_size_bb=None,
        )

    first_raise = aggressive_actions[0]
    raise_index = prefix_actions.index(first_raise)
    call_count = sum(
        1
        for action in prefix_actions[raise_index + 1 :]
        if action.action_type in {ActionType.CHECK, ActionType.CALL}
    )
    if limp_count > 0:
        raise UnsupportedContextError("当前最小实现暂不支持 limp 后加注场景")
    return NodeContext(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=Position.UTG,
        aggressor_position=Position.UTG,
        call_count=call_count,
        limp_count=0,
        raise_size_bb=first_raise.amount / big_blind if big_blind > 0 else None,
    )


def build_player_node_context(
    observed_state: ObservedTableState,
    *,
    table_type: TableType = TableType.SIX_MAX,
) -> PlayerNodeContext:
    """从观察状态构建当前 actor 的统一节点上下文。

    Args:
        observed_state: 当前牌桌观察状态。
        table_type: 目标玩家统计表类型。

    Returns:
        当前 actor 的统一节点上下文。

    Raises:
        UnsupportedContextError: 当场景超出 v1 支持矩阵时抛出。
    """

    if observed_state.actor_seat is None:
        raise UnsupportedContextError("当前观察状态缺少 actor_seat")
    if observed_state.street != Street.PREFLOP:
        raise UnsupportedContextError("当前最小实现只支持 preflop")
    if (
        observed_state.player_count != int(table_type)
        or table_type != TableType.SIX_MAX
    ):
        raise UnsupportedContextError("当前最小实现只支持 6-max")

    actor_seat = observed_state.actor_seat
    actor_position = _resolve_actor_position(observed_state, actor_seat)
    metrics_position = _map_table_position_to_metrics(actor_position)
    if metrics_position is None:
        raise UnsupportedContextError("当前 actor 位置无法映射到 player metrics")

    preflop_actions = _filter_preflop_actions(observed_state.action_history)
    prefix_actions = _build_first_action_prefix(preflop_actions, actor_seat)
    action_order = tuple(action.player_index for action in prefix_actions)
    query_history = build_preflop_history(
        prefix_actions,
        big_blind=observed_state.big_blind,
    )

    base_node_context = _classify_action_family(
        prefix_actions, observed_state.big_blind
    )
    aggressor_position = None
    if base_node_context.action_family == ActionFamily.CALL_VS_OPEN:
        for action in prefix_actions:
            if action.action_type in {
                ActionType.BET,
                ActionType.RAISE,
                ActionType.ALL_IN,
            }:
                aggressor_position = _resolve_actor_position(
                    observed_state, action.player_index
                )
                break

    node_context = NodeContext(
        action_family=base_node_context.action_family,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=base_node_context.call_count,
        limp_count=base_node_context.limp_count,
        raise_size_bb=base_node_context.raise_size_bb,
    )

    num_callers = base_node_context.limp_count
    num_raises = 0
    if node_context.action_family == ActionFamily.CALL_VS_OPEN:
        num_callers = base_node_context.call_count
        num_raises = 1

    params = PreFlopParams(
        table_type=table_type,
        position=metrics_position,
        num_callers=min(num_callers, 1),
        num_raises=min(num_raises, 2),
        num_active_players=max(2, observed_state.player_count),
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=_is_in_position_on_flop(
            actor_position,
            observed_state.player_count,
        ),
    )
    return PlayerNodeContext(
        actor_seat=actor_seat,
        actor_position=actor_position,
        query_history=query_history,
        node_context=node_context,
        params=params,
        action_order=action_order,
    )
