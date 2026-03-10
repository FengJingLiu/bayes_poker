"""策略模块惰性导出。"""

from __future__ import annotations

from importlib import import_module

_EXPORT_MODULES: dict[str, str] = {
    "StrategyHandler": "bayes_poker.strategy.strategy_engine",
    "StrategyDecision": "bayes_poker.strategy.strategy_engine",
    "RecommendationDecision": "bayes_poker.strategy.strategy_engine",
    "NoResponseDecision": "bayes_poker.strategy.strategy_engine",
    "UnsupportedScenarioDecision": "bayes_poker.strategy.strategy_engine",
    "SafeFallbackDecision": "bayes_poker.strategy.strategy_engine",
    "StrategyEngine": "bayes_poker.strategy.strategy_engine",
    "StrategyEngineConfig": "bayes_poker.strategy.strategy_engine",
    "create_strategy_handler": "bayes_poker.strategy.strategy_engine",
    "PreflopLayer": "bayes_poker.strategy.runtime",
    "PreflopRuntimeConfig": "bayes_poker.strategy.runtime",
    "create_preflop_strategy": "bayes_poker.strategy.runtime",
    "create_preflop_strategy_from_directory": "bayes_poker.strategy.runtime",
    "create_postflop_strategy": "bayes_poker.strategy.runtime",
    "infer_preflop_layer": "bayes_poker.strategy.runtime",
    "load_preflop_strategy_from_directory": "bayes_poker.strategy.runtime",
    "STRATEGY_VECTOR_LENGTH": "bayes_poker.strategy.preflop_parse",
    "PreflopStrategy": "bayes_poker.strategy.preflop_parse",
    "StrategyAction": "bayes_poker.strategy.preflop_parse",
    "StrategyNode": "bayes_poker.strategy.preflop_parse",
    "normalize_token": "bayes_poker.strategy.preflop_parse",
    "parse_all_strategies": "bayes_poker.strategy.preflop_parse",
    "parse_bet_size_from_code": "bayes_poker.strategy.preflop_parse",
    "parse_file_meta": "bayes_poker.strategy.preflop_parse",
    "parse_strategy_directory": "bayes_poker.strategy.preflop_parse",
    "parse_strategy_file": "bayes_poker.strategy.preflop_parse",
    "parse_strategy_node": "bayes_poker.strategy.preflop_parse",
    "split_history_tokens": "bayes_poker.strategy.preflop_parse",
    "OpponentRangePredictor": "bayes_poker.strategy.opponent_range",
    "create_opponent_range_predictor": "bayes_poker.strategy.opponent_range",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> object:
    """按需加载策略模块导出。

    Args:
        name: 导出名称。

    Returns:
        对应的运行时对象。

    Raises:
        AttributeError: 当名称不在导出列表中时抛出。
    """

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
