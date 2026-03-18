"""G5 风格对手贝叶斯行动估计器。

基于 VPIP/PFR/Aggression/WTP 四维相似度，从历史玩家池中
找到风格相近的对手，构建 HistDistribution 先验，再用玩家
自身样本做贝叶斯后验更新，输出三维 GaussianDistribution。

移植自 G5.Logic (C#) 的 OpponentModeling.cs。
"""

from __future__ import annotations

from collections.abc import Callable
import math
import random
from dataclasses import dataclass

import numpy as np

from .builder import calculate_aggression, calculate_pfr, calculate_wtp
from .estimated_ad import EstimatedAD
from .enums import TableType
from .gaussian_distribution import GaussianDistribution
from .hist_distribution import HistDistribution
from .models import ActionStats, PlayerMetricsSummary, PlayerStats
from .params import PostFlopParams, PreFlopParams

__all__ = [
    "DifferencePair",
    "OpponentEstimator",
    "OpponentEstimatorOptions",
]

# ──────────────────────────────────────────
# 配置与辅助数据类
# ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OpponentEstimatorOptions:
    """OpponentEstimator 的超参数配置。

    Attributes:
        prior_num_bins: 先验直方图分桶数量。
        min_samples: 玩家被纳入先验所需的最少样本数。
        max_similar_players: 每次估计时最多参考的相似玩家数。
        max_difference: 允许的最大归一化 L2 距离（首个相似玩家除外）。
        max_base_stats_sigma: BaseModel 中统计 sigma 的最大允许值（高 sigma 表示数据不足）。
        max_update_samples: 当前玩家样本上限（截断防止 confidence 过高）。
    """

    prior_num_bins: int = 100
    min_samples: int = 20
    max_similar_players: int = 130
    max_difference: float = 0.3
    max_base_stats_sigma: float = 0.08
    max_update_samples: int = 300


@dataclass(slots=True)
class _BaseModel:
    """玩家在 VPIP/PFR/Aggression/WTP 四维上的高斯估计。"""

    vpip: GaussianDistribution
    pfr: GaussianDistribution
    aggression: GaussianDistribution
    wtp: GaussianDistribution


@dataclass(frozen=True, slots=True)
class DifferencePair:
    """玩家池中某玩家与目标玩家的归一化 L2 距离。

    Attributes:
        index: 玩家在 `_summaries` 中的索引.
        difference: 归一化距离（越小越相似）。
    """

    index: int
    difference: float


# ──────────────────────────────────────────
# OpponentEstimator
# ──────────────────────────────────────────


