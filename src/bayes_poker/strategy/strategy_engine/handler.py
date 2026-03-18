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
    source_ids: tuple[int, ...] | None = None,
    strategy_name: str | None = None,
    strategy_names: tuple[str, ...] | None = None,
    enable_global_raise_blending: bool = True,
) -> StrategyHandler:
    """创建 strategy_engine v2 的公开 handler.

    Args:
        strategy_db_path: 策略数据库路径.
        player_stats_db_path: 玩家统计数据库路径.
        table_type: 牌桌类型.
        source_id: 单个策略源 ID.
        source_ids: 多个策略源 ID.
        strategy_name: 单个策略源名称.
        strategy_names: 多个策略源名称.
        enable_global_raise_blending: 是否启用全局加注频率混合.

    Returns:
        可调用的策略处理器.
    """

    return build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=strategy_db_path,
            player_stats_db_path=player_stats_db_path,
            table_type=table_type,
            source_id=source_id,
            source_ids=source_ids,
            strategy_name=strategy_name,
            strategy_names=strategy_names,
            enable_global_raise_blending=enable_global_raise_blending,
        )
    )
