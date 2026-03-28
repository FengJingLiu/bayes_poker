"""population_vb 训练数据读取与组装。"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import numpy as np

from bayes_poker.strategy.range import RANGE_169_LENGTH

from .contracts import PopulationBucketObservation

_ACTION_FAMILY_INDEX: dict[str, int] = {"F": 0, "C": 1, "R": 2}


def _read_gzip_csv(path: str | Path) -> list[dict[str, str]]:
    """读取 gzip CSV 并返回字典行列表。

    Args:
        path: gzip CSV 文件路径。

    Returns:
        行字典列表。
    """

    with gzip.open(path, "rt", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def _parse_bucket_key(row: dict[str, str]) -> tuple[int, int]:
    """解析 bucket 主键。

    Args:
        row: CSV 单行字典。

    Returns:
        `(table_type, param_index)` 元组。
    """

    table_type = int(row["table_type"])
    param_index = int(row["preflop_param_index"])
    return (table_type, param_index)


def _init_observation_arrays() -> tuple[np.ndarray, np.ndarray]:
    """初始化单个 bucket 的空数组。

    Returns:
        `(action_totals, exposed_counts)`。
    """

    action_totals = np.zeros(3, dtype=np.float32)
    exposed_counts = np.zeros((RANGE_169_LENGTH, 3), dtype=np.float32)
    return (action_totals, exposed_counts)


def compute_unexposed_by_action(observation: PopulationBucketObservation) -> np.ndarray:
    """按动作计算未暴露样本数。

    Args:
        observation: 单个 bucket 观测对象。

    Returns:
        F/C/R 的未暴露样本向量, 形状 `[3]`。
    """

    exposed_by_action = observation.exposed_counts.sum(axis=0)
    return np.maximum(observation.action_totals - exposed_by_action, 0.0).astype(
        np.float32
    )


def load_population_dataset(
    action_totals_path: str,
    exposed_counts_path: str,
) -> list[PopulationBucketObservation]:
    """加载 population 训练数据并按 bucket 聚合。

    Args:
        action_totals_path: `action_totals.csv.gz` 路径。
        exposed_counts_path: `exposed_combo_counts.csv.gz` 路径。
            要求 `holdcard_index` 已是 169 维 hand class 桶索引。

    Returns:
        聚合后的 bucket 观测列表。
    """

    action_rows = _read_gzip_csv(action_totals_path)
    exposed_rows = _read_gzip_csv(exposed_counts_path)

    bucket_keys: set[tuple[int, int]] = set()
    bucket_keys.update(_parse_bucket_key(row) for row in action_rows)
    bucket_keys.update(_parse_bucket_key(row) for row in exposed_rows)
    
    # 每个 bucket 包含两个数组：
    # action_totals[3] — 3 个动作族（F/C/R）的总计数
    # exposed_counts[169, 3] — 169 手牌类型 × 3 动作的暴露计数
    bucket_arrays: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {
        bucket_key: _init_observation_arrays() for bucket_key in bucket_keys
    }

    for row in action_rows:
        key = _parse_bucket_key(row)
        action_family = row["action_family"].strip().upper()
        if action_family not in _ACTION_FAMILY_INDEX:
            continue
        action_index = _ACTION_FAMILY_INDEX[action_family]
        n_total = float(row["n_total"])
        action_totals, _ = bucket_arrays[key]
        action_totals[action_index] += n_total

    for row in exposed_rows:
        key = _parse_bucket_key(row)
        action_family = row["action_family"].strip().upper()
        if action_family not in _ACTION_FAMILY_INDEX:
            continue
        action_index = _ACTION_FAMILY_INDEX[action_family]
        holdcard_index = int(row["holdcard_index"])
        if holdcard_index < 0 or holdcard_index >= RANGE_169_LENGTH:
            msg = (
                "exposed_combo_counts holdcard_index 必须是 169 维桶索引, "
                f"当前值为 {holdcard_index}, 期望区间 [0, {RANGE_169_LENGTH - 1}]。"
            )
            raise ValueError(msg)
        hand_class = holdcard_index
        n_exposed = float(row["n_exposed"])
        _, exposed_counts = bucket_arrays[key]
        exposed_counts[hand_class, action_index] += n_exposed

    observations: list[PopulationBucketObservation] = []
    for table_type, param_index in sorted(bucket_arrays):
        action_totals, exposed_counts = bucket_arrays[(table_type, param_index)]
        observations.append(
            PopulationBucketObservation(
                table_type=table_type,
                param_index=param_index,
                action_totals=action_totals,
                exposed_counts=exposed_counts,
            )
        )
    return observations
