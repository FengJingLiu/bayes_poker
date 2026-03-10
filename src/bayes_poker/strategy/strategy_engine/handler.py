"""strategy_engine v2 的 handler factory。"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.player_metrics.enums import TableType
from .contracts import StrategyHandler
from .engine import (
    StrategyEngineConfig,
    build_strategy_engine,
)


def create_strategy_handler(
    *,
    strategy_db_path: Path,
    player_stats_db_path: Path,
    table_type: TableType = TableType.SIX_MAX,
    source_id: int | None = None,
    strategy_name: str | None = None,
    pool_prior_strength: float = 20.0,
) -> StrategyHandler:
    """创建 strategy_engine v2 的公开 handler。"""

    return build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=strategy_db_path,
            player_stats_db_path=player_stats_db_path,
            table_type=table_type,
            source_id=source_id,
            strategy_name=strategy_name,
            pool_prior_strength=pool_prior_strength,
        )
    )
