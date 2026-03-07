"""翻前共享推理内核惰性导出。"""

from __future__ import annotations

from importlib import import_module

_EXPORT_MODULES: dict[str, str] = {
    "PreflopDecisionState": "bayes_poker.strategy.preflop_engine.state",
    "PreflopNodeMapper": "bayes_poker.strategy.preflop_engine.mapper",
    "RangeEngine": "bayes_poker.strategy.preflop_engine.range_engine",
    "PreflopHeroEngine": "bayes_poker.strategy.preflop_engine.hero_engine",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> object:
    """按需加载翻前引擎导出。

    Args:
        name: 导出名称。

    Returns:
        对应的运行时对象。

    Raises:
        AttributeError: 当名称不存在时抛出。
    """

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
