"""预留检验 bucket 相似度映射逻辑的白盒测试。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from bayes_poker.strategy.preflop_parse import normalize_history
from bayes_poker.strategy.range import PreflopRange

import importlib

bucket_similarity = importlib.import_module(
    "bayes_poker.strategy.strategy_engine.population_vb.bucket_similarity"
)


def _make_solver_node(*, history_full: str, acting_position: str) -> dict[str, str]:
    """构造只带历史与位置的 solver_node 记录。

    Args:
        history_full: 完整历史字符串。
        acting_position: 当前待行动位置。

    Returns:
        仅包含历史与位置的节点字典。
    """

    return {
        "history_full": history_full,
        "history_actions": normalize_history(history_full),
        "acting_position": acting_position,
    }


def test_map_param_index_first_in_root() -> None:
    """根节点 UTG 对应 bucket 0。"""

    node = _make_solver_node(history_full="", acting_position="UTG")
    assert bucket_similarity.map_solver_node_to_preflop_param_index(node) == 0


def test_map_param_index_first_in_bb_limp_defense() -> None:
    """BB limp defense 应落在 bucket 19。"""

    node = _make_solver_node(history_full="F-F-F-F-C", acting_position="BB")
    assert bucket_similarity.map_solver_node_to_preflop_param_index(node) == 19


def test_map_param_index_passive_reentry() -> None:
    """Passive re-entry 场景应落在 bucket 25。"""

    node = _make_solver_node(
        history_full="R2-C-F-F-R6-F-F",
        acting_position="HJ",
    )
    assert bucket_similarity.map_solver_node_to_preflop_param_index(node) == 25


def test_map_param_index_active_reentry() -> None:
    """Active re-entry 场景应落在 bucket 45。"""

    node = _make_solver_node(
        history_full="F-F-R3-F-R8-F",
        acting_position="CO",
    )
    assert bucket_similarity.map_solver_node_to_preflop_param_index(node) == 45


def test_map_param_index_aggressor_first_in_flag() -> None:
    """Aggressor_first_in True/False 两种历史应映射到不同桶。"""

    true_aggressor = _make_solver_node(
        history_full="F-F-R3-F-R8-F",
        acting_position="CO",
    )
    false_aggressor = _make_solver_node(
        history_full="C-F-R3-F-F-F-R8",
        acting_position="CO",
    )

    result_true = bucket_similarity.map_solver_node_to_preflop_param_index(true_aggressor)
    result_false = bucket_similarity.map_solver_node_to_preflop_param_index(false_aggressor)
    assert result_true == 45
    assert result_false == 47


def test_map_param_index_returns_none_for_unknown_token() -> None:
    """历史包含未知 token 时应返回 None。"""

    node = _make_solver_node(
        history_full="F-F-R3-X-R8-F",
        acting_position="CO",
    )
    assert bucket_similarity.map_solver_node_to_preflop_param_index(node) is None


@dataclass(frozen=True)
class _FakeActionRecord:
    action_family: str
    action_code: str
    strategy: PreflopRange
    total_combos: int
    action_type: str = ""


def _constant_range(value: float) -> PreflopRange:
    """构造值相等的 169 维策略矩阵。"""

    return PreflopRange.from_list(strategy=[value] * 169, evs=[0.0] * 169)


def test_profile_fold_accumulates_raises() -> None:
    """验证动作族折叠会把多个 raise 尺度累加到 `R` 列。

    Returns:
        `None`。
    """

    records = (
        _FakeActionRecord(action_family="F", action_code="F", strategy=_constant_range(0.1), total_combos=10),
        _FakeActionRecord(action_family="C", action_code="C", strategy=_constant_range(0.2), total_combos=10),
        _FakeActionRecord(action_family="R", action_code="R4", strategy=_constant_range(0.3), total_combos=10),
        _FakeActionRecord(action_family="R", action_code="R10", strategy=_constant_range(0.4), total_combos=10),
    )
    profile = bucket_similarity.fold_action_families(records)
    assert profile.shape == (169, 3)
    assert profile[0].tolist() == pytest.approx([0.1, 0.2, 0.7])


def test_profile_fold_falls_back_to_action_type() -> None:
    """验证动作码未知时会回退到 `action_type` 识别动作族。

    Returns:
        `None`。
    """

    records = (
        _FakeActionRecord(
            action_family="",
            action_code="X",
            action_type="CHECK",
            strategy=_constant_range(1.0),
            total_combos=10,
        ),
    )
    profile = bucket_similarity.fold_action_families(records)
    assert profile.shape == (169, 3)
    assert profile[0].tolist() == pytest.approx([0.0, 1.0, 0.0])


def test_bucket_profile_weighted_average() -> None:
    """验证分桶画像按节点 `total_combos` 做加权平均。

    Returns:
        `None`。
    """

    profile_a = bucket_similarity.fold_action_families((
        _FakeActionRecord(action_family="F", action_code="F", strategy=_constant_range(1.0), total_combos=1),
    ))
    profile_b = bucket_similarity.fold_action_families((
        _FakeActionRecord(action_family="R", action_code="R4", strategy=_constant_range(1.0), total_combos=1),
    ))
    bucket = bucket_similarity.aggregate_bucket_profile(
        param_index=25,
        node_profiles=(
            bucket_similarity.BucketNodeProfile(
                probs_fcr=profile_a,
                total_combos=15.0,
            ),
            bucket_similarity.BucketNodeProfile(
                probs_fcr=profile_b,
                total_combos=5.0,
            ),
        ),
    )
    assert bucket.total_node_weight == 20
    assert bucket.probs_fcr[0].tolist() == pytest.approx([0.75, 0.0, 0.25])


def test_distance_combo_vs_uniform() -> None:
    """验证 `combo` 与 `uniform` 两种距离模式的数值。

    Returns:
        `None`。
    """

    base = np.zeros((169, 3), dtype=float)
    base[0, 0] = 1.0
    variant = np.zeros_like(base)
    variant[0, 1] = 1.0
    combo_distance = bucket_similarity.compute_distance(base, variant, weight_mode="combo")
    uniform_distance = bucket_similarity.compute_distance(base, variant, weight_mode="uniform")
    assert combo_distance == pytest.approx((12 / 1326) ** 0.5)
    assert uniform_distance == pytest.approx((2 / 169) ** 0.5)
    assert combo_distance != uniform_distance


def test_distance_matrix_accepts_bucket_profiles() -> None:
    """验证距离矩阵接口可直接接收 `BucketStrategyProfile` 映射。

    Returns:
        `None`。
    """

    profile_a = np.zeros((169, 3), dtype=float)
    profile_a[0, 0] = 1.0
    profile_b = np.zeros((169, 3), dtype=float)
    profile_b[0, 1] = 1.0
    buckets = {
        25: bucket_similarity.BucketStrategyProfile(
            table_type=6,
            param_index=25,
            probs_fcr=profile_a.astype(np.float32),
            node_count=1,
            total_node_weight=10.0,
        ),
        4: bucket_similarity.BucketStrategyProfile(
            table_type=6,
            param_index=4,
            probs_fcr=profile_b.astype(np.float32),
            node_count=1,
            total_node_weight=10.0,
        ),
    }

    ordered_indices, distance_matrix = bucket_similarity.compute_distance_matrix(
        buckets,
        weight_mode="combo",
    )

    assert ordered_indices == (4, 25)
    assert np.allclose(distance_matrix, distance_matrix.T)
    assert np.allclose(np.diag(distance_matrix), 0.0)


def test_cluster_complete_link_prevents_chain_merging() -> None:
    """complete-link 聚类不会把链式距离的三个桶合并为一个簇。"""

    distance_matrix = np.array(
        [
            [0.0, 0.1, 0.5],
            [0.1, 0.0, 0.1],
            [0.5, 0.1, 0.0],
        ],
        dtype=float,
    )
    cluster_labels = bucket_similarity.cluster_buckets(distance_matrix, threshold=0.2)

    assert len(cluster_labels) == 2
    assert {frozenset(cluster) for cluster in cluster_labels} == {frozenset({0}), frozenset({1, 2})}


def test_representative_bucket_prefers_highest_hits() -> None:
    """代表桶应选取 hits 最大的桶。"""

    cluster = (25, 40)
    hits = {25: 5, 40: 10}
    representative = bucket_similarity.select_representative_bucket(cluster, hits)
    assert representative == 40


def test_threshold_sweep_reports_stats_and_recommendation() -> None:
    """阈值扫描应返回簇统计与推荐阈值。"""

    distance_matrix = np.array(
        [
            [0.0, 0.1, 0.4],
            [0.1, 0.0, 0.3],
            [0.4, 0.3, 0.0],
        ],
        dtype=float,
    )
    bucket_ids = (25, 40, 60)
    hits = {25: 10, 40: 5, 60: 2}
    thresholds = [0.05, 0.15, 0.35]
    sweep = bucket_similarity.compute_threshold_sweep(
        distance_matrix,
        hits,
        thresholds,
        ordered_bucket_indices=bucket_ids,
    )

    def _get(row: object, key: str) -> object | None:
        if isinstance(row, dict):
            return row.get(key)
        return getattr(row, key, None)

    assert len(sweep) == len(thresholds)
    expected_keys = (
        "threshold",
        "cluster_count",
        "merged_bucket_count",
        "merged_hit_ratio",
        "guardrail_ok",
    )
    for row in sweep:
        for key in expected_keys:
            assert _get(row, key) is not None
    threshold_row = next(
        (row for row in sweep if _get(row, "threshold") == pytest.approx(0.15)),
        None,
    )
    assert threshold_row is not None
    assert _get(threshold_row, "cluster_count") == 2
    assert _get(threshold_row, "merged_bucket_count") == 2
    assert _get(threshold_row, "merged_hit_ratio") == pytest.approx(15 / 17)

    recommended_rows = [row for row in sweep if _get(row, "recommended")]
    assert len(recommended_rows) == 1
    assert all(_get(row, "guardrail_ok") is False for row in sweep)
    assert _get(recommended_rows[0], "guardrail_ok") is False
