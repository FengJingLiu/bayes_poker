"""strategy_engine v2 的可调用 facade。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from .contracts import (
    NoResponseDecision,
    StrategyDecision,
)
from .hero_resolver import HeroGtoResolver
from .opponent_pipeline import (
    OpponentPipeline,
    OpponentPipelineConfig,
)
from .repository_adapter import (
    StrategyRepositoryAdapter,
)
from .stats_adapter import (
    PlayerNodeStatsAdapter,
    PlayerNodeStatsAdapterConfig,
)
from bayes_poker.table.observed_state import ObservedTableState


@dataclass(frozen=True, slots=True)
class StrategyEngineConfig:
    """strategy_engine facade 的构建配置。"""

    strategy_db_path: Path
    player_stats_db_path: Path
    table_type: TableType = TableType.SIX_MAX
    source_id: int | None = None
    source_ids: tuple[int, ...] | None = None
    strategy_name: str | None = None
    strategy_names: tuple[str, ...] | None = None
    pool_prior_strength: float = 20.0


class StrategyEngine:
    """把对手 pipeline 与 hero resolver 组装为可调用处理器。"""

    def __init__(
        self,
        *,
        opponent_pipeline: OpponentPipeline,
        hero_resolver: HeroGtoResolver,
    ) -> None:
        """初始化引擎 facade。"""

        self._opponent_pipeline = opponent_pipeline
        self._hero_resolver = hero_resolver

    async def __call__(
        self,
        session_id: str,
        observed_state: ObservedTableState,
    ) -> StrategyDecision:
        """处理一次策略请求。"""

        if observed_state.actor_seat != observed_state.hero_seat:
            return NoResponseDecision(
                state_version=observed_state.state_version,
                reason="not_hero_turn",
            )
        session_context = self._opponent_pipeline.process_hero_snapshot(
            session_id=session_id,
            observed_state=observed_state,
        )
        return self._hero_resolver.resolve(
            observed_state=observed_state,
            session_context=session_context,
        )


def build_strategy_engine(config: StrategyEngineConfig) -> StrategyEngine:
    """按数据库配置构建完整 strategy_engine。"""

    repository_adapter = StrategyRepositoryAdapter(config.strategy_db_path)
    repository_adapter.connect()
    source_selector = _merge_source_id_selector(
        source_id=config.source_id,
        source_ids=config.source_ids,
    )
    strategy_name_selector = _merge_strategy_name_selector(
        strategy_name=config.strategy_name,
        strategy_names=config.strategy_names,
    )
    sources = repository_adapter.resolve_source(
        source_id=source_selector,
        strategy_name=strategy_name_selector,
    )
    source_ids = tuple(source.source_id for source in sources)
    stats_repo = PlayerStatsRepository(config.player_stats_db_path)
    stats_repo.connect()
    stats_adapter = PlayerNodeStatsAdapter(
        stats_repo,
        config=PlayerNodeStatsAdapterConfig(
            pool_prior_strength=config.pool_prior_strength,
        ),
    )
    opponent_pipeline = OpponentPipeline(
        repository_adapter=repository_adapter,
        stats_adapter=stats_adapter,
        source_id=source_ids,
        config=OpponentPipelineConfig(table_type=config.table_type),
    )
    hero_resolver = HeroGtoResolver(
        repository_adapter=repository_adapter,
        source_id=source_ids,
    )
    return StrategyEngine(
        opponent_pipeline=opponent_pipeline,
        hero_resolver=hero_resolver,
    )


def _merge_source_id_selector(
    *,
    source_id: int | None,
    source_ids: tuple[int, ...] | None,
) -> int | Sequence[int] | None:
    """合并单值和多值策略源 ID 选择器.

    Args:
        source_id: 单个策略源 ID.
        source_ids: 多个策略源 ID.

    Returns:
        合并后的策略源 ID 选择器.
    """

    if source_ids is None:
        return source_id
    if source_id is None:
        return source_ids
    return (source_id, *source_ids)


def _merge_strategy_name_selector(
    *,
    strategy_name: str | None,
    strategy_names: tuple[str, ...] | None,
) -> str | Sequence[str] | None:
    """合并单值和多值策略源名称选择器.

    Args:
        strategy_name: 单个策略源名称.
        strategy_names: 多个策略源名称.

    Returns:
        合并后的策略源名称选择器.
    """

    if strategy_names is None:
        return strategy_name
    if strategy_name is None:
        return strategy_names
    return (strategy_name, *strategy_names)
