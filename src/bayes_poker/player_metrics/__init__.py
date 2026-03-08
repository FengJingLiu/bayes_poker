"""玩家指标构建模块。

从 PHHS 手牌数据中提取玩家动作并构建统计指标，包括：
- VPIP (Voluntarily Put Money In Pot) - 自愿入池率
- PFR (Pre-Flop Raise) - 翻前加注率
- Aggression - 激进频率
- WTP (Willingness to Pay) - 面对下注时的继续率

移植自 G5.Logic (C#) 项目。
"""

from __future__ import annotations

from .builder import (
    ParsedAction,
    build_player_stats_from_hands,
    calculate_aggression,
    calculate_bet_sizing_category,
    calculate_pfr,
    calculate_total_hands,
    calculate_wtp,
    extract_actions_from_hand_history,
    get_player_position,
    increment_player_stats,
    is_in_position,
)
from .enums import ActionType, Position, Street, TableType
from .models import ActionStats, BetSizingCategory, PlayerStats, StatValue
from .params import PostFlopParams, PreFlopParams
from .posterior import (
    ActionBucket,
    ActionSpaceKind,
    ActionSpaceSpec,
    BinaryPosteriorCounts,
    PosteriorSmoothingConfig,
    classify_postflop_action_space,
    classify_preflop_action_space,
    smooth_binary_counts,
    smooth_multinomial_counts,
)

__all__ = [
    "ActionStats",
    "ActionBucket",
    "ActionType",
    "ActionSpaceKind",
    "ActionSpaceSpec",
    "BetSizingCategory",
    "BinaryPosteriorCounts",
    "ParsedAction",
    "PlayerStats",
    "Position",
    "PostFlopParams",
    "PosteriorSmoothingConfig",
    "PreFlopParams",
    "StatValue",
    "Street",
    "TableType",
    "build_player_stats_from_hands",
    "calculate_aggression",
    "calculate_bet_sizing_category",
    "calculate_pfr",
    "calculate_total_hands",
    "calculate_wtp",
    "classify_postflop_action_space",
    "classify_preflop_action_space",
    "extract_actions_from_hand_history",
    "get_player_position",
    "increment_player_stats",
    "is_in_position",
    "smooth_binary_counts",
    "smooth_multinomial_counts",
]
