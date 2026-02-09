"""实时策略执行（runtime）。

提供策略处理器的类型定义、通用工具函数，以及 preflop/postflop 策略处理器实现。
"""

from bayes_poker.strategy.runtime.base import StrategyHandler, _base_response
from bayes_poker.strategy.runtime.postflop import create_postflop_strategy
from bayes_poker.strategy.runtime.preflop import (
    PreflopLayer,
    PreflopRuntimeConfig,
    create_preflop_strategy,
    create_preflop_strategy_from_directory,
    infer_preflop_layer,
    load_preflop_strategy_from_directory,
)

__all__ = [
    "StrategyHandler",
    "_base_response",
    "PreflopLayer",
    "PreflopRuntimeConfig",
    "create_preflop_strategy",
    "create_preflop_strategy_from_directory",
    "create_postflop_strategy",
    "infer_preflop_layer",
    "load_preflop_strategy_from_directory",
]
