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

    def debug_str(self, *, top_n: int | None = None, sort_by: str = "raise") -> str:
        """将 exposed_counts 以手牌字符串格式输出，便于调试。

        Args:
            top_n: 仅输出前 N 个手牌; None 表示输出全部 169 个。
            sort_by: 排序依据列, 可选 "fold" / "call" / "raise"。

        Returns:
            格式化调试字符串。
        """
        from bayes_poker.strategy.range.mappings import RANGE_169_ORDER

        col = {"fold": 0, "call": 1, "raise": 2}.get(sort_by, 2)
        indices = sorted(
            range(len(RANGE_169_ORDER)),
            key=lambda i: float(self.exposed_counts[i, col]),
            reverse=True,
        )
        if top_n is not None:
            indices = indices[:top_n]
        tt, pi = self.table_type, self.param_index
        f0, c0, r0 = self.action_totals[0], self.action_totals[1], self.action_totals[2]
        lines: list[str] = [
            f"PopulationBucketObservation(table_type={tt}, param_index={pi})",
            f"  action_totals: F={f0:.0f}  C={c0:.0f}  R={r0:.0f}",
            "  exposed_counts (hand: fold / call / raise):",
        ]
        for i in indices:
            hand = RANGE_169_ORDER[i]
            f, c, r = self.exposed_counts[i]
            lines.append(f"    {hand:<5}: F={f:>9.0f}  C={c:>9.0f}  R={r:>9.0f}")
        return "\n".join(lines)


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

    def debug_str(self, *, top_n: int | None = None, sort_by: str = "raise") -> str:
        """将 probs_fcr 和 raise_score 以手牌字符串格式输出，便于调试。

        Args:
            top_n: 仅输出前 N 个手牌; None 表示输出全部 169 个。
            sort_by: 排序依据列, 可选 "fold" / "call" / "raise"。

        Returns:
            格式化调试字符串。
        """
        from bayes_poker.strategy.range.mappings import RANGE_169_ORDER

        col = {"fold": 0, "call": 1, "raise": 2}.get(sort_by, 2)
        indices = sorted(
            range(len(RANGE_169_ORDER)),
            key=lambda i: float(self.probs_fcr[i, col]),
            reverse=True,
        )
        if top_n is not None:
            indices = indices[:top_n]
        tt, pi, pk = self.table_type, self.param_index, self.prior_kind
        lines: list[str] = [
            f"GtoFamilyPrior(table_type={tt}, param_index={pi}, prior_kind={pk!r})",
            "  probs_fcr (hand: F / C / R) | raise_score:",
        ]
        for i in indices:
            hand = RANGE_169_ORDER[i]
            f, c, r = self.probs_fcr[i]
            rs = self.raise_score[i]
            row = f"    {hand:<5}: F={f:.7f}  C={c:.7f}  R={r:.7f}  score={rs:+.7f}"
            lines.append(row)
        return "\n".join(lines)


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

    def debug_str(self, *, top_n: int | None = None, sort_by: str = "raise") -> str:
        """将 mean_fcr / alpha_fcr / ess_by_hand 以手牌字符串格式输出，便于调试。

        Args:
            top_n: 仅输出前 N 个手牌; None 表示输出全部 169 个。
            sort_by: 排序依据列, 可选 "fold" / "call" / "raise"。

        Returns:
            格式化调试字符串。
        """
        from bayes_poker.strategy.range.mappings import RANGE_169_ORDER

        col = {"fold": 0, "call": 1, "raise": 2}.get(sort_by, 2)
        indices = sorted(
            range(len(RANGE_169_ORDER)),
            key=lambda i: float(self.mean_fcr[i, col]),
            reverse=True,
        )
        if top_n is not None:
            indices = indices[:top_n]
        tt, pi, pk = self.table_type, self.param_index, self.prior_kind
        lines: list[str] = [
            f"PosteriorBucket(tt={tt}, pi={pi}, prior_kind={pk!r})",
            "  mean_fcr (hand: F / C / R) | ess:",
        ]
        for i in indices:
            hand = RANGE_169_ORDER[i]
            f, c, r = self.mean_fcr[i]
            ess = self.ess_by_hand[i]
            row = f"    {hand:<5}: F={f:.4f}  C={c:.4f}  R={r:.4f}  ess={ess:.1f}"
            lines.append(row)
        return "\n".join(lines)
