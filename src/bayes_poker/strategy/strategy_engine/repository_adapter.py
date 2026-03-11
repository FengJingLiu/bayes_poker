"""strategy_engine v2 的 sqlite 读取适配层。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bayes_poker.domain.table import Position
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
    actor_position: str | None
    aggressor_position: str | None
    call_count: int
    limp_count: int
    raise_time: int
    pot_size: float
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
        source_id: int | Sequence[int] | None = None,
        strategy_name: str | Sequence[str] | None = None,
    ) -> tuple[StrategySourceInfo, ...]:
        """解析要使用的策略源.

        Args:
            source_id: 指定的策略源 ID 或 ID 序列.
            strategy_name: 指定的策略源名称或名称序列.

        Returns:
            匹配的中性策略源信息元组.

        Raises:
            ValueError: 当未命中策略源或选择器为空时抛出.
        """

        sources = self._repo.list_sources()
        source_ids = _normalize_source_id_selector(source_id)
        strategy_names = _normalize_strategy_name_selector(strategy_name)
        if source_ids is not None:
            matched = [source for source in sources if source.source_id in source_ids]
        elif strategy_names is not None:
            matched = [
                source for source in sources if source.strategy_name in strategy_names
            ]
        else:
            matched = list(sources)

        if not matched:
            raise ValueError("未找到匹配的策略源。")
        return tuple(
            StrategySourceInfo(
                source_id=source.source_id,
                strategy_name=source.strategy_name,
                source_dir=source.source_dir,
                format_version=source.format_version,
            )
            for source in matched
        )

    def resolve_stack_bb(
        self,
        *,
        source_id: int | Sequence[int],
        requested_stack_bb: int,
    ) -> int:
        """解析最接近的可用筹码深度.

        Args:
            source_id: 策略源 ID 或 ID 序列.
            requested_stack_bb: 期望的筹码深度（BB 数）.

        Returns:
            与请求最接近的可用筹码深度.

        Raises:
            ValueError: 当指定策略源都没有可用 stack 时抛出.
        """

        source_ids = _normalize_source_id_selector(source_id)
        if source_ids is None:
            raise ValueError("source_id 不能为空。")

        resolved_pairs: list[tuple[int, int]] = []
        for current_source_id in source_ids:
            try:
                resolved_stack = self._repo.resolve_stack_bb(
                    source_id=current_source_id,
                    requested_stack_bb=requested_stack_bb,
                )
            except ValueError:
                continue
            resolved_pairs.append((current_source_id, resolved_stack))

        if not resolved_pairs:
            raise ValueError("指定策略源没有可用的 stack 配置。")

        _, best_stack = min(
            resolved_pairs,
            key=lambda item: (
                abs(item[1] - requested_stack_bb),
                item[1],
                item[0],
            ),
        )
        return best_stack

    def load_candidates(
        self,
        *,
        source_id: int | Sequence[int],
        stack_bb: int,
        node_context: NodeContext,
    ) -> tuple[StrategyNodeCandidate, ...]:
        """读取给定节点上下文的候选节点.

        Args:
            source_id: 策略源 ID 或 ID 序列.
            stack_bb: 目标筹码深度（BB 数）.
            node_context: 待匹配的中性节点上下文.

        Returns:
            候选节点元组.

        Raises:
            ValueError: 当 `source_id` 为空选择器时抛出.
        """

        source_ids = _normalize_source_id_selector(source_id)
        if source_ids is None:
            raise ValueError("source_id 不能为空。")

        candidates = []
        is_in_position = _derive_in_position(
            actor_position=node_context.actor_position,
            aggressor_position=node_context.aggressor_position,
        )
        candidates.extend(
            self._repo.list_candidates(
                source_ids=source_ids,
                stack_bb=stack_bb,
                is_in_position=is_in_position,
                raise_time=node_context.raise_time,
                pot_size=node_context.pot_size,
            )
        )
        return tuple(
            StrategyNodeCandidate(
                node_id=candidate.node_id,
                source_id=candidate.source_id,
                stack_bb=candidate.stack_bb,
                history_full=candidate.history_full,
                history_actions=candidate.history_actions,
                history_token_count=candidate.history_token_count,
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
                raise_time=candidate.raise_time,
                pot_size=candidate.pot_size,
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


def _normalize_source_id_selector(
    selector: int | Sequence[int] | None,
) -> tuple[int, ...] | None:
    """规范化策略源 ID 选择器.

    Args:
        selector: 输入的策略源 ID 或 ID 序列.

    Returns:
        规范化后的策略源 ID 元组, 如果输入为 `None` 则返回 `None`.

    Raises:
        ValueError: 当序列选择器为空时抛出.
    """

    if selector is None:
        return None
    if isinstance(selector, int):
        return (selector,)

    normalized = tuple(selector)
    if not normalized:
        raise ValueError("source_id 不能为空。")
    return normalized


def _normalize_strategy_name_selector(
    selector: str | Sequence[str] | None,
) -> tuple[str, ...] | None:
    """规范化策略源名称选择器.

    Args:
        selector: 输入的策略源名称或名称序列.

    Returns:
        规范化后的策略源名称元组, 如果输入为 `None` 则返回 `None`.

    Raises:
        ValueError: 当序列选择器为空时抛出.
    """

    if selector is None:
        return None
    if isinstance(selector, str):
        return (selector,)

    normalized = tuple(selector)
    if not normalized:
        raise ValueError("strategy_name 不能为空。")
    return normalized


def _derive_in_position(
    *,
    actor_position: Position,
    aggressor_position: Position | None,
) -> bool | None:
    if aggressor_position is None:
        return None
    if actor_position == aggressor_position:
        return False
    if {actor_position, aggressor_position} <= {
        Position.SB,
        Position.BB,
    }:
        return actor_position == Position.SB and aggressor_position == Position.BB

    postflop_position_order = (
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.MP,
        Position.MP1,
        Position.HJ,
        Position.CO,
        Position.BTN,
    )
    return postflop_position_order.index(
        actor_position
    ) > postflop_position_order.index(aggressor_position)
