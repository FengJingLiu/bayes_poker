"""翻前策略解析模块。

提供 GTOWizard 风格翻前策略 JSON 文件的解析功能。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bayes_poker.strategy.preflop_parse.models import (
    STRATEGY_VECTOR_LENGTH,
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.preflop_parse.parser import (
    is_in_position,
    normalize_token,
    parse_all_strategies,
    parse_bet_size_from_code,
    parse_file_meta,
    parse_strategy_directory,
    parse_strategy_file,
    parse_strategy_node,
    resolve_action_positions,
    resolve_position,
    split_history_tokens,
)
from bayes_poker.strategy.preflop_parse.query import (
    QueryResult,
    generate_call_to_fold_variants,
    normalize_history,
    query_node,
)

if TYPE_CHECKING:
    from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository


def import_strategy_directory_to_sqlite(
    *,
    strategy_dir: Path,
    db_path: Path,
) -> Path:
    """惰性导入 sqlite 导入入口。

    Args:
        strategy_dir: 策略目录路径。
        db_path: 目标数据库路径。

    Returns:
        导入完成后的数据库路径。
    """

    from bayes_poker.strategy.preflop_parse.importer import (
        import_strategy_directory_to_sqlite as _impl,
    )

    return _impl(strategy_dir=strategy_dir, db_path=db_path)


def build_preflop_strategy_db(
    *,
    strategy_dir: Path,
    db_path: Path,
) -> Path:
    """惰性导入 sqlite 构建入口。

    Args:
        strategy_dir: 策略目录路径。
        db_path: 目标数据库路径。

    Returns:
        构建完成后的数据库路径。
    """

    from bayes_poker.strategy.preflop_parse.loader import (
        build_preflop_strategy_db as _impl,
    )

    return _impl(strategy_dir=strategy_dir, db_path=db_path)


def open_preflop_strategy_repository(
    db_path: Path,
) -> "PreflopStrategyRepository":
    """惰性导入仓库打开入口。

    Args:
        db_path: sqlite 数据库路径。

    Returns:
        已连接的翻前策略仓库。
    """

    from bayes_poker.strategy.preflop_parse.loader import (
        open_preflop_strategy_repository as _impl,
    )

    return _impl(db_path)

__all__ = [
    # Models
    "STRATEGY_VECTOR_LENGTH",
    "PreflopStrategy",
    "StrategyAction",
    "StrategyNode",
    # Sqlite Import / Loader
    "build_preflop_strategy_db",
    "import_strategy_directory_to_sqlite",
    "open_preflop_strategy_repository",
    # Parser
    "normalize_token",
    "parse_all_strategies",
    "parse_bet_size_from_code",
    "parse_file_meta",
    "parse_strategy_directory",
    "parse_strategy_file",
    "parse_strategy_node",
    "resolve_action_positions",
    "resolve_position",
    "is_in_position",
    "split_history_tokens",
    # Query
    "QueryResult",
    "generate_call_to_fold_variants",
    "normalize_history",
    "query_node",
]
