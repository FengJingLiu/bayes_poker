"""对手翻前上下文构建工具。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bayes_poker.comm.strategy_history import build_preflop_history
from bayes_poker.domain.poker import ActionType as DomainActionType
from bayes_poker.domain.poker import Street
from bayes_poker.domain.table import (
    Player,
    PlayerAction,
    Position as TablePosition,
    get_position_by_seat,
)
from bayes_poker.player_metrics.enums import (
    ActionType as MetricsActionType,
    Position as MetricsPosition,
    TableType,
)
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.strategy.runtime.preflop_history import (
    PreflopScenario,
    classify_preflop_scenario,
)

if TYPE_CHECKING:
    from bayes_poker.table.observed_state import ObservedTableState


@dataclass(slots=True, frozen=True)
class OpponentPreflopContext:
    """对手翻前上下文。"""

    scenario: PreflopScenario
    query_history: str
    params: PreFlopParams | None


def _resolve_table_position(
    player: "Player",
    table_state: "ObservedTableState",
) -> TablePosition | None:
    """解析玩家位置枚举。

    Args:
        player: 玩家对象。
        table_state: 牌桌状态。

    Returns:
        位置枚举, 失败时返回 `None`。
    """
    if table_state.player_count == 2:
        offset = (player.seat_index - table_state.btn_seat) % 2
        return TablePosition.SB if offset == 0 else TablePosition.BB

    if table_state.player_count in (6, 9):
        try:
            return get_position_by_seat(
                player.seat_index,
                table_state.btn_seat,
                table_state.player_count,
            )
        except Exception:
            return player.position

    return player.position


def _map_table_position_to_metrics(position: TablePosition) -> MetricsPosition:
    """映射布局位置到统计位置枚举。

    Args:
        position: 布局位置枚举。

    Returns:
        统计模块位置枚举。
    """
    mapping = {
        TablePosition.SB: MetricsPosition.SMALL_BLIND,
        TablePosition.BB: MetricsPosition.BIG_BLIND,
        TablePosition.UTG: MetricsPosition.UTG,
        TablePosition.MP: MetricsPosition.HJ,
        TablePosition.HJ: MetricsPosition.HJ,
        TablePosition.CO: MetricsPosition.CO,
        TablePosition.BTN: MetricsPosition.BUTTON,
    }
    return mapping.get(position, MetricsPosition.EMPTY)


def _map_domain_action_to_metrics(action: DomainActionType) -> MetricsActionType:
    """映射领域动作到统计动作枚举。

    Args:
        action: 领域动作枚举。

    Returns:
        统计动作枚举。
    """
    mapping = {
        DomainActionType.FOLD: MetricsActionType.FOLD,
        DomainActionType.CHECK: MetricsActionType.CHECK,
        DomainActionType.CALL: MetricsActionType.CALL,
        DomainActionType.BET: MetricsActionType.BET,
        DomainActionType.RAISE: MetricsActionType.RAISE,
        DomainActionType.ALL_IN: MetricsActionType.ALL_IN,
    }
    return mapping[action]


def _is_in_position_on_flop(
    *,
    table_position: TablePosition,
    player_count: int,
) -> bool:
    """判断是否在翻后处于位置优势。

    Args:
        table_position: 玩家位置。
        player_count: 玩家人数。

    Returns:
        是否翻后在位置。
    """
    if player_count == 2:
        return table_position == TablePosition.SB
    return table_position == TablePosition.BTN


def _build_params_for_player_first_preflop_action(
    *,
    player: "Player",
    preflop_actions: Sequence["PlayerAction"],
    table_state: "ObservedTableState",
    table_type: TableType,
) -> PreFlopParams | None:
    """基于行动前缀构建玩家首次翻前动作参数。

    Args:
        player: 对手玩家。
        preflop_actions: 翻前动作序列。
        table_state: 牌桌状态。
        table_type: 桌型。

    Returns:
        构建得到的参数, 不可构建时返回 `None`。
    """
    table_position = _resolve_table_position(player, table_state)
    if table_position is None:
        return None
    metrics_position = _map_table_position_to_metrics(table_position)
    if metrics_position == MetricsPosition.EMPTY:
        return None

    num_raises = 0
    num_callers = 0
    previous_player_action = MetricsActionType.FOLD

    for action in preflop_actions:
        if action.player_index == player.seat_index:
            return PreFlopParams(
                table_type=table_type,
                position=metrics_position,
                num_callers=min(num_callers, 1),
                num_raises=min(num_raises, 2),
                num_active_players=max(2, int(table_state.player_count)),
                previous_action=previous_player_action,
                in_position_on_flop=_is_in_position_on_flop(
                    table_position=table_position,
                    player_count=table_state.player_count,
                ),
            )

        mapped_action = _map_domain_action_to_metrics(action.action_type)
        if mapped_action in (
            MetricsActionType.RAISE,
            MetricsActionType.BET,
            MetricsActionType.ALL_IN,
        ):
            num_raises += 1
            num_callers = 0
        elif mapped_action == MetricsActionType.CALL:
            num_callers += 1

    return None


def build_opponent_preflop_context(
    *,
    player: "Player",
    action_prefix: Sequence["PlayerAction"],
    table_state: "ObservedTableState",
    table_type: TableType,
) -> OpponentPreflopContext:
    """构建对手翻前上下文。

    Args:
        player: 对手玩家。
        action_prefix: 当前动作前缀。
        table_state: 当前牌桌状态。
        table_type: 桌型。

    Returns:
        对手翻前上下文。
    """
    preflop_actions = [
        action
        for action in action_prefix
        if action.street == Street.PREFLOP
    ]
    query_history = build_preflop_history(
        list(preflop_actions),
        big_blind=table_state.big_blind,
    )
    scenario = classify_preflop_scenario(query_history)
    params = _build_params_for_player_first_preflop_action(
        player=player,
        preflop_actions=preflop_actions,
        table_state=table_state,
        table_type=table_type,
    )
    return OpponentPreflopContext(
        scenario=scenario,
        query_history=query_history,
        params=params,
    )
