"""翻前策略 sqlite loader。"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.importer import (
    import_strategy_directory_to_sqlite,
)

_EXPECTED_FORMAT_VERSION = 2


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
    _assert_repository_format(repo)
    return repo


def _assert_repository_format(repo: PreflopStrategyRepository) -> None:
    """校验仓库格式版本符合 v2 预期。

    Args:
        repo: 已连接的策略仓库。

    Raises:
        ValueError: 当仓库内 source 的格式版本不符合预期时抛出。
    """

    sources = repo.list_sources()
    if not sources:
        return
    invalid_sources = [
        source
        for source in sources
        if source.format_version != _EXPECTED_FORMAT_VERSION
    ]
    if invalid_sources:
        raise ValueError("当前策略库格式版本过旧，请重建 sqlite 数据库。")
