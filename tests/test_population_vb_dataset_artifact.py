"""population_vb 数据层与 artifact 基础测试。"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import numpy as np
import pytest

from bayes_poker.strategy.strategy_engine.population_vb.artifact import (
    load_population_artifact,
    save_population_artifact,
)
from bayes_poker.strategy.strategy_engine.population_vb.contracts import (
    PopulationPosteriorBucket,
)
from bayes_poker.strategy.strategy_engine.population_vb.dataset import (
    compute_unexposed_by_action,
    load_population_dataset,
)
from bayes_poker.strategy.strategy_engine.population_vb.holdcards import (
    combo_weights_169,
    holdcard_to_hand_class_169,
)
from bayes_poker.strategy.strategy_engine.population_vb.reader import (
    PopulationPosteriorReader,
)


def _write_gzip_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    """把测试数据写入 gzip CSV 文件。

    Args:
        path: 输出文件路径。
        header: CSV 表头。
        rows: CSV 数据行。
    """
    with gzip.open(path, "wt", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def test_combo_weights_and_holdcard_mapping() -> None:
    """应返回合法组合权重并支持 1326->169 映射。"""
    weights = combo_weights_169()
    assert weights.shape == (169,)
    assert float(weights.sum()) == pytest.approx(1326.0)
    assert {4.0, 6.0, 12.0}.issubset(set(weights.tolist()))

    mapped_first = holdcard_to_hand_class_169(0)
    mapped_last = holdcard_to_hand_class_169(1325)
    assert 0 <= mapped_first < 169
    assert 0 <= mapped_last < 169

    with pytest.raises(ValueError, match="holdcard_index"):
        holdcard_to_hand_class_169(1326)


def test_load_population_dataset_merges_counts_and_clamps_unexposed(
    tmp_path: Path,
) -> None:
    """应正确聚合桶数据并在计算 unexposed 时裁剪到非负。"""
    action_totals_path = tmp_path / "action_totals.csv.gz"
    exposed_counts_path = tmp_path / "exposed_combo_counts.csv.gz"

    _write_gzip_csv(
        action_totals_path,
        ["table_type", "preflop_param_index", "action_family", "n_total"],
        [
            [6, 30, "F", 100],
            [6, 30, "C", 80],
            [6, 30, "R", 20],
            [6, 31, "F", 10],
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
            [6, 30, "F", 1000, 10],
            [6, 30, "C", 1001, 15],
            [6, 30, "C", 1002, 90],
            [6, 30, "R", 1003, 5],
        ],
    )
    observations = load_population_dataset(
        action_totals_path=str(action_totals_path),
        exposed_counts_path=str(exposed_counts_path),
    )

    by_param = {obs.param_index: obs for obs in observations}
    assert set(by_param) == {30, 31}

    obs = by_param[30]
    assert obs.table_type == 6
    assert obs.action_totals.shape == (3,)
    assert obs.exposed_counts.shape == (169, 3)
    assert np.array_equal(obs.action_totals, np.array([100.0, 80.0, 20.0]))

    c_index_1 = holdcard_to_hand_class_169(1001)
    c_index_2 = holdcard_to_hand_class_169(1002)
    assert obs.exposed_counts[c_index_1, 1] == pytest.approx(15.0)
    assert obs.exposed_counts[c_index_2, 1] == pytest.approx(90.0)

    unexposed = compute_unexposed_by_action(obs)
    assert np.array_equal(unexposed, np.array([90.0, 0.0, 15.0]))


def test_population_artifact_roundtrip_and_reader(tmp_path: Path) -> None:
    """artifact 保存/加载与 reader 查询应保持一致。"""
    alpha = np.full((169, 3), 1.5, dtype=np.float32)
    mean = np.full((169, 3), 0.2, dtype=np.float32)
    ess = np.full(169, 12.0, dtype=np.float32)
    bucket = PopulationPosteriorBucket(
        table_type=6,
        param_index=30,
        alpha_fcr=alpha,
        mean_fcr=mean,
        ess_by_hand=ess,
        prior_kind="direct_gto",
    )

    artifact_path = tmp_path / "population_vb_test.npz"
    save_population_artifact(
        buckets=[bucket],
        output_path=str(artifact_path),
        metadata={"version": "v1", "note": "unit-test"},
    )

    loaded = load_population_artifact(str(artifact_path))
    assert (6, 30) in loaded
    loaded_bucket = loaded[(6, 30)]
    assert np.allclose(loaded_bucket.alpha_fcr, alpha)
    assert np.allclose(loaded_bucket.mean_fcr, mean)
    assert np.allclose(loaded_bucket.ess_by_hand, ess)
    assert loaded_bucket.prior_kind == "direct_gto"

    reader = PopulationPosteriorReader(str(artifact_path))
    assert reader.get(table_type=6, param_index=30) is not None
    assert reader.get(table_type=6, param_index=9999) is None
