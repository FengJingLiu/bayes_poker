"""翻前策略 sqlite 导入记录模型。"""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.domain.action_family import ActionFamily
from bayes_poker.domain.table import Position
from bayes_poker.strategy.range import PreflopRange


@dataclass(frozen=True, slots=True)
class ParsedStrategyActionRecord:
    """单个策略动作的导入记录。

    Attributes:
        order_index: 动作在节点中的顺序索引。
        action_code: 原始动作代码。
        action_type: 原始动作类型。
        bet_size_bb: 动作尺度，单位为 BB。
        is_all_in: 是否全下。
        total_frequency: 当前动作总体频率。
        next_position: 下一个行动位置。
        preflop_range: 当前动作的 169 维策略与 EV 向量。
        total_ev: 当前动作总 EV。
        total_combos: 当前动作总组合数。
    """

    order_index: int
    action_code: str
    action_type: str
    bet_size_bb: float | None
    is_all_in: bool
    total_frequency: float
    next_position: str
    preflop_range: PreflopRange
    total_ev: float
    total_combos: float


@dataclass(frozen=True, slots=True)
class ParsedStrategyNodeRecord:
    """单个策略节点的导入记录。

    Attributes:
        stack_bb: 当前节点所属有效筹码深度。
        history_full: 节点完整历史。
        history_actions: 去量后的标准化历史。
        history_token_count: 历史 token 数量。
        acting_position: 原始 acting position 字符串。
        source_file: 来源 JSON 文件名。
        action_family: 供 mapper 使用的动作族。
        actor_position: 当前待行动位置。
        aggressor_position: 最后一次激进行动位置。
        call_count: 最后一次激进行动后的跟注人数。
        limp_count: 首个激进行动前的 limp 人数。
        raise_time: 当前节点前出现的加注次数。
        pot_size: 当前节点前的底池大小（单位 BB）。
        raise_size_bb: 最后一次激进行动尺度。
        is_in_position: 当前待行动方相对 aggressor 是否有位置优势。
    """

    stack_bb: int
    history_full: str
    history_actions: str
    history_token_count: int
    acting_position: str
    source_file: str
    action_family: ActionFamily | None
    actor_position: Position | None
    aggressor_position: Position | None
    call_count: int
    limp_count: int
    raise_time: int
    pot_size: float
    raise_size_bb: float | None
    is_in_position: bool | None
