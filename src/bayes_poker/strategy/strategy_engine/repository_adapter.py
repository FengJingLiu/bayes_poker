"""strategy_engine v2 的 sqlite 读取适配层。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.strategy_engine.core_types import NodeContext


@dataclass(frozen=True, slots=True)
class StrategySourceInfo:
    """strategy_engine v2 使用的中性策略源信息。"""

    source_id: int
    strategy_name: str
    source_dir: str
    format_version: int


@dataclass(frozen=True, slots=True)
class StrategyNodeCandidate:
    """strategy_engine v2 使用的中性节点候选。"""

    node_id: int
    source_id: int
    stack_bb: int
    history_full: str
    history_actions: str
    history_token_count: int
    action_family: str | None
    actor_position: str | None
    aggressor_position: str | None
    call_count: int
    limp_count: int
    raise_size_bb: float | None
    is_in_position: bool | None


@dataclass(frozen=True, slots=True)
class StrategyActionOption:
    """strategy_engine v2 使用的中性动作选项。"""

    node_id: int
    order_index: int
    action_code: str
    action_type: str
    bet_size_bb: float | None
    is_all_in: bool
    total_frequency: float
    next_position: str
    total_ev: float
    total_combos: float


class StrategyRepositoryAdapter:
    """对 `PreflopStrategyRepository` 的中性读取封装。"""

    def __init__(self, db_path: str | Path) -> None:
        """初始化适配器。

        Args:
            db_path: sqlite 数据库路径。
        """

        self._repo = PreflopStrategyRepository(db_path)

    def connect(self) -> None:
        """连接底层 sqlite 仓库。"""

        self._repo.connect()

    def close(self) -> None:
        """关闭底层 sqlite 仓库。"""

        self._repo.close()

    def resolve_source(
        self,
        *,
        source_id: int | None = None,
        strategy_name: str | None = None,
    ) -> StrategySourceInfo:
        """解析要使用的策略源。

        Args:
            source_id: 指定的策略源 ID。
            strategy_name: 指定的策略源名称。

        Returns:
            中性策略源信息。

        Raises:
            ValueError: 当未命中或命中多个策略源时抛出。
        """

        sources = self._repo.list_sources()
        if source_id is not None:
            matched = [source for source in sources if source.source_id == source_id]
        elif strategy_name is not None:
            matched = [
                source for source in sources if source.strategy_name == strategy_name
            ]
        else:
            matched = sources

        if not matched:
            raise ValueError("未找到匹配的策略源。")
        if len(matched) > 1:
            raise ValueError("存在多个策略源，请显式指定 source_id 或 strategy_name。")

        source = next(iter(matched), None)
        if source is None:
            raise ValueError("未找到匹配的策略源。")
        return StrategySourceInfo(
            source_id=source.source_id,
            strategy_name=source.strategy_name,
            source_dir=source.source_dir,
            format_version=source.format_version,
        )

    def resolve_stack_bb(self, *, source_id: int, requested_stack_bb: int) -> int:
        """解析最接近的可用筹码深度。"""

        return self._repo.resolve_stack_bb(
            source_id=source_id,
            requested_stack_bb=requested_stack_bb,
        )

    def load_candidates(
        self,
        *,
        source_id: int,
        stack_bb: int,
        node_context: NodeContext,
    ) -> tuple[StrategyNodeCandidate, ...]:
        """读取给定节点上下文的候选节点。"""

        candidates = self._repo.list_candidates(
            source_id=source_id,
            stack_bb=stack_bb,
            action_family=cast(Any, node_context.action_family),
            actor_position=node_context.actor_position,
        )
        return tuple(
            StrategyNodeCandidate(
                node_id=candidate.node_id,
                source_id=candidate.source_id,
                stack_bb=candidate.stack_bb,
                history_full=candidate.history_full,
                history_actions=candidate.history_actions,
                history_token_count=candidate.history_token_count,
                action_family=(
                    candidate.action_family.name
                    if candidate.action_family is not None
                    else None
                ),
                actor_position=(
                    candidate.actor_position.value
                    if candidate.actor_position is not None
                    else None
                ),
                aggressor_position=(
                    candidate.aggressor_position.value
                    if candidate.aggressor_position is not None
                    else None
                ),
                call_count=candidate.call_count,
                limp_count=candidate.limp_count,
                raise_size_bb=candidate.raise_size_bb,
                is_in_position=candidate.is_in_position,
            )
            for candidate in candidates
        )

    def load_actions(
        self,
        node_ids: tuple[int, ...],
    ) -> dict[int, tuple[StrategyActionOption, ...]]:
        """批量读取节点动作。"""

        actions_by_node = self._repo.get_actions_for_nodes(node_ids)
        return {
            node_id: tuple(
                StrategyActionOption(
                    node_id=action.node_id,
                    order_index=action.order_index,
                    action_code=action.action_code,
                    action_type=action.action_type,
                    bet_size_bb=action.bet_size_bb,
                    is_all_in=action.is_all_in,
                    total_frequency=action.total_frequency,
                    next_position=action.next_position,
                    total_ev=action.total_ev,
                    total_combos=action.total_combos,
                )
                for action in actions
            )
            for node_id, actions in actions_by_node.items()
        }
