"""翻前策略 sqlite loader。"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.importer import (
    import_strategy_directory_to_sqlite,
)


def build_preflop_strategy_db(
    *,
    strategy_dir: Path,
    db_path: Path,
) -> Path:
    """构建翻前策略 sqlite 数据库。

    Args:
        strategy_dir: 策略目录路径。
        db_path: 目标数据库路径。

    Returns:
        构建完成后的数据库路径。
    """

    return import_strategy_directory_to_sqlite(
        strategy_dir=strategy_dir,
        db_path=db_path,
    )


def open_preflop_strategy_repository(db_path: Path) -> PreflopStrategyRepository:
    """打开并连接翻前策略仓库。

    Args:
        db_path: sqlite 数据库路径。

    Returns:
        已连接的仓库实例。
    """

    repo = PreflopStrategyRepository(db_path)
    repo.connect()
    return repo
