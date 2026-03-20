"""strategy_engine v2 的玩家节点概率适配层。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.strategy_engine.core_types import PlayerNodeContext

_AGGREGATED_PLAYER_NAMES: dict[TableType, str] = {
    TableType.SIX_MAX: "aggregated_sixmax_100",
}

_MIN_HANDS_FOR_INDIVIDUAL_STATS: int = 10


def _should_fallback_to_population(stats: PlayerStats) -> bool:
    """判断玩家统计是否过于极端, 应回退到聚合玩家池数据。

    当玩家总手数不足 10 手, 或 VPIP 和 PFR(bet_raise) 均为 0 时,
    个体统计不具备建模意义, 使用 aggregated_sixmax_100 作为替代。

    Args:
        stats: 玩家原始统计。

    Returns:
        True 表示应回退到 population fallback。
    """
    if stats.vpip.total < _MIN_HANDS_FOR_INDIVIDUAL_STATS:
        return True
    if stats.vpip.positive == 0 and stats.vpip.total > 0:
        total_raise = sum(
            s.raise_samples for s in stats.preflop_stats
        )
        if total_raise == 0:
            return True
    return False


@dataclass(frozen=True, slots=True)
class PlayerNodeStats:
    """当前节点的玩家动作概率视图。

    Attributes:
        raise_probability: 当前节点的加注概率。
        call_probability: 当前节点的跟注/过牌概率。
        fold_probability: 当前节点的弃牌概率。
        bet_0_40_probability: 下注尺寸在 (0, 0.4] 区间的概率。
        bet_40_80_probability: 下注尺寸在 (0.4, 0.8] 区间的概率。
        bet_80_120_probability: 下注尺寸在 (0.8, 1.2] 区间的概率。
        bet_over_120_probability: 下注尺寸在 (1.2, +∞) 区间的概率。
        source_kind: 统计来源, 例如 player 或 population。
    """

    raise_probability: float
    call_probability: float
    fold_probability: float
    bet_0_40_probability: float
    bet_40_80_probability: float
    bet_80_120_probability: float
    bet_over_120_probability: float
    source_kind: str


@dataclass(frozen=True, slots=True)
class PlayerNodeStatsAdapterConfig:
    """玩家节点概率适配器配置。

    Attributes:
        max_similar_players: 相似玩家池大小, 传递给 OpponentEstimator。
    """

    max_similar_players: int = 130


class PlayerNodeStatsAdapter:
    """把玩家统计仓库适配为节点概率输出。"""

    def __init__(
        self,
        repo: PlayerStatsRepository,
        *,
        config: PlayerNodeStatsAdapterConfig | None = None,
    ) -> None:
        """初始化 stats adapter。

        Args:
            repo: 玩家统计仓库。
            config: 可选适配器配置。
        """

        self._repo = repo
        self._config = config or PlayerNodeStatsAdapterConfig()

    def load(
        self,
        *,
        player_name: str | None,
        table_type: TableType,
        node_context: PlayerNodeContext,
    ) -> PlayerNodeStats:
        """读取指定玩家在当前节点的动作概率。

        流程:
        1. 获取 raw_stats 判断玩家是否存在。
        2. G5 OpponentEstimator 路径构建节点概率。
        3. G5 不可用时回退到 population fallback。

        Args:
            player_name: 玩家名, 为空时直接走 population fallback。
            table_type: 桌型。
            node_context: 当前节点上下文。

        Returns:
            当前节点的玩家动作概率。
        """

        raw_stats = self._load_raw_player_stats(player_name, table_type)
        if raw_stats is None or (player_name and raw_stats.player_name != player_name):
            return self._load_population_node_stats(table_type, node_context)
        if player_name is None:
            return self._load_population_node_stats(table_type, node_context)

        if _should_fallback_to_population(raw_stats):
            return self._load_population_node_stats(table_type, node_context)

        g5_result = self._load_g5_node_stats(
            player_name=player_name,
            table_type=table_type,
            node_context=node_context,
            raw_stats=raw_stats,
        )
        if g5_result is not None:
            return g5_result

        return self._load_population_node_stats(table_type, node_context)

    def _load_raw_player_stats(
        self,
        player_name: str | None,
        table_type: TableType,
    ) -> PlayerStats | None:
        """获取玩家原始未平滑统计。

        该方法仅用于读取 vpip.total 等全局指标。

        Args:
            player_name: 玩家名。
            table_type: 桌型。

        Returns:
            原始统计, 玩家不存在时返回 None。
        """

        if not player_name:
            return None
        try:
            return self._repo.get(player_name, table_type)
        except sqlite3.OperationalError:
            return None

    def _load_population_node_stats(
        self,
        table_type: TableType,
        node_context: PlayerNodeContext,
    ) -> PlayerNodeStats:
        """构建 population fallback 的 PlayerNodeStats。

        Args:
            table_type: 桌型。
            node_context: 当前节点上下文。

        Returns:
            population 级别的节点统计。
        """

        stats = self._load_population_stats(table_type)
        action_stats = stats.get_preflop_stats(node_context.params)
        return PlayerNodeStats(
            raise_probability=action_stats.bet_raise_probability(),
            call_probability=action_stats.check_call_probability(),
            fold_probability=action_stats.fold_probability(),
            bet_0_40_probability=action_stats.bet_0_40_probability(),
            bet_40_80_probability=action_stats.bet_40_80_probability(),
            bet_80_120_probability=action_stats.bet_80_120_probability(),
            bet_over_120_probability=action_stats.bet_over_120_probability(),
            source_kind="population",
        )

    def _load_population_stats(self, table_type: TableType) -> PlayerStats:
        aggregated_name = _AGGREGATED_PLAYER_NAMES.get(table_type)
        if aggregated_name is not None:
            try:
                aggregated = self._repo.get(aggregated_name, table_type)
            except sqlite3.OperationalError:
                aggregated = None
            if aggregated is not None:
                return aggregated
        return PlayerStats(player_name="population", table_type=table_type)

    def _get_g5_estimator(self, table_type: TableType) -> object:
        """懒加载并缓存 G5 OpponentEstimator（按桌型）。"""
        if not hasattr(self, "_g5_estimators"):
            self._g5_estimators: dict[TableType, object] = {}
        estimator = self._g5_estimators.get(table_type)
        if estimator is None:
            from bayes_poker.player_metrics.opponent_estimator import (
                OpponentEstimator,
                OpponentEstimatorOptions,
            )

            def _load_exact(name: str) -> PlayerStats | None:
                try:
                    stats = self._repo.get(name, table_type)
                except sqlite3.OperationalError:
                    return None
                if stats is None or stats.player_name != name:
                    return None
                return stats

            options = OpponentEstimatorOptions(
                max_similar_players=self._config.max_similar_players,
            )
            summaries = self._repo.load_summary_for_estimator(table_type)
            if summaries:
                estimator = OpponentEstimator.from_summaries(
                    summaries,
                    table_type=table_type,
                    stats_loader=_load_exact,
                    options=options,
                )
            else:
                estimator = OpponentEstimator(
                    self._repo.load_all_for_estimator(table_type),
                    table_type,
                    options=options,
                )
            self._g5_estimators[table_type] = estimator
        return estimator

    def _load_g5_node_stats(
        self,
        *,
        player_name: str,
        table_type: TableType,
        node_context: PlayerNodeContext,
        raw_stats: PlayerStats,
    ) -> PlayerNodeStats | None:
        """用 G5 OpponentEstimator 构建节点统计, 不可用时返回 None 触发 population fallback。"""
        try:
            estimator = self._get_g5_estimator(table_type)
            estimated = self.load_g5_estimated_ad(
                player_name=player_name,
                estimator=estimator,
                table_type=table_type,
            )
        except sqlite3.OperationalError:
            return None

        if estimated is None:
            return None

        preflop_ads, _ = estimated
        try:
            ad = preflop_ads[node_context.params.to_index()]
        except IndexError:
            return None

        return self._build_player_node_stats_from_estimated_ad(ad=ad)

    def _build_player_node_stats_from_estimated_ad(
        self,
        *,
        ad: object,
    ) -> PlayerNodeStats:
        """从 EstimatedAD 构建 PlayerNodeStats。

        bet sizing 分布保持均匀（G5 路径不建模 sizing 分解）。
        """
        from bayes_poker.player_metrics.estimated_ad import EstimatedAD

        assert isinstance(ad, EstimatedAD)
        return PlayerNodeStats(
            raise_probability=ad.bet_raise.mean,
            call_probability=ad.check_call.mean,
            fold_probability=ad.fold.mean,
            bet_0_40_probability=0.25,
            bet_40_80_probability=0.25,
            bet_80_120_probability=0.25,
            bet_over_120_probability=0.25,
            source_kind="g5_player",
        )

    def load_g5_estimated_ad(
        self,
        player_name: str,
        estimator: object,
        table_type: TableType,
    ) -> tuple[list[object], list[object]] | None:
        """用 G5 OpponentEstimator 获取玩家全节点 AD 估计。

        Args:
            player_name: 目标玩家名。
            estimator: 已初始化的 OpponentEstimator 实例。
            table_type: 桌型。

        Returns:
            元组 (preflop_ads, postflop_ads)，玩家在数据库中不存在时返回 None。
        """
        from bayes_poker.player_metrics.opponent_estimator import OpponentEstimator

        if not isinstance(estimator, OpponentEstimator):
            return None

        player_stats = self._load_raw_player_stats(player_name, table_type)
        if player_stats is None or player_stats.player_name != player_name:
            return None

        return estimator.estimate_player_model(player_stats)
