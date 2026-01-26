"""实时策略执行（runtime）。

与 `bayes_poker.strategy.preflop`（策略文件解析/查询）区分：本包面向 server 的实时决策，
用于实现可注册到 `StrategyDispatcher` 的 preflop/postflop 策略处理器。
"""

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
    "PreflopLayer",
    "PreflopRuntimeConfig",
    "create_preflop_strategy",
    "create_preflop_strategy_from_directory",
    "create_postflop_strategy",
    "infer_preflop_layer",
    "load_preflop_strategy_from_directory",
]
