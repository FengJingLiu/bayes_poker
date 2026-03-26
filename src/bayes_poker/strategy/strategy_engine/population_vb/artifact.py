"""population_vb 后验 artifact 读写工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast, get_args

import numpy as np

from .contracts import PopulationPosteriorBucket, PriorKind

_PRIOR_KIND_VALUES: set[str] = set(get_args(PriorKind))


def _parse_prior_kind(value: object) -> PriorKind:
    """校验并解析 `prior_kind`。

    Args:
        value: artifact 中读出的原始值。

    Returns:
        合法的 `PriorKind`。

    Raises:
        ValueError: 当值不在允许集合时抛出。
    """

    raw = str(value)
    if raw not in _PRIOR_KIND_VALUES:
        msg = f"artifact 中 prior_kind 值非法: {raw!r}"
        raise ValueError(msg)
    return cast(PriorKind, raw)


def _parse_exposure_model_meta(
    value: object,
) -> dict[str, int | float | str] | None:
    """校验并解析 `exposure_model_meta`。

    Args:
        value: artifact 中读出的 JSON 字符串值。

    Returns:
        合法的曝光模型元信息字典。空对象会返回空字典。

    Raises:
        ValueError: 当结构或字段类型不符合约束时抛出。
    """

    decoded = json.loads(str(value))
    if decoded is None:
        return None
    if not isinstance(decoded, dict):
        msg = f"artifact 中 exposure_model_meta 必须为对象, 实际为 {type(decoded)!r}"
        raise ValueError(msg)
    normalized: dict[str, int | float | str] = {}
    for key, item in decoded.items():
        if not isinstance(key, str):
            msg = f"exposure_model_meta key 必须为 str, 实际为 {type(key)!r}"
            raise ValueError(msg)
        if not isinstance(item, (int, float, str)):
            msg = (
                "exposure_model_meta value 必须为 int/float/str, "
                f"key={key!r}, 实际为 {type(item)!r}"
            )
            raise ValueError(msg)
        normalized[key] = item
    return normalized


def save_population_artifact(
    buckets: list[PopulationPosteriorBucket],
    output_path: str | Path,
    *,
    metadata: dict[str, object],
) -> None:
    """保存 population 后验 artifact。

    Args:
        buckets: 后验 bucket 列表。
        output_path: `.npz` 输出路径。
        metadata: 额外元信息字典。
    """

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    ordered_buckets = sorted(
        buckets,
        key=lambda bucket: (bucket.table_type, bucket.param_index),
    )
    if not ordered_buckets:
        np.savez_compressed(
            output,
            table_types=np.zeros(0, dtype=np.int32),
            param_indices=np.zeros(0, dtype=np.int32),
            alpha_fcr=np.zeros((0, 169, 3), dtype=np.float32),
            mean_fcr=np.zeros((0, 169, 3), dtype=np.float32),
            ess_by_hand=np.zeros((0, 169), dtype=np.float32),
            prior_kinds=np.zeros(0, dtype=np.str_),
            exposure_model_meta_json=np.zeros(0, dtype=np.str_),
            metadata_json=np.array(
                [json.dumps(metadata, ensure_ascii=False)],
                dtype=np.str_,
            ),
        )
        return

    np.savez_compressed(
        output,
        table_types=np.array(
            [bucket.table_type for bucket in ordered_buckets],
            dtype=np.int32,
        ),
        param_indices=np.array(
            [bucket.param_index for bucket in ordered_buckets],
            dtype=np.int32,
        ),
        alpha_fcr=np.stack(
            [bucket.alpha_fcr for bucket in ordered_buckets],
            axis=0,
        ).astype(np.float32),
        mean_fcr=np.stack(
            [bucket.mean_fcr for bucket in ordered_buckets],
            axis=0,
        ).astype(np.float32),
        ess_by_hand=np.stack(
            [bucket.ess_by_hand for bucket in ordered_buckets],
            axis=0,
        ).astype(np.float32),
        prior_kinds=np.array(
            [bucket.prior_kind for bucket in ordered_buckets],
            dtype=np.str_,
        ),
        exposure_model_meta_json=np.array(
            [
                json.dumps(bucket.exposure_model_meta or {}, ensure_ascii=False)
                for bucket in ordered_buckets
            ],
            dtype=np.str_,
        ),
        metadata_json=np.array(
            [json.dumps(metadata, ensure_ascii=False)],
            dtype=np.str_,
        ),
    )


def load_population_artifact(
    path: str | Path,
) -> dict[tuple[int, int], PopulationPosteriorBucket]:
    """加载 population 后验 artifact。

    Args:
        path: `.npz` artifact 路径。

    Returns:
        以 `(table_type, param_index)` 为 key 的后验 bucket 映射。
    """

    loaded = np.load(path, allow_pickle=False)
    table_types = loaded["table_types"]
    param_indices = loaded["param_indices"]
    alpha_fcr = loaded["alpha_fcr"]
    mean_fcr = loaded["mean_fcr"]
    ess_by_hand = loaded["ess_by_hand"]
    prior_kinds = loaded["prior_kinds"]
    exposure_model_meta_json = loaded["exposure_model_meta_json"]

    bucket_count = int(table_types.shape[0])
    if not (
        param_indices.shape[0]
        == alpha_fcr.shape[0]
        == mean_fcr.shape[0]
        == ess_by_hand.shape[0]
        == prior_kinds.shape[0]
        == exposure_model_meta_json.shape[0]
        == bucket_count
    ):
        msg = "artifact 内数组长度不一致, 无法恢复 bucket。"
        raise ValueError(msg)

    restored: dict[tuple[int, int], PopulationPosteriorBucket] = {}
    for index in range(bucket_count):
        table_type = int(table_types[index])
        param_index = int(param_indices[index])
        restored[(table_type, param_index)] = PopulationPosteriorBucket(
            table_type=table_type,
            param_index=param_index,
            alpha_fcr=np.array(alpha_fcr[index], dtype=np.float32),
            mean_fcr=np.array(mean_fcr[index], dtype=np.float32),
            ess_by_hand=np.array(ess_by_hand[index], dtype=np.float32),
            prior_kind=_parse_prior_kind(prior_kinds[index]),
            exposure_model_meta=_parse_exposure_model_meta(
                exposure_model_meta_json[index]
            ),
        )
    return restored
