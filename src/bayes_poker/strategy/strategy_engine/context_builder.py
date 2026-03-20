"""strategy_engine v2 的统一 context builder。"""

from __future__ import annotations

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import (
    Player,
    PlayerAction,
    Position,
    get_position_by_seat,
)
from bayes_poker.player_metrics.enums import (
    ActionType as MetricsActionType,
)
from bayes_poker.player_metrics.enums import (
    Position as MetricsPosition,
)
from bayes_poker.player_metrics.enums import (
    TableType,
)
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.table.observed_state import ObservedTableState

from .core_types import (
    NodeContext,
    PlayerNodeContext,
)


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
    except ValueError as exc:
        if player.position is None:
            raise UnsupportedContextError("无法解析 actor 的位置") from exc
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


def _map_domain_action_to_metrics_action(
    action_type: ActionType | None,
) -> MetricsActionType:
    """把领域动作类型映射到 player_metrics 动作类型。

    Args:
        action_type: 领域层动作类型; `None` 表示此前尚未行动。

    Returns:
        player_metrics 使用的动作类型枚举。
    """

    mapping = {
        None: MetricsActionType.FOLD,
        ActionType.FOLD: MetricsActionType.FOLD,
        ActionType.CHECK: MetricsActionType.CHECK,
        ActionType.CALL: MetricsActionType.CALL,
        ActionType.BET: MetricsActionType.BET,
        ActionType.RAISE: MetricsActionType.RAISE,
        ActionType.ALL_IN: MetricsActionType.ALL_IN,
    }
    return mapping[action_type]


def _is_in_position_on_flop(
    *,
    actor_position: Position,
    aggressor_position: Position | None,
    player_count: int,
) -> bool:
    if aggressor_position is not None:
        if actor_position == aggressor_position:
            return False
        if {actor_position, aggressor_position} <= {Position.SB, Position.BB}:
            return actor_position == Position.SB and aggressor_position == Position.BB
        postflop_position_order: tuple[Position, ...] = (
            Position.SB,
            Position.BB,
            Position.UTG,
            Position.UTG1,
            Position.MP,
            Position.MP1,
            Position.HJ,
            Position.CO,
            Position.BTN,
        )
        return postflop_position_order.index(
            actor_position
        ) > postflop_position_order.index(aggressor_position)
    if player_count == 2:
        return actor_position == Position.SB
    return actor_position == Position.BTN


def _build_base_node_context(
    prefix_actions: list[PlayerAction],
    *,
    small_blind: float,
    big_blind: float,
) -> NodeContext:
    aggressive_indices = [
        index
        for index, action in enumerate(prefix_actions)
        if action.action_type in {ActionType.BET, ActionType.RAISE, ActionType.ALL_IN}
    ]

    raise_time = len(aggressive_indices)
    pot_size = _calculate_prefix_pot_size(
        prefix_actions=prefix_actions,
        small_blind=small_blind,
        big_blind=big_blind,
    )

    if not aggressive_indices:
        limp_count = sum(
            1
            for action in prefix_actions
            if action.action_type in {ActionType.CHECK, ActionType.CALL}
        )
        if limp_count == 0:
            return NodeContext(
                actor_position=Position.UTG,
                aggressor_position=None,
                call_count=0,
                limp_count=0,
                raise_time=0,
                pot_size=pot_size,
                raise_size_bb=None,
            )
        return NodeContext(
            actor_position=Position.UTG,
            aggressor_position=None,
            call_count=0,
            limp_count=limp_count,
            raise_time=0,
            pot_size=pot_size,
            raise_size_bb=None,
        )

    first_raise_index = aggressive_indices[0]
    last_raise_index = aggressive_indices[-1]
    last_raise = prefix_actions[last_raise_index]
    limp_count = sum(
        1
        for action in prefix_actions[:first_raise_index]
        if action.action_type in {ActionType.CHECK, ActionType.CALL}
    )
    call_count = sum(
        1
        for action in prefix_actions[last_raise_index + 1 :]
        if action.action_type in {ActionType.CHECK, ActionType.CALL}
    )
    if limp_count > 0:
        raise UnsupportedContextError("当前最小实现暂不支持 limp 后加注场景")
    return NodeContext(
        actor_position=Position.UTG,
        aggressor_position=None,
        call_count=call_count,
        limp_count=0,
        raise_time=raise_time,
        pot_size=pot_size,
        raise_size_bb=last_raise.amount / big_blind if big_blind > 0 else None,
    )


def _calculate_prefix_pot_size(
    *,
    prefix_actions: list[PlayerAction],
    small_blind: float,
    big_blind: float,
) -> float:
    """按动作前缀估算当前底池大小（单位 BB）。

    Args:
        prefix_actions: 当前 actor 行动前的翻前动作序列。
        small_blind: 小盲金额（BB 单位）。
        big_blind: 大盲金额（BB 单位）。

    Returns:
        当前动作前的底池大小。
    """

    pot_size = small_blind + big_blind
    current_to_call = big_blind
    contribution_by_seat: dict[int, float] = {}

    for action in prefix_actions:
        if action.action_type in {ActionType.FOLD, ActionType.CHECK}:
            continue

        target = current_to_call
        if action.action_type == ActionType.CALL:
            target = current_to_call
        elif action.action_type in {
            ActionType.BET,
            ActionType.RAISE,
            ActionType.ALL_IN,
        }:
            target = max(action.amount, current_to_call)
            current_to_call = target

        contributed = contribution_by_seat.get(action.player_index, 0.0)
        delta = max(target - contributed, 0.0)
        contribution_by_seat[action.player_index] = contributed + delta
        pot_size += delta

    return pot_size


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

    prefix_actions = list(observed_state.get_preflop_prefix_before_current_turn())
    action_order = tuple(action.player_index for action in prefix_actions)

    base_node_context = _build_base_node_context(
        prefix_actions,
        small_blind=observed_state.small_blind,
        big_blind=observed_state.big_blind,
    )
    aggressor_position = None
    if base_node_context.raise_time > 0 and base_node_context.limp_count == 0:
        for action in prefix_actions:
            if action.action_type in {
                ActionType.BET,
                ActionType.RAISE,
                ActionType.ALL_IN,
            }:
                aggressor_position = _resolve_actor_position(
                    observed_state, action.player_index
                )

    node_context = NodeContext(
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=base_node_context.call_count,
        limp_count=base_node_context.limp_count,
        raise_time=base_node_context.raise_time,
        pot_size=base_node_context.pot_size,
        raise_size_bb=base_node_context.raise_size_bb,
    )

    num_callers = base_node_context.limp_count
    num_raises = base_node_context.raise_time
    if node_context.aggressor_position is not None and base_node_context.raise_time > 0:
        num_callers = base_node_context.call_count
    previous_action = observed_state.get_preflop_previous_action_for_seat(actor_seat)
    active_player_count = observed_state.get_active_player_count_before_current_turn()

    params = PreFlopParams(
        table_type=table_type,
        position=metrics_position,
        num_callers=min(num_callers, 1),
        num_raises=min(num_raises, 2),
        num_active_players=max(2, active_player_count),
        previous_action=_map_domain_action_to_metrics_action(previous_action),
        in_position_on_flop=_is_in_position_on_flop(
            actor_position=actor_position,
            aggressor_position=node_context.aggressor_position,
            player_count=observed_state.player_count,
        ),
    )
    return PlayerNodeContext(
        actor_seat=actor_seat,
        actor_position=actor_position,
        node_context=node_context,
        params=params,
        action_order=action_order,
    )
