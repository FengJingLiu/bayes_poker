"""population_vb 训练阶段的数据契约定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

ActionFamily = Literal["F", "C", "R"]
PriorKind = Literal["direct_gto", "pseudo_call_from_raise_ev"]


@dataclass(frozen=True, slots=True)
class PopulationBucketObservation:
    """单个 population 桶的观测数据。

    Attributes:
        table_type: 桌型编码。
        param_index: 翻前参数索引。
        action_totals: F/C/R 三类动作总量, 形状为 `[3]`。
        exposed_counts: 已暴露底牌计数, 形状为 `[169, 3]`。
    """

    table_type: int
    param_index: int
    action_totals: np.ndarray
    exposed_counts: np.ndarray


@dataclass(frozen=True, slots=True)
class GtoFamilyPrior:
    """单个 param family 的 GTO 先验。

    Attributes:
        table_type: 桌型编码。
        param_index: 翻前参数索引。
        probs_fcr: 每个 hand class 的 F/C/R 先验概率, 形状 `[169, 3]`。
        raise_score: 每个 hand class 的加注打分, 形状 `[169]`。
        prior_kind: 先验来源类型。
    """

    table_type: int
    param_index: int
    probs_fcr: np.ndarray
    raise_score: np.ndarray
    prior_kind: PriorKind


@dataclass(frozen=True, slots=True)
class PopulationPosteriorBucket:
    """单个 bucket 的后验参数。

    Attributes:
        table_type: 桌型编码。
        param_index: 翻前参数索引。
        alpha_fcr: Dirichlet 后验参数, 形状 `[169, 3]`。
        mean_fcr: Dirichlet 后验均值, 形状 `[169, 3]`。
        ess_by_hand: 每个 hand class 的有效样本量, 形状 `[169]`。
        prior_kind: 先验来源类型。
        exposure_model_meta: 曝光模型元信息。
    """

    table_type: int
    param_index: int
    alpha_fcr: np.ndarray
    mean_fcr: np.ndarray
    ess_by_hand: np.ndarray
    prior_kind: PriorKind
    exposure_model_meta: dict[str, int | float | str] | None = None
