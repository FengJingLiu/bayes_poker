"""strategy_engine v2 的中性核心类型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bayes_poker.domain.poker import ActionType
from bayes_poker.domain.table import Position
from bayes_poker.player_metrics.params import PreFlopParams


class ActionFamily(str, Enum):
    """支持的翻前行动族。"""

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
    """中性化后的已观察动作。"""

    position: Position
    action_type: ActionType
    raise_size_bb: float | None = None


@dataclass(frozen=True, slots=True)
class NodeContext:
    """用于 mapper/GTO 节点查找的中性上下文。"""

    actor_position: Position
    aggressor_position: Position | None
    call_count: int
    limp_count: int
    raise_time: int
    pot_size: float
    raise_size_bb: float | None = None


@dataclass(frozen=True, slots=True)
class PlayerNodeContext:
    """当前 actor 的统一节点上下文。"""

    actor_seat: int
    actor_position: Position
    node_context: NodeContext
    params: PreFlopParams
    action_order: tuple[int, ...]
