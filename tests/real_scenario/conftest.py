"""tests/real_scenario 公共 fixture。

提供 StrategyEngine 构建、玩家样本加载等共享 fixture,
避免各测试文件重复初始化。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine import (
    StrategyEngine,
    StrategyEngineConfig,
    build_strategy_engine,
)

from .helpers import (
    PLAYER_CORE_STATS_CSV_PATH,
    PLAYER_STATS_DB_PATH,
    RUN_REAL_SCENARIO_ENV,
    STRATEGY_DB_PATH,
    PlayerPfrRow,
    load_players_with_large_pfr_spread,
)


def _skip_unless_real_scenario_enabled() -> None:
    """检查真实场景测试门控条件, 不满足则 skip。"""

    if os.environ.get(RUN_REAL_SCENARIO_ENV) != "1":
        pytest.skip(f"未启用真实场景测试 (设置 {RUN_REAL_SCENARIO_ENV}=1 才运行)。")
    if not STRATEGY_DB_PATH.exists():
        pytest.skip(f"策略数据库不存在: {STRATEGY_DB_PATH}")
    if not PLAYER_STATS_DB_PATH.exists():
        pytest.skip(f"玩家统计数据库不存在: {PLAYER_STATS_DB_PATH}")
    if not PLAYER_CORE_STATS_CSV_PATH.exists():
        pytest.skip(f"player_core_stats.csv 不存在: {PLAYER_CORE_STATS_CSV_PATH}")


@pytest.fixture(scope="module")
def real_scenario_engine() -> StrategyEngine:
    """构建真实场景 StrategyEngine (module 级复用)。

    Returns:
        已初始化的 StrategyEngine 实例。
    """

    _skip_unless_real_scenario_enabled()
    return build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=STRATEGY_DB_PATH,
            player_stats_db_path=PLAYER_STATS_DB_PATH,
            table_type=TableType.SIX_MAX,
            source_ids=(1, 2, 3, 4, 5),
        )
    )


@pytest.fixture(scope="module")
def selected_players() -> list[PlayerPfrRow]:
    """加载 PFR 差异较大的玩家样本 (module 级复用)。

    Returns:
        3 名 PFR 差异较大的玩家行。
    """

    _skip_unless_real_scenario_enabled()
    return load_players_with_large_pfr_spread(
        csv_path=PLAYER_CORE_STATS_CSV_PATH,
        min_hands=200,
        sample_count=3,
    )
