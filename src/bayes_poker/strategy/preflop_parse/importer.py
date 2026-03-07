"""翻前策略 sqlite 导入入口。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.parser import (
    parse_file_meta,
    parse_strategy_node_records,
)

LOGGER = logging.getLogger(__name__)
_FORMAT_VERSION = 1


def import_strategy_directory_to_sqlite(
    *,
    strategy_dir: Path,
    db_path: Path,
) -> Path:
    """将策略目录导入到 sqlite 数据库。

    Args:
        strategy_dir: 策略目录路径。
        db_path: 目标 sqlite 路径。

    Returns:
        导入完成后的数据库路径。
    """

    repo = PreflopStrategyRepository(db_path)
    repo.connect()

    source_id = repo.upsert_source(
        strategy_name=strategy_dir.name,
        source_dir=str(strategy_dir),
        format_version=_FORMAT_VERSION,
    )

    for file_path in sorted(strategy_dir.glob("*.json")):
        _import_strategy_file(
            repo=repo,
            source_id=source_id,
            file_path=file_path,
            strategy_name=strategy_dir.name,
        )

    repo.close()
    return db_path


def _import_strategy_file(
    *,
    repo: PreflopStrategyRepository,
    source_id: int,
    file_path: Path,
    strategy_name: str,
) -> None:
    """导入单个策略文件。

    Args:
        repo: 打开的策略仓库。
        source_id: 目标策略源 ID。
        file_path: 当前 JSON 文件。
        strategy_name: 策略名称。
    """

    meta = parse_file_meta(strategy_name, file_path.stem)
    if meta is None:
        LOGGER.debug("跳过无法识别的策略文件: %s", file_path.name)
        return

    stack_bb, history_full = meta
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("读取策略文件 %s 失败: %s", file_path.name, exc)
        return

    records = parse_strategy_node_records(
        data=data,
        stack_bb=stack_bb,
        history_full=history_full,
        source_file=file_path.name,
    )
    if records is None:
        LOGGER.debug("策略文件 %s 未解析出有效记录", file_path.name)
        return

    node_record, action_records = records
    node_id = repo.insert_node(
        source_id=source_id,
        node_record=node_record,
    )
    repo.insert_actions(
        node_id=node_id,
        action_records=action_records,
    )
