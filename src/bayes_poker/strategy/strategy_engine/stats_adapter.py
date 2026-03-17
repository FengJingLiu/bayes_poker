"""strategy_engine v2 的玩家节点概率适配层。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.strategy_engine.core_types import PlayerNodeContext

_AGGREGATED_PLAYER_NAMES: dict[TableType, str] = {
    TableType.SIX_MAX: "aggregated_sixmax_100",
}


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
        confidence: 节点统计置信度。
        global_pfr: 玩家全局 PFR 概率。
        global_vpip: 玩家全局 VPIP 概率。
        total_hands: 玩家全局样本手数。
        source_kind: 统计来源, 例如 player 或 population。
    """

    raise_probability: float
    call_probability: float
    fold_probability: float
    bet_0_40_probability: float
    bet_40_80_probability: float
    bet_80_120_probability: float
    bet_over_120_probability: float
    confidence: float
    global_pfr: float
    global_vpip: float
    total_hands: int
    source_kind: str


@dataclass(frozen=True, slots=True)
class PlayerNodeStatsAdapterConfig:
    """玩家节点概率适配器配置。

    Attributes:
        pool_prior_strength: 玩家样本与群体样本平滑时的群体先验强度。
        confidence_k: 置信度计算中的平滑常量。
        adaptive_reference_hands: 自适应平滑的参考手数。
        adaptive_min_strength: 自适应平滑的最小强度。
    """

    pool_prior_strength: float = 20.0
    confidence_k: float = 20.0
    adaptive_reference_hands: float = 200.0
    adaptive_min_strength: float = 2.0


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

        四步流程:
        1. 获取 raw_stats 计算 adaptive_k。
        2. 基于 adaptive_k 调用 get_with_raw() 获取 (raw, smoothed)。
        3. 从 raw 提取 confidence + 全局信号。
        4. 从 smoothed 提取节点概率, 组装返回。

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

        adaptive_k = self._compute_adaptive_prior_strength(raw_stats)
        raw_from_pair, smoothed = self._repo.get_with_raw(
            player_name,
            table_type,
            pool_prior_strength=adaptive_k,
        )
        if smoothed is None:
            return self._load_population_node_stats(table_type, node_context)

        raw_action = (
            raw_from_pair.get_preflop_stats(node_context.params)
            if raw_from_pair is not None
            else None
        )
        raw_total = raw_action.total_samples() if raw_action is not None else 0
        raw_confidence = self._build_confidence(raw_total)

        global_pfr = (
            self._compute_global_pfr(raw_from_pair)
            if raw_from_pair is not None
            else 0.0
        )
        global_vpip = (
            raw_from_pair.vpip.to_float() if raw_from_pair is not None else 0.0
        )
        total_hands = raw_from_pair.vpip.total if raw_from_pair is not None else 0

        smoothed_action = smoothed.get_preflop_stats(node_context.params)
        return PlayerNodeStats(
            raise_probability=smoothed_action.bet_raise_probability(),
            call_probability=smoothed_action.check_call_probability(),
            fold_probability=smoothed_action.fold_probability(),
            bet_0_40_probability=smoothed_action.bet_0_40_probability(),
            bet_40_80_probability=smoothed_action.bet_40_80_probability(),
            bet_80_120_probability=smoothed_action.bet_80_120_probability(),
            bet_over_120_probability=smoothed_action.bet_over_120_probability(),
            confidence=raw_confidence,
            global_pfr=global_pfr,
            global_vpip=global_vpip,
            total_hands=total_hands,
            source_kind="player",
        )

    def _compute_adaptive_prior_strength(
        self,
        player_stats: PlayerStats,
    ) -> float:
        """根据玩家全局手牌量自适应调整 pool_prior_strength。

        全局手牌多 -> 信任玩家数据 -> 降低 prior_strength。
        全局手牌少 -> 不确定性高 -> 保持较高 prior_strength。

        Args:
            player_stats: 玩家原始统计数据。

        Returns:
            自适应调整后的 pool_prior_strength。
        """

        total_hands = player_stats.vpip.total
        base_strength = self._config.pool_prior_strength
        reference_hands = self._config.adaptive_reference_hands
        adaptive_strength = base_strength / (1.0 + total_hands / reference_hands)
        return max(self._config.adaptive_min_strength, adaptive_strength)

    @staticmethod
    def _compute_global_pfr(player_stats: PlayerStats) -> float:
        """从原始统计安全计算全局 PFR。

        Args:
            player_stats: 玩家原始统计数据。

        Returns:
            全局 PFR 概率, 样本为 0 时返回 0.0。
        """

        from bayes_poker.player_metrics.builder import calculate_pfr

        positive, total = calculate_pfr(player_stats)
        return positive / total if total > 0 else 0.0

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
            return self._repo.get(
                player_name,
                table_type,
                smooth_with_pool=False,
            )
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
        total_samples = action_stats.total_samples()
        return PlayerNodeStats(
            raise_probability=action_stats.bet_raise_probability(),
            call_probability=action_stats.check_call_probability(),
            fold_probability=action_stats.fold_probability(),
            bet_0_40_probability=action_stats.bet_0_40_probability(),
            bet_40_80_probability=action_stats.bet_40_80_probability(),
            bet_80_120_probability=action_stats.bet_80_120_probability(),
            bet_over_120_probability=action_stats.bet_over_120_probability(),
            confidence=self._build_confidence(total_samples),
            global_pfr=0.0,
            global_vpip=0.0,
            total_hands=0,
            source_kind="population",
        )

    def _load_population_stats(self, table_type: TableType) -> PlayerStats:
        aggregated_name = _AGGREGATED_PLAYER_NAMES.get(table_type)
        if aggregated_name is not None:
            try:
                aggregated = self._repo.get(
                    aggregated_name,
                    table_type,
                    smooth_with_pool=False,
                )
            except sqlite3.OperationalError:
                aggregated = None
            if aggregated is not None:
                return aggregated
        return PlayerStats(player_name="population", table_type=table_type)

    def _build_confidence(self, total_samples: int) -> float:
        if total_samples < 0:
            raise ValueError("total_samples 不能为负数")
        return total_samples / (total_samples + self._config.confidence_k)
