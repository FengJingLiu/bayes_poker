"""贝叶斯估计的三维行动概率数据结构。

移植自 G5.Logic (C#) 的 EstimatedAD.cs。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gaussian_distribution import GaussianDistribution

__all__ = ["EstimatedAD"]


@dataclass(frozen=True, slots=True)
class EstimatedAD:
    """贝叶斯估计的三维行动概率（均值 + 不确定性）。

    对应 G5 的 EstimatedAD：三维动作空间（BetRaise / CheckCall / Fold）
    各自以 GaussianDistribution（均值 + σ）的形式表达估计结果。

    Attributes:
        bet_raise: BetRaise 行动的高斯概率估计（合并 bet + raise）。
        check_call: CheckCall 行动的高斯概率估计。
        fold: Fold 行动的高斯概率估计（非强制行动节点为零均值）。
        prior_samples: 相似玩家贡献到先验的样本数量（k）。
        update_samples: 当前玩家自身用于后验更新的样本数量。
    """

    bet_raise: GaussianDistribution
    check_call: GaussianDistribution
    fold: GaussianDistribution
    prior_samples: int
    update_samples: int

    def __str__(self) -> str:
        return (
            f"BR: {self.bet_raise.mean:.4f}, "
            f"CC: {self.check_call.mean:.4f}, "
            f"FO: {self.fold.mean:.4f} "
            f"[prior={self.prior_samples}, update={self.update_samples}]"
        )
