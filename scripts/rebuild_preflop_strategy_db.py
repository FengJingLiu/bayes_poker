"""重建翻前策略 SQLite 数据库(多源导入)。

用法:
    uv run python scripts/rebuild_preflop_strategy_db.py

将 5 个策略源目录全部导入到同一个 preflop_strategy.sqlite3 中。
旧数据库会被删除并重建。
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.parser import (
    parse_file_meta,
    parse_strategy_node_records,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)

_FORMAT_VERSION = 2

STRATEGY_BASE = Path("/home/autumn/gg_handhistory/preflop_strategy")
STRATEGY_DIRS: list[str] = [
    "Cash6m50zGeneral",
    "Cash6m50zGeneral25Open3betV2",
    "Cash6m50zGeneral3betV2",
    "Cash6m50zSimple_SimpleIP",
    "Cash6m50zSimple25Open_SimpleIP",
]

DB_PATH = Path("data/database/preflop_strategy.sqlite3")


def main() -> None:
    """主入口: 删除旧库, 依次导入 5 个策略源。"""

    if DB_PATH.exists():
        LOGGER.info("删除旧数据库: %s", DB_PATH)
        DB_PATH.unlink()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    repo = PreflopStrategyRepository(DB_PATH)
    repo.connect()

    total_nodes = 0
    t_start = time.perf_counter()

    for dir_name in STRATEGY_DIRS:
        strategy_dir = STRATEGY_BASE / dir_name
        if not strategy_dir.is_dir():
            LOGGER.warning("策略目录不存在, 跳过: %s", strategy_dir)
            continue

        source_id = repo.upsert_source(
            strategy_name=dir_name,
            source_dir=str(strategy_dir),
            format_version=_FORMAT_VERSION,
        )

        json_files = sorted(strategy_dir.glob("*.json"))
        LOGGER.info(
            "导入 %s (%d 个文件, source_id=%d) ...",
            dir_name,
            len(json_files),
            source_id,
        )

        dir_nodes = 0
        for file_path in json_files:
            meta = parse_file_meta(dir_name, file_path.stem)
            if meta is None:
                continue

            stack_bb, history_full = meta
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                LOGGER.warning("读取 %s 失败: %s", file_path.name, exc)
                continue

            records = parse_strategy_node_records(
                data=data,
                stack_bb=stack_bb,
                history_full=history_full,
                source_file=file_path.name,
            )
            if records is None:
                continue

            node_record, action_records = records
            node_id = repo.insert_node(
                source_id=source_id,
                node_record=node_record,
            )
            repo.insert_actions(
                node_id=node_id,
                action_records=action_records,
            )
            dir_nodes += 1

        LOGGER.info("  -> %s: %d 个节点", dir_name, dir_nodes)
        total_nodes += dir_nodes

    repo.close()

    elapsed = time.perf_counter() - t_start
    LOGGER.info(
        "完成! 共导入 %d 个节点, 耗时 %.1f 秒, 数据库: %s",
        total_nodes,
        elapsed,
        DB_PATH,
    )


if __name__ == "__main__":
    main()
