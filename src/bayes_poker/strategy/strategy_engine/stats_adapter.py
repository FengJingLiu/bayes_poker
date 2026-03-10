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
    """当前节点的玩家动作概率视图。"""

    raise_probability: float
    call_probability: float
    fold_probability: float
    bet_0_40_probability: float
    bet_40_80_probability: float
    bet_80_120_probability: float
    bet_over_120_probability: float
    confidence: float
    source_kind: str


@dataclass(frozen=True, slots=True)
class PlayerNodeStatsAdapterConfig:
    """玩家节点概率适配器配置。"""

    pool_prior_strength: float = 20.0
    confidence_k: float = 20.0


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

        Args:
            player_name: 玩家名, 为空时直接走 population fallback。
            table_type: 桌型。
            node_context: 当前节点上下文。

        Returns:
            当前节点的玩家动作概率。
        """

        source_kind = "player"
        stats = self._load_player_stats(player_name, table_type)
        if stats is None:
            source_kind = "population"
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
            source_kind=source_kind,
        )

    def _load_player_stats(
        self,
        player_name: str | None,
        table_type: TableType,
    ) -> PlayerStats | None:
        if not player_name:
            return None
        try:
            return self._repo.get(
                player_name,
                table_type,
                smooth_with_pool=True,
                pool_prior_strength=self._config.pool_prior_strength,
            )
        except sqlite3.OperationalError:
            return None

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
