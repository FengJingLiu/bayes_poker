"""Range 模块。

提供统一的 Range 类用于表示 preflop（169维）和 postflop（1326维）策略向量。
"""

from bayes_poker.strategy.range.mappings import (
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    card_to_index52,
    combo_to_index1326,
    combos_per_hand,
    get_hand_key_to_169_index,
    get_range_169_to_1326,
    get_range_1326_to_169,
    index1326_to_combo,
    index52_to_card,
)
from bayes_poker.strategy.range.belief_adjustment import (
    adjust_belief_range,
    combo_weight,
)
from bayes_poker.strategy.range.models import (
    PostflopRange,
    PreflopRange,
)

__all__ = [
    # 常量
    "RANGE_169_LENGTH",
    "RANGE_169_ORDER",
    "RANGE_1326_LENGTH",
    "adjust_belief_range",
    "combo_weight",
    # 类
    "PostflopRange",
    "PreflopRange",
    # 映射函数
    "card_to_index52",
    "combo_to_index1326",
    "combos_per_hand",
    "get_hand_key_to_169_index",
    "get_range_169_to_1326",
    "get_range_1326_to_169",
    "index1326_to_combo",
    "index52_to_card",
]