class OpponentEstimator:
    """基于相似玩家的贝叶斯行动估计器。

    初始化时构建四个全局先验直方图（VPIP/PFR/Aggression/WTP），
    并为玩家池中每个玩家预计算 BaseModel。

    使用方式：
        estimator = OpponentEstimator(player_stats_list, TableType.SIX_MAX)
        preflop_ads, postflop_ads = estimator.estimate_player_model(player_stats)
    """

    def __init__(
        self,
        player_stats_list: list[PlayerStats],
        table_type: TableType,
        options: OpponentEstimatorOptions | None = None,
        *,
        random_seed: int | None = None,
    ) -> None:
        """初始化估计器，构建全局先验直方图与各玩家 BaseModel。

        Args:
            player_stats_list: 玩家池统计列表（来自 PlayerStatsRepository）。
            table_type: 桌型（影响 PreFlopParams/PostFlopParams 参数空间）。
            options: 超参数配置，None 时使用默认值。
            random_seed: 随机数种子，指定后保证可复现性。
        """
        self._initialize_common_state(
            table_type=table_type,
            options=options,
            random_seed=random_seed,
        )
        self._stats_list = [
            stats
            for stats in player_stats_list
            if not stats.player_name.casefold().startswith("aggregated_")
        ]
        self._summaries = [
            self._build_summary_from_stats(stats) for stats in self._stats_list
        ]
        self._stats_cache: dict[str, PlayerStats | None] = {
            stats.player_name: stats for stats in self._stats_list
        }
        self._stats_loader: Callable[[str], PlayerStats | None] = self._stats_cache.get
        self._initialize_priors_and_base_models()

    @classmethod
    def from_summaries(
        cls,
        summaries: list[PlayerMetricsSummary],
        *,
        table_type: TableType,
        stats_loader: Callable[[str], PlayerStats | None],
        options: OpponentEstimatorOptions | None = None,
        random_seed: int | None = None,
    ) -> OpponentEstimator:
        """从轻量 summary 列表构建估计器.

        Args:
            summaries: 玩家轻量指标列表.
            table_type: 桌型.
            stats_loader: 按玩家名懒加载完整 `PlayerStats` 的回调.
            options: 超参数配置, None 时使用默认值.
            random_seed: 随机数种子.

        Returns:
            初始化完成的 `OpponentEstimator`.
        """

        estimator = cls.__new__(cls)
        estimator._initialize_common_state(
            table_type=table_type,
            options=options,
            random_seed=random_seed,
        )
        estimator._stats_list = []
        estimator._summaries = [
            summary
            for summary in summaries
            if not summary.player_name.casefold().startswith("aggregated_")
        ]
        estimator._stats_cache = {}
        estimator._stats_loader = stats_loader
        estimator._initialize_priors_and_base_models()
        return estimator

    def _initialize_common_state(
        self,
        *,
        table_type: TableType,
        options: OpponentEstimatorOptions | None,
        random_seed: int | None,
    ) -> None:
        """初始化与数据源无关的公共状态.

        Args:
            table_type: 桌型.
            options: 超参数配置.
            random_seed: 随机数种子.

        Returns:
            None.
        """

        self._options = options or OpponentEstimatorOptions()
        if self._options.prior_num_bins <= 0:
            raise ValueError("prior_num_bins 必须大于 0")
        if self._options.min_samples <= 0:
            raise ValueError("min_samples 必须大于 0")
        if self._options.max_similar_players <= 0:
            raise ValueError("max_similar_players 必须大于 0")
        if self._options.max_difference < 0.0:
            raise ValueError("max_difference 不能为负数")
        if self._options.max_base_stats_sigma < 0.0:
            raise ValueError("max_base_stats_sigma 不能为负数")
        if self._options.max_update_samples < 0:
            raise ValueError("max_update_samples 不能为负数")
        self._table_type = table_type
        self._rng = random.Random(random_seed)

    def _initialize_priors_and_base_models(self) -> None:
        """基于当前 summary 列表构建先验与 base models.

        Returns:
            None.
        """

        self._vpip_prior = self._create_vpip_prior()
        self._pfr_prior = self._create_pfr_prior()
        self._aggression_prior = self._create_aggression_prior()
        self._wtp_prior = self._create_wtp_prior()

        self._base_models: list[_BaseModel | None] = [
            self._estimate_base_model_from_summary(summary)
            for summary in self._summaries
        ]
        self._build_numpy_cache()

    def _build_numpy_cache(self) -> None:
        """为相似度搜索构建 NumPy 向量化缓存。

        对 `None` base model 使用 `NaN` 占位，并单独维护有效掩码。

        Returns:
            None.
        """

        size = len(self._base_models)
        self._np_vpip_m = np.full(size, np.nan, dtype=np.float32)
        self._np_vpip_s = np.full(size, np.nan, dtype=np.float32)
        self._np_pfr_m = np.full(size, np.nan, dtype=np.float32)
        self._np_pfr_s = np.full(size, np.nan, dtype=np.float32)
        self._np_agg_m = np.full(size, np.nan, dtype=np.float32)
        self._np_agg_s = np.full(size, np.nan, dtype=np.float32)
        self._np_wtp_m = np.full(size, np.nan, dtype=np.float32)
        self._np_wtp_s = np.full(size, np.nan, dtype=np.float32)
        self._np_valid_mask = np.zeros(size, dtype=bool)

        for index, base_model in enumerate(self._base_models):
            if base_model is None:
                continue
            self._np_valid_mask[index] = True
            self._np_vpip_m[index] = np.float32(base_model.vpip.mean)
            self._np_vpip_s[index] = np.float32(base_model.vpip.sigma)
            self._np_pfr_m[index] = np.float32(base_model.pfr.mean)
            self._np_pfr_s[index] = np.float32(base_model.pfr.sigma)
            self._np_agg_m[index] = np.float32(base_model.aggression.mean)
            self._np_agg_s[index] = np.float32(base_model.aggression.sigma)
            self._np_wtp_m[index] = np.float32(base_model.wtp.mean)
            self._np_wtp_s[index] = np.float32(base_model.wtp.sigma)

    def _has_numpy_cache(self) -> bool:
        """返回当前实例是否已构建 NumPy 缓存。

        Returns:
            若缓存存在且长度匹配，则返回 `True`。
        """

        if not hasattr(self, "_np_valid_mask"):
            return False
        return len(self._np_valid_mask) == len(self._base_models)

    def _normalized_difference_array(
        self,
        target_mean: np.float32,
        target_sigma: np.float32,
        means: np.ndarray,
        sigmas: np.ndarray,
    ) -> np.ndarray:
        """计算目标统计与玩家池统计的逐元素归一化差值。

        当分母为 0 时，均值也相同的项记为 0，不同的项记为 `inf`。

        Args:
            target_mean: 目标均值。
            target_sigma: 目标标准差。
            means: 玩家池均值数组。
            sigmas: 玩家池标准差数组。

        Returns:
            与输入同形状的归一化差值数组。
        """

        numerator = np.abs(target_mean - means)
        denominator = np.sqrt(target_sigma**2 + sigmas**2)
        diff = np.divide(
            numerator,
            denominator,
            out=np.zeros_like(numerator, dtype=np.float32),
            where=denominator > 0.0,
        )
        zero_sigma_mask = (denominator == 0.0) & (numerator > 0.0)
        diff[zero_sigma_mask] = np.float32(np.inf)
        return diff

    def _normalized_difference_scalar(
        self,
        target: GaussianDistribution,
        other: GaussianDistribution,
    ) -> float:
        """计算两个高斯统计的标量归一化差值。

        当分母为 0 时，均值也相同则返回 0，不同则返回 `inf`。

        Args:
            target: 目标高斯统计。
            other: 玩家池中的高斯统计。

        Returns:
            归一化差值。
        """

        numerator = abs(target.mean - other.mean)
        denominator = math.sqrt(target.sigma**2 + other.sigma**2)
        if denominator > 0.0:
            return numerator / denominator
        if numerator == 0.0:
            return 0.0
        return math.inf

    def _select_top_difference_pairs(self, distances: np.ndarray) -> list[DifferencePair]:
        """从距离数组中选出最相近的玩家。

        仅保留有效 base model 且距离非 NaN 的候选项。
        按距离升序排列；距离相同时按原始索引升序（稳定 tie-break，与标量路径一致）。

        Args:
            distances: 全量玩家距离数组（float32/float64）。

        Returns:
            距离升序排列的 `DifferencePair` 列表。
        """

        valid_indices = np.flatnonzero(self._np_valid_mask)
        if len(valid_indices) == 0:
            return []

        distances_valid = np.asarray(distances[self._np_valid_mask], dtype=np.float64)

        # 过滤 NaN（分母为 0 且分子也为 0 时产生）
        finite_mask = ~np.isnan(distances_valid)
        valid_indices = valid_indices[finite_mask]
        distances_valid = distances_valid[finite_mask]

        max_candidates = min(self._options.max_similar_players, len(distances_valid))
        if max_candidates == 0:
            return []

        # lexsort 按 (distance, original_index) 双键稳定排序，与 Python 标量路径完全等价
        order = np.lexsort((valid_indices, distances_valid))[:max_candidates]

        return [
            DifferencePair(
                index=int(valid_indices[i]),
                difference=float(distances_valid[i]),
            )
            for i in order
        ]

    def _build_summary_from_stats(self, stats: PlayerStats) -> PlayerMetricsSummary:
        """从完整统计提取轻量 summary.

        Args:
            stats: 完整玩家统计.

        Returns:
            轻量 summary.
        """

        pfr_pos, pfr_total = calculate_pfr(stats)
        agg_pos, agg_total = calculate_aggression(stats)
        wtp_pos, wtp_total = calculate_wtp(stats)
        return PlayerMetricsSummary(
            player_name=stats.player_name,
            table_type=stats.table_type,
            total_hands=stats.vpip.total,
            vpip_pos=stats.vpip.positive,
            vpip_total=stats.vpip.total,
            pfr_pos=pfr_pos,
            pfr_total=pfr_total,
            agg_pos=agg_pos,
            agg_total=agg_total,
            wtp_pos=wtp_pos,
            wtp_total=wtp_total,
        )

    # ──────────────────────────────────────────
    # 全局先验构建（对应 G5 initBaseStats 四个 create* 方法）
    # ──────────────────────────────────────────

    def _create_vpip_prior(self) -> HistDistribution:
        """构建 VPIP 全局先验直方图.

        Returns:
            VPIP 先验直方图.
        """

        dist = HistDistribution(self._options.prior_num_bins)
        for summary in self._summaries:
            if summary.vpip_total > self._options.min_samples:
                dist.add_sample(summary.vpip_pos / summary.vpip_total)
        dist.normalize()
        return dist

    def _create_pfr_prior(self) -> HistDistribution:
        """构建 PFR 全局先验直方图.

        Returns:
            PFR 先验直方图.
        """

        dist = HistDistribution(self._options.prior_num_bins)
        for summary in self._summaries:
            if summary.pfr_total > self._options.min_samples:
                dist.add_sample(summary.pfr_pos / summary.pfr_total)
        dist.normalize()
        return dist

    def _create_aggression_prior(self) -> HistDistribution:
        """构建 Aggression 全局先验直方图.

        Returns:
            Aggression 先验直方图.
        """

        dist = HistDistribution(self._options.prior_num_bins)
        for summary in self._summaries:
            if summary.agg_total > self._options.min_samples:
                dist.add_sample(summary.agg_pos / summary.agg_total)
        dist.normalize()
        return dist

    def _create_wtp_prior(self) -> HistDistribution:
        """构建 WTP 全局先验直方图.

        Returns:
            WTP 先验直方图.
        """

        dist = HistDistribution(self._options.prior_num_bins)
        for summary in self._summaries:
            if summary.wtp_total > self._options.min_samples:
                dist.add_sample(summary.wtp_pos / summary.wtp_total)
        dist.normalize()
        return dist

    # ──────────────────────────────────────────
    # BaseModel 估计（对应 G5 estimateBaseModel）
    # ──────────────────────────────────────────

    def _estimate_base_model(self, stats: PlayerStats) -> _BaseModel | None:
        """为单个玩家构建 BaseModel（四维高斯估计）。

        样本数不足时返回 None，表示该玩家不参与相似度排序。
        """
        return self._estimate_base_model_from_summary(
            self._build_summary_from_stats(stats)
        )

    def _estimate_base_model_from_summary(
        self,
        summary: PlayerMetricsSummary,
    ) -> _BaseModel | None:
        """为单个 summary 构建 BaseModel.

        若 summary 携带预计算的高斯参数（`has_base_model() == True`），
        直接从参数构建，跳过贝叶斯直方图更新（极快）。
        否则退回到完整的 `_estimate_gaussian` 计算路径。

        Args:
            summary: 玩家轻量指标摘要.

        Returns:
            样本不足时返回 `None`, 否则返回 `_BaseModel`.
        """

        vpip_total = summary.vpip_total
        if vpip_total <= 0:
            return None

        if summary.has_base_model():
            # 快路径：直接从预计算参数构建
            return _BaseModel(
                vpip=GaussianDistribution(
                    mean=summary.vpip_mean,  # type: ignore[arg-type]
                    sigma=summary.vpip_sigma,  # type: ignore[arg-type]
                ),
                pfr=GaussianDistribution(
                    mean=summary.pfr_mean,  # type: ignore[arg-type]
                    sigma=summary.pfr_sigma,  # type: ignore[arg-type]
                ),
                aggression=GaussianDistribution(
                    mean=summary.agg_mean,  # type: ignore[arg-type]
                    sigma=summary.agg_sigma,  # type: ignore[arg-type]
                ),
                wtp=GaussianDistribution(
                    mean=summary.wtp_mean,  # type: ignore[arg-type]
                    sigma=summary.wtp_sigma,  # type: ignore[arg-type]
                ),
            )

        vpip_gauss = self._estimate_gaussian(
            self._vpip_prior,
            summary.vpip_pos,
            vpip_total,
        )

        pfr_gauss = self._estimate_gaussian(
            self._pfr_prior,
            summary.pfr_pos,
            summary.pfr_total,
        )

        agg_gauss = self._estimate_gaussian(
            self._aggression_prior,
            summary.agg_pos,
            summary.agg_total,
        )

        wtp_gauss = self._estimate_gaussian(
            self._wtp_prior,
            summary.wtp_pos,
            summary.wtp_total,
        )

        return _BaseModel(
            vpip=vpip_gauss,
            pfr=pfr_gauss,
            aggression=agg_gauss,
            wtp=wtp_gauss,
        )

    # ──────────────────────────────────────────
    # 贝叶斯更新（对应 G5 estimateGaussian + updateDistributionRandom）
    # ──────────────────────────────────────────

    def _estimate_gaussian(
        self,
        prior: HistDistribution,
        positive: int,
        total: int,
    ) -> GaussianDistribution:
        """用玩家样本对先验直方图做贝叶斯更新，返回高斯拟合。

        精确复制 G5 逻辑：
        1. 截断样本数到 max_update_samples（防止 confidence 过高）。
        2. 分批随机交错更新（每批 ≤100 个，保证随机顺序）。
        3. FitGaussian 返回 GaussianDistribution。

        Args:
            prior: 先验直方图（不会被修改，内部创建副本）。
            positive: 正样本数。
            total: 总样本数。

        Returns:
            后验高斯拟合。
        """
        new_dist = HistDistribution.copy_from(prior)

        if total > self._options.max_update_samples:
            positive = (self._options.max_update_samples * positive) // total
            total = self._options.max_update_samples

        pos = positive
        neg = total - positive

        while pos + neg > 0:
            remaining = pos + neg
            if remaining <= 100:
                self._update_distribution_random(new_dist, pos, neg)
                pos = 0
                neg = 0
            else:
                batch_pos = int(100 * pos / remaining)
                batch_neg = int(100 * neg / remaining)
                self._update_distribution_random(new_dist, batch_pos, batch_neg)
                pos -= batch_pos
                neg -= batch_neg

        return new_dist.fit_gaussian()

    def _update_distribution_random(
        self,
        dist: HistDistribution,
        pos: int,
        neg: int,
    ) -> None:
        """随机交错发送正/负样本到直方图。

        对应 G5 updateDistributionRandom：以正样本比例随机决定
        每次发送正或负样本，消除顺序偏差。

        Args:
            dist: 待更新的直方图（原地修改）。
            pos: 剩余正样本数。
            neg: 剩余负样本数。
        """
        while pos + neg > 0:
            if pos > 0 and self._rng.random() < pos / (pos + neg):
                dist.update(True)
                pos -= 1
            else:
                dist.update(False)
                neg -= 1

    # ──────────────────────────────────────────
    # 相似玩家搜索（对应 G5 getSimilarOpponents_PreFlop/PostFlop）
    # ──────────────────────────────────────────

    def _get_similar_opponents_preflop(
        self,
        base_model: _BaseModel,
    ) -> list[DifferencePair]:
        """按 VPIP + PFR 的归一化 L2 距离排序，返回最相近玩家。

        Args:
            base_model: 目标玩家的 BaseModel。

        Returns:
            按距离升序排列的 DifferencePair 列表。
        """
        if not self._has_numpy_cache():
            pairs: list[DifferencePair] = []
            for index, other_base_model in enumerate(self._base_models):
                if other_base_model is None:
                    continue
                vpip_diff = self._normalized_difference_scalar(
                    base_model.vpip,
                    other_base_model.vpip,
                )
                pfr_diff = self._normalized_difference_scalar(
                    base_model.pfr,
                    other_base_model.pfr,
                )
                dist = math.sqrt(vpip_diff**2 + pfr_diff**2)
                pairs.append(DifferencePair(index=index, difference=dist))
            pairs.sort(key=lambda pair: pair.difference)
            return pairs[: self._options.max_similar_players]

        target_vpip_mean = np.float32(base_model.vpip.mean)
        target_vpip_sigma = np.float32(base_model.vpip.sigma)
        target_pfr_mean = np.float32(base_model.pfr.mean)
        target_pfr_sigma = np.float32(base_model.pfr.sigma)

        vpip_diff = self._normalized_difference_array(
            target_vpip_mean,
            target_vpip_sigma,
            self._np_vpip_m,
            self._np_vpip_s,
        )
        pfr_diff = self._normalized_difference_array(
            target_pfr_mean,
            target_pfr_sigma,
            self._np_pfr_m,
            self._np_pfr_s,
        )
        distances = np.sqrt(vpip_diff**2 + pfr_diff**2)
        return self._select_top_difference_pairs(distances)

    def _get_similar_opponents_postflop(
        self,
        base_model: _BaseModel,
    ) -> list[DifferencePair]:
        """按 Aggression + WTP 的归一化 L2 距离排序，返回最相近玩家。

        Args:
            base_model: 目标玩家的 BaseModel。

        Returns:
            按距离升序排列的 DifferencePair 列表。
        """
        if not self._has_numpy_cache():
            pairs: list[DifferencePair] = []
            for index, other_base_model in enumerate(self._base_models):
                if other_base_model is None:
                    continue
                agg_diff = self._normalized_difference_scalar(
                    base_model.aggression,
                    other_base_model.aggression,
                )
                wtp_diff = self._normalized_difference_scalar(
                    base_model.wtp,
                    other_base_model.wtp,
                )
                dist = math.sqrt(agg_diff**2 + wtp_diff**2)
                pairs.append(DifferencePair(index=index, difference=dist))
            pairs.sort(key=lambda pair: pair.difference)
            return pairs[: self._options.max_similar_players]

        target_agg_mean = np.float32(base_model.aggression.mean)
        target_agg_sigma = np.float32(base_model.aggression.sigma)
        target_wtp_mean = np.float32(base_model.wtp.mean)
        target_wtp_sigma = np.float32(base_model.wtp.sigma)

        agg_diff = self._normalized_difference_array(
            target_agg_mean,
            target_agg_sigma,
            self._np_agg_m,
            self._np_agg_s,
        )
        wtp_diff = self._normalized_difference_array(
            target_wtp_mean,
            target_wtp_sigma,
            self._np_wtp_m,
            self._np_wtp_s,
        )
        distances = np.sqrt(agg_diff**2 + wtp_diff**2)
        return self._select_top_difference_pairs(distances)

    # ──────────────────────────────────────────
    # AD 估计（对应 G5 estimateADPreFLop/PostFlop）
    # ──────────────────────────────────────────

    def _load_player_stats(self, player_name: str) -> PlayerStats | None:
        """按玩家名懒加载完整统计.

        Args:
            player_name: 玩家名.

        Returns:
            完整 `PlayerStats`, 不存在时返回 `None`.
        """

        if player_name not in self._stats_cache:
            self._stats_cache[player_name] = self._stats_loader(player_name)
        return self._stats_cache[player_name]

    def _collect_prior_action_stats(
        self,
        player_stats: PlayerStats,
        sorted_opponents: list[DifferencePair],
        params_list: list[PreFlopParams] | list[PostFlopParams],
        *,
        is_preflop: bool,
    ) -> list[tuple[HistDistribution, HistDistribution, HistDistribution, int]]:
        """从相似玩家构建翻前或翻后各情境的先验直方图元组列表。

        每个情境返回 (bet_raise_dist, check_call_dist, fold_dist, prior_k)。

        Args:
            player_stats: 目标玩家统计（用于过滤自身）。
            sorted_opponents: 按距离升序排列的相似玩家列表。
            params_list: 所有情境参数列表。
            is_preflop: True 表示翻前，False 表示翻后。

        Returns:
            与 params_list 等长的先验三元组 + k 值列表。
        """
        opts = self._options
        n = len(params_list)
        br_dists = [HistDistribution(opts.prior_num_bins) for _ in range(n)]
        cc_dists = [HistDistribution(opts.prior_num_bins) for _ in range(n)]
        fo_dists = [HistDistribution(opts.prior_num_bins) for _ in range(n)]
        prior_k_list = [0] * n

        cumulative = [ActionStats() for _ in range(n)]
        cumulative_k = 0

        k = 0
        for pair in sorted_opponents:
            if k >= opts.max_similar_players:
                break
            if k > 0 and pair.difference >= opts.max_difference:
                break

            bm = self._base_models[pair.index]
            if bm is None:
                continue

            sigma_check = bm.vpip.sigma if is_preflop else bm.aggression.sigma
            if sigma_check >= opts.max_base_stats_sigma:
                continue

            opponent_name = self._summaries[pair.index].player_name
            if opponent_name == player_stats.player_name:
                continue

            opponent = self._load_player_stats(opponent_name)
            if opponent is None or opponent.player_name != opponent_name:
                continue

            for idx, params in enumerate(params_list):
                if is_preflop:
                    action_stats = opponent.get_preflop_stats(params)  # type: ignore[arg-type]
                else:
                    action_stats = opponent.get_postflop_stats(params)  # type: ignore[arg-type]

                total = action_stats.total_samples()
                if total > opts.min_samples:
                    br_rate = action_stats.bet_raise_samples / total
                    cc_rate = action_stats.check_call_samples / total
                    fo_rate = action_stats.fold_samples / total
                    br_dists[idx].add_sample(br_rate)
                    cc_dists[idx].add_sample(cc_rate)
                    fo_dists[idx].add_sample(fo_rate)
                    prior_k_list[idx] += 1
                else:
                    cumulative[idx].append(action_stats)

            cumulative_k += 1
            if cumulative_k >= opts.min_samples:
                for idx in range(n):
                    cum = cumulative[idx]
                    cum_total = cum.total_samples()
                    if cum_total > 0:
                        br_rate = cum.bet_raise_samples / cum_total
                        cc_rate = cum.check_call_samples / cum_total
                        fo_rate = cum.fold_samples / cum_total
                        br_dists[idx].add_sample(br_rate)
                        cc_dists[idx].add_sample(cc_rate)
                        fo_dists[idx].add_sample(fo_rate)
                        prior_k_list[idx] += 1
                    cumulative[idx].clear()
                cumulative_k = 0

            k += 1

        for idx in range(n):
            br_dists[idx].normalize()
            cc_dists[idx].normalize()
            fo_dists[idx].normalize()

        return [(br_dists[idx], cc_dists[idx], fo_dists[idx], prior_k_list[idx]) for idx in range(n)]

    def _estimate_ad_for_params(
        self,
        player_stats: PlayerStats,
        br_dist: HistDistribution,
        cc_dist: HistDistribution,
        fo_dist: HistDistribution,
        prior_k: int,
        action_stats: ActionStats,
        *,
        forced_action: bool,
    ) -> EstimatedAD:
        """对单个情境节点执行贝叶斯后验更新，输出 EstimatedAD。

        精确复制 G5 estimateADPreFLop/PostFlop 的后验更新与归一化逻辑。

        Args:
            player_stats: 目标玩家（仅用于记录 update_samples）。
            br_dist: BetRaise 先验直方图。
            cc_dist: CheckCall 先验直方图。
            fo_dist: Fold 先验直方图。
            prior_k: 先验样本数量。
            action_stats: 当前玩家在该节点的原始 ActionStats。
            forced_action: True 表示强制行动节点（三维归一化），
                           False 表示非强制节点（fold 置零，二维归一化）。

        Returns:
            EstimatedAD。
        """
        total = action_stats.total_samples()

        br_gauss = self._estimate_gaussian(br_dist, action_stats.bet_raise_samples, total)
        cc_gauss = self._estimate_gaussian(cc_dist, action_stats.check_call_samples, total)
        fo_gauss = self._estimate_gaussian(fo_dist, action_stats.fold_samples, total)

        if forced_action:
            total_mean = br_gauss.mean + cc_gauss.mean + fo_gauss.mean
            if total_mean > 0.0:
                scale = 1.0 / total_mean
                br_gauss = br_gauss.scale(scale)
                cc_gauss = cc_gauss.scale(scale)
                fo_gauss = fo_gauss.scale(scale)
        else:
            zero = GaussianDistribution(mean=0.0, sigma=0.0)
            fo_gauss = zero
            total_mean = br_gauss.mean + cc_gauss.mean
            if total_mean > 0.0:
                scale = 1.0 / total_mean
                br_gauss = br_gauss.scale(scale)
                cc_gauss = cc_gauss.scale(scale)

        return EstimatedAD(
            bet_raise=br_gauss,
            check_call=cc_gauss,
            fold=fo_gauss,
            prior_samples=prior_k,
            update_samples=total,
        )

    def _estimate_ad_preflop(
        self,
        player_stats: PlayerStats,
        sorted_opponents: list[DifferencePair],
        params: PreFlopParams,
        br_dist: HistDistribution,
        cc_dist: HistDistribution,
        fo_dist: HistDistribution,
        prior_k: int,
    ) -> EstimatedAD:
        action_stats = player_stats.get_preflop_stats(params)
        return self._estimate_ad_for_params(
            player_stats,
            br_dist,
            cc_dist,
            fo_dist,
            prior_k,
            action_stats,
            forced_action=params.forced_action(),
        )

    def _estimate_ad_postflop(
        self,
        player_stats: PlayerStats,
        sorted_opponents: list[DifferencePair],
        params: PostFlopParams,
        br_dist: HistDistribution,
        cc_dist: HistDistribution,
        fo_dist: HistDistribution,
        prior_k: int,
    ) -> EstimatedAD:
        action_stats = player_stats.get_postflop_stats(params)
        return self._estimate_ad_for_params(
            player_stats,
            br_dist,
            cc_dist,
            fo_dist,
            prior_k,
            action_stats,
            forced_action=params.forced_action(),
        )

    # ──────────────────────────────────────────
    # 公共入口
    # ──────────────────────────────────────────

    def estimate_player_model(
        self,
        player_stats: PlayerStats,
    ) -> tuple[list[EstimatedAD], list[EstimatedAD]]:
        """估计玩家在所有翻前/翻后情境下的行动概率。

        对应 G5 estimatePlayerModel。

        Args:
            player_stats: 目标玩家统计数据。

        Returns:
            元组 (preflop_ads, postflop_ads)，
            分别与 PreFlopParams.get_all_params() 和
            PostFlopParams.get_all_params() 的情境列表一一对应。
        """
        base_model = self._estimate_base_model(player_stats)
        if base_model is None:
            base_model = _BaseModel(
                vpip=GaussianDistribution(mean=0.25, sigma=0.5),
                pfr=GaussianDistribution(mean=0.15, sigma=0.5),
                aggression=GaussianDistribution(mean=0.3, sigma=0.5),
                wtp=GaussianDistribution(mean=0.5, sigma=0.5),
            )

        sorted_pre = self._get_similar_opponents_preflop(base_model)
        sorted_post = self._get_similar_opponents_postflop(base_model)

        preflop_params = list(PreFlopParams.get_all_params(self._table_type))
        postflop_params = list(PostFlopParams.get_all_params(self._table_type))

        preflop_priors = self._collect_prior_action_stats(
            player_stats,
            sorted_pre,
            preflop_params,  # type: ignore[arg-type]
            is_preflop=True,
        )
        postflop_priors = self._collect_prior_action_stats(
            player_stats,
            sorted_post,
            postflop_params,  # type: ignore[arg-type]
            is_preflop=False,
        )

        preflop_ads = [
            self._estimate_ad_preflop(
                player_stats,
                sorted_pre,
                params,
                br_dist,
                cc_dist,
                fo_dist,
                prior_k,
            )
            for params, (br_dist, cc_dist, fo_dist, prior_k) in zip(
                preflop_params, preflop_priors
            )
        ]

        postflop_ads = [
            self._estimate_ad_postflop(
                player_stats,
                sorted_post,
                params,
                br_dist,
                cc_dist,
                fo_dist,
                prior_k,
            )
            for params, (br_dist, cc_dist, fo_dist, prior_k) in zip(
                postflop_params, postflop_priors
            )
        ]

        return preflop_ads, postflop_ads
