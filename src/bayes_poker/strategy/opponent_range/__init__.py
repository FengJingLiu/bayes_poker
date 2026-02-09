"""对手范围预测模块。

根据对手的行动历史和统计数据预测其手牌范围。

主要功能：
- 翻前范围预测：根据对手行动收窄 169 维手牌范围
- 翻后范围预测：根据公共牌和行动收窄 1326 维手牌范围
"""

from bayes_poker.strategy.opponent_range.predictor import (
    OpponentRangePredictor,
    create_opponent_range_predictor,
)
from bayes_poker.strategy.opponent_range.frequency_fill import build_limp_calling_range
from bayes_poker.strategy.opponent_range.preflop_context import (
    OpponentPreflopContext,
    build_opponent_preflop_context,
)
from bayes_poker.strategy.opponent_range.stats_source import (
    get_aggregated_player_name,
    get_aggregated_player_stats,
)

__all__ = [
    "OpponentRangePredictor",
    "create_opponent_range_predictor",
    "OpponentPreflopContext",
    "build_limp_calling_range",
    "build_opponent_preflop_context",
    "get_aggregated_player_name",
    "get_aggregated_player_stats",
]
