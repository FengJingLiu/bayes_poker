"""strategy_engine v2 的 hero GTO resolver。"""

from __future__ import annotations

from collections.abc import Sequence
from bayes_poker.domain.table import Player
from .context_builder import build_player_node_context
from .contracts import (
    RecommendationDecision,
    SafeFallbackDecision,
    StrategyDecision,
    UnsupportedScenarioDecision,
)
from .gto_policy import GtoPriorBuilder, GtoPriorPolicy
from .node_mapper import StrategyNodeMapper
from .repository_adapter import (
    StrategyRepositoryAdapter,
)
from .session_context import StrategySessionContext
from bayes_poker.table.observed_state import ObservedTableState


class HeroGtoResolver:
    """根据当前 hero 节点返回 GTO 推荐。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        source_id: int | Sequence[int],
    ) -> None:
        """初始化 hero resolver.

        Args:
            repository_adapter: 策略仓库适配器.
            source_id: 策略源 ID 或 ID 序列.
        """

        self._repository_adapter = repository_adapter
        self._source_id = source_id

    def resolve(
        self,
        *,
        observed_state: ObservedTableState,
        session_context: StrategySessionContext,
    ) -> StrategyDecision:
        """解析当前 hero 节点的 GTO 推荐。"""

        try:
            node_context = build_player_node_context(observed_state)
            hero_player = _find_player(observed_state, observed_state.hero_seat)
            if hero_player is None:
                raise ValueError("找不到 hero 玩家信息。")
            stack_bb = max(
                1, int(round(hero_player.get_stack_bb(observed_state.big_blind)))
            )
            resolved_stack = self._repository_adapter.resolve_stack_bb(
                source_id=self._source_id,
                requested_stack_bb=stack_bb,
            )
            mapped_context = StrategyNodeMapper(
                repository_adapter=self._repository_adapter,
                source_id=self._source_id,
                stack_bb=resolved_stack,
            ).map_node_context(node_context.node_context)
            policy = GtoPriorBuilder(
                repository_adapter=self._repository_adapter,
            ).build_policy(mapped_context)
            best_action = _select_best_action(policy)
            return RecommendationDecision(
                state_version=observed_state.state_version,
                action_code=best_action.action_name,
                amount=_extract_amount(best_action.action_name),
                confidence=best_action.blended_frequency,
                ev=None,
                notes=(
                    f"hero_posterior_deferred_v1; matched_history={mapped_context.matched_history}"
                ),
                range_breakdown={
                    f"seat_{seat}": player_range.total_frequency()
                    for seat, player_range in session_context.player_ranges.items()
                },
            )
        except ValueError as exc:
            return UnsupportedScenarioDecision(
                state_version=observed_state.state_version,
                reason=str(exc),
            )
        except Exception as exc:
            return SafeFallbackDecision(
                state_version=observed_state.state_version,
                error_code="hero_resolver_error",
                notes=str(exc),
            )


def _find_player(observed_state: ObservedTableState, seat_index: int) -> Player | None:
    for player in observed_state.players:
        if player.seat_index == seat_index:
            return player
    return None


def _select_best_action(policy: GtoPriorPolicy):
    best_action = policy.actions[0]
    for action in policy.actions[1:]:
        if action.blended_frequency > best_action.blended_frequency:
            best_action = action
    return best_action


def _extract_amount(action_name: str) -> float | None:
    normalized = action_name.upper()
    if normalized == "RAI":
        return 0.0
    if normalized.startswith("R"):
        try:
            return float(normalized[1:])
        except ValueError:
            return 0.0
    return 0.0
