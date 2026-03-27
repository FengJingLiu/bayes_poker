"""population_vb CLI 冒烟测试。"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

from bayes_poker.domain.table import Position
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import RANGE_169_LENGTH, PreflopRange
from bayes_poker.strategy.strategy_engine.population_vb.artifact import (
    load_population_artifact,
)
from bayes_poker.strategy.strategy_engine.population_vb.cli import run_cli


def _constant_range(strategy_value: float, ev_value: float) -> PreflopRange:
    """构造常量 preflop range。"""
    return PreflopRange.from_list(
        strategy=[strategy_value] * RANGE_169_LENGTH,
        evs=[ev_value] * RANGE_169_LENGTH,
    )


def _write_gzip_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    """写入 gzip CSV 测试文件。"""
    with gzip.open(path, "wt", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def _build_tiny_strategy_db(path: Path) -> int:
    """构造最小可用策略库并返回 source_id。"""
    repo = PreflopStrategyRepository(path)
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="cli-smoke",
        source_dir=str(path.parent),
        format_version=1,
    )
    node_id = repo.insert_node(
        source_id=source_id,
        node_record=ParsedStrategyNodeRecord(
            stack_bb=100,
            history_full="R2",
            history_actions="R",
            history_token_count=1,
            acting_position="UTG",
            source_file="cli_smoke.json",
            action_family=None,
            actor_position=Position.UTG,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_time=0,
            pot_size=1.5,
            raise_size_bb=None,
            is_in_position=None,
        ),
    )
    repo.insert_actions(
        node_id=node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.3,
                next_position="HJ",
                preflop_range=_constant_range(0.3, -1.0),
                total_ev=-1.0,
                total_combos=0.3 * 1326.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.3,
                next_position="HJ",
                preflop_range=_constant_range(0.3, 0.0),
                total_ev=0.0,
                total_combos=0.3 * 1326.0,
            ),
            ParsedStrategyActionRecord(
                order_index=2,
                action_code="R4",
                action_type="RAISE",
                bet_size_bb=4.0,
                is_all_in=False,
                total_frequency=0.4,
                next_position="HJ",
                preflop_range=_constant_range(0.4, 0.8),
                total_ev=0.8,
                total_combos=0.4 * 1326.0,
            ),
        ),
    )
    repo.close()
    return source_id


def test_cli_end_to_end_on_tiny_fixture(tmp_path: Path) -> None:
    """CLI 在最小数据集上应能输出 artifact。"""
    strategy_db_path = tmp_path / "strategy.db"
    source_id = _build_tiny_strategy_db(strategy_db_path)

    action_totals_path = tmp_path / "action_totals.csv.gz"
    exposed_counts_path = tmp_path / "exposed_combo_counts.csv.gz"
    _write_gzip_csv(
        action_totals_path,
        ["table_type", "preflop_param_index", "action_family", "n_total"],
        [
            [6, 10, "F", 30],
            [6, 10, "C", 30],
            [6, 10, "R", 40],
        ],
    )
    _write_gzip_csv(
        exposed_counts_path,
        [
            "table_type",
            "preflop_param_index",
            "action_family",
            "holdcard_index",
            "n_exposed",
        ],
        [
            [6, 10, "F", 80, 3],
            [6, 10, "C", 81, 3],
            [6, 10, "R", 82, 4],
        ],
    )
    artifact_path = tmp_path / "population_artifact.npz"
    exit_code = run_cli(
        [
            "--strategy-db",
            str(strategy_db_path),
            "--source-id",
            str(source_id),
            "--action-totals",
            str(action_totals_path),
            "--exposed-counts",
            str(exposed_counts_path),
            "--output",
            str(artifact_path),
        ]
    )

    assert exit_code == 0
    assert artifact_path.exists()
    loaded = load_population_artifact(str(artifact_path))
    assert len(loaded) == 1
    assert (6, 10) in loaded
