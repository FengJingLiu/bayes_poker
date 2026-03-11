"""测试 StrategyEngine 初始化与基本功能。"""

from __future__ import annotations

from pathlib import Path

import pytest

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine import (
    StrategyEngine,
    StrategyEngineConfig,
    build_strategy_engine,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STRATEGY_DB_PATH = _REPO_ROOT / "data" / "database" / "preflop_strategy.sqlite3"
_PLAYER_STATS_DB_PATH = _REPO_ROOT / "data" / "database" / "player_stats.db"


@pytest.mark.skipif(
    not _STRATEGY_DB_PATH.exists(),
    reason="策略数据库不存在",
)
@pytest.mark.skipif(
    not _PLAYER_STATS_DB_PATH.exists(),
    reason="玩家统计数据库不存在",
)
def test_strategy_engine_initialization_with_source_ids() -> None:
    """StrategyEngine 应能使用指定 source_ids 正确初始化。"""

    config = StrategyEngineConfig(
        strategy_db_path=_STRATEGY_DB_PATH,
        player_stats_db_path=_PLAYER_STATS_DB_PATH,
        table_type=TableType.SIX_MAX,
        source_ids=(1, 2, 3, 4, 5),
    )

    engine = build_strategy_engine(config)

    assert isinstance(engine, StrategyEngine)
    assert engine._opponent_pipeline is not None
    assert engine._hero_resolver is not None


@pytest.mark.skipif(
    not _STRATEGY_DB_PATH.exists(),
    reason="策略数据库不存在",
)
@pytest.mark.skipif(
    not _PLAYER_STATS_DB_PATH.exists(),
    reason="玩家统计数据库不存在",
)
def test_strategy_engine_initialization_resolve_all_sources() -> None:
    """StrategyEngine 应能自动解析所有可用策略源。"""

    config = StrategyEngineConfig(
        strategy_db_path=_STRATEGY_DB_PATH,
        player_stats_db_path=_PLAYER_STATS_DB_PATH,
        table_type=TableType.SIX_MAX,
    )

    engine = build_strategy_engine(config)

    assert isinstance(engine, StrategyEngine)
    assert engine._opponent_pipeline is not None
    assert engine._hero_resolver is not None
