"""翻前 bucket 相似度 CLI 冒烟测试。"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from bayes_poker.domain.action_family import ActionFamily
from bayes_poker.domain.table import Position
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH


def _constant_range(strategy_value: float, ev_value: float) -> PreflopRange:
    """构造常量 preflop range。"""

    return PreflopRange.from_list(
        strategy=[strategy_value] * RANGE_169_LENGTH,
        evs=[ev_value] * RANGE_169_LENGTH,
    )


def _make_action_records() -> tuple[ParsedStrategyActionRecord, ...]:
    """构造节点动作列表用于聚合。"""

    return (
        ParsedStrategyActionRecord(
            order_index=0,
            action_code="F",
            action_type="FOLD",
            bet_size_bb=None,
            is_all_in=False,
            total_frequency=0.4,
            next_position=Position.BTN.value,
            preflop_range=_constant_range(0.4, -0.1),
            total_ev=-0.1,
            total_combos=0.4 * 1326.0,
        ),
        ParsedStrategyActionRecord(
            order_index=1,
            action_code="C",
            action_type="CALL",
            bet_size_bb=None,
            is_all_in=False,
            total_frequency=0.6,
            next_position=Position.BTN.value,
            preflop_range=_constant_range(0.6, 0.2),
            total_ev=0.2,
            total_combos=0.6 * 1326.0,
        ),
    )


def _make_node_record(
    *,
    history_full: str,
    history_actions: str,
    actor_position: Position,
    aggressor_position: Position | None,
    call_count: int,
    limp_count: int,
    raise_time: int,
    pot_size: float,
    raise_size_bb: float | None,
    is_in_position: bool | None,
) -> ParsedStrategyNodeRecord:
    """构造预设的策略节点记录，用于生成两个不同的 bucket。"""

    return ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full=history_full,
        history_actions=history_actions,
        history_token_count=len(history_actions.split("-")),
        acting_position=actor_position.value,
        source_file="cli_bucket_similarity.json",
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=actor_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_time=raise_time,
        pot_size=pot_size,
        raise_size_bb=raise_size_bb,
        is_in_position=is_in_position,
    )


def _build_tiny_strategy_db(path: Path) -> None:
    """构造包含两个参数桶的策略数据库。"""

    repo = PreflopStrategyRepository(path)
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="bucket-similarity",
        source_dir=str(path.parent),
        format_version=1,
    )
    node_records = (
        _make_node_record(
            history_full="R2",
            history_actions="R",
            actor_position=Position.CO,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_time=0,
            pot_size=1.5,
            raise_size_bb=None,
            is_in_position=None,
        ),
        _make_node_record(
            history_full="R2-C",
            history_actions="R-C",
            actor_position=Position.BTN,
            aggressor_position=Position.CO,
            call_count=1,
            limp_count=0,
            raise_time=1,
            pot_size=3.0,
            raise_size_bb=2.0,
            is_in_position=True,
        ),
    )
    node_ids = repo.insert_nodes(source_id=source_id, node_records=node_records)
    for node_id in node_ids.values():
        repo.insert_actions(node_id=node_id, action_records=_make_action_records())
    repo.close()


def _write_hits_csv(path: Path, rows: Sequence[tuple[int, int]]) -> None:
    """写入包含 preflop_param_index 和 hits 的命中量 CSV。"""

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["preflop_param_index", "hits"])
        writer.writerows(rows)


def _invoke_bucket_similarity_cli(
    strategy_db: Path, hits_csv: Path, output_dir: Path
) -> subprocess.CompletedProcess[str]:
    """调用未来的 analyze_preflop_bucket_similarity CLI。"""

    python_path = str(Path.cwd() / "src")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{python_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else python_path
    )
    cmd = [
        sys.executable,
        "scripts/analyze_preflop_bucket_similarity.py",
        "--strategy-db",
        str(strategy_db),
        "--hits-csv",
        str(hits_csv),
        "--output-dir",
        str(output_dir),
    ]
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def test_cli_outputs_bucket_merge_artifacts(tmp_path: Path) -> None:
    """CLI 运行后应在输出目录包含合并摘要与建议文件。"""

    strategy_db = tmp_path / "strategy.db"
    _build_tiny_strategy_db(strategy_db)
    hits_csv = tmp_path / "bucket_hits.csv"
    _write_hits_csv(hits_csv, [(0, 15), (4, 9)])
    output_dir = tmp_path / "bucket_similarity"
    output_dir.mkdir()

    result = _invoke_bucket_similarity_cli(
        strategy_db=strategy_db, hits_csv=hits_csv, output_dir=output_dir
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "bucket_merge_summary.json").exists()
    assert (output_dir / "bucket_merge_suggestions.csv").exists()
