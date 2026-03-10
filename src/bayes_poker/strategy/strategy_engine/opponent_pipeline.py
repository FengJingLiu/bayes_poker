"""strategy_engine v2 的对手范围更新管线。"""

from __future__ import annotations

from collections.abc import Sequence
import time
from dataclasses import dataclass

from bayes_poker.comm.session import SessionConfig
from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH
from .calibrator import (
    ActionPolicy,
    ActionPolicyAction,
    calibrate_multinomial_policy,
    redistribute_aggressive_mass,
)
from .context_builder import build_player_node_context
from .gto_policy import (
    GtoPriorBuilder,
    GtoPriorPolicy,
)
from .node_mapper import StrategyNodeMapper
from .posterior import update_posterior
from .repository_adapter import (
    StrategyRepositoryAdapter,
)
from .session_context import (
    StrategySessionContext,
    StrategySessionStore,
)
from .stats_adapter import (
    PlayerNodeStats,
    PlayerNodeStatsAdapter,
)
from bayes_poker.table.observed_state import ObservedTableState


@dataclass(frozen=True, slots=True)
class OpponentPipelineConfig:
    """对手范围更新管线配置。"""

    table_type: TableType = TableType.SIX_MAX
    session_timeout: float = SessionConfig.session_timeout


class OpponentPipeline:
    """在 hero 回合重建对手实际范围。"""

    def __init__(
        self,
        *,
        repository_adapter: StrategyRepositoryAdapter,
        stats_adapter: PlayerNodeStatsAdapter,
        source_id: int | Sequence[int],
        config: OpponentPipelineConfig | None = None,
    ) -> None:
        """初始化对手范围更新管线.

        Args:
            repository_adapter: 策略仓库适配器.
            stats_adapter: 节点统计适配器.
            source_id: 策略源 ID 或 ID 序列.
            config: 可选管线配置.
        """

        self._repository_adapter = repository_adapter
        self._stats_adapter = stats_adapter
        self._source_id = source_id
        self._config = config or OpponentPipelineConfig()
        self._session_store = StrategySessionStore(
            session_timeout=self._config.session_timeout,
        )

    def process_hero_snapshot(
        self,
        *,
        session_id: str,
        observed_state: ObservedTableState,
    ) -> StrategySessionContext:
        """在 hero 回合处理当前快照。"""

        self._session_store.cleanup_expired()
        context = self._session_store.get_or_create(
            session_id=session_id,
            table_id=observed_state.table_id,
            hand_id=observed_state.hand_id,
            state_version=observed_state.state_version,
        )
        context.last_seen_monotonic = time.monotonic()

        if observed_state.actor_seat != observed_state.hero_seat:
            return context

        fingerprint = observed_state.get_action_history_string()
        if context.last_action_fingerprint == fingerprint:
            return context

        acted_prefixes = _collect_first_action_prefixes(observed_state)
        live_opponents = [
            player
            for player in observed_state.players
            if player.seat_index != observed_state.hero_seat and not player.is_folded
        ]
        acted_opponents = [
            player for player in live_opponents if player.seat_index in acted_prefixes
        ]
        acted_opponents.sort(key=lambda player: acted_prefixes[player.seat_index][0])
        prior_only_opponents = [
            player
            for player in live_opponents
            if player.seat_index not in acted_prefixes
        ]

        for player in acted_opponents:
            seat = player.seat_index
            action_index, prefix = acted_prefixes[seat]
            action = observed_state.action_history[action_index]
            context.player_ranges[seat] = self._build_posterior_range(
                player=player,
                observed_state=observed_state,
                action=action,
                decision_prefix=prefix,
                prior=context.player_ranges.get(
                    seat, _build_initial_prior_range(player)
                ),
            )
            context.player_summaries[seat] = {
                "status": "posterior",
                "source_kind": self._last_source_kind,
            }

        for player in prior_only_opponents:
            seat = player.seat_index
            context.player_ranges.setdefault(seat, _build_initial_prior_range(player))
            context.player_summaries[seat] = {"status": "prior_only"}

        context.last_action_fingerprint = fingerprint
        return context

    def _build_posterior_range(
        self,
        *,
        player: Player,
        observed_state: ObservedTableState,
        action: PlayerAction,
        decision_prefix: list[PlayerAction],
        prior: PreflopRange,
    ) -> PreflopRange:
        state_for_player = ObservedTableState(
            table_id=observed_state.table_id,
            player_count=observed_state.player_count,
            small_blind=observed_state.small_blind,
            big_blind=observed_state.big_blind,
            hand_id=observed_state.hand_id,
            street=Street.PREFLOP,
            pot=observed_state.pot,
            btn_seat=observed_state.btn_seat,
            actor_seat=player.seat_index,
            hero_seat=observed_state.hero_seat,
            hero_cards=observed_state.hero_cards,
            board_cards=observed_state.board_cards,
            players=observed_state.players,
            action_history=decision_prefix,
            state_version=observed_state.state_version,
            timestamp=observed_state.timestamp,
        )
        node_context = build_player_node_context(
            state_for_player,
            table_type=self._config.table_type,
        )
        node_stats = self._stats_adapter.load(
            player_name=player.player_id,
            table_type=self._config.table_type,
            node_context=node_context,
        )
        self._last_source_kind = node_stats.source_kind

        stack_bb = max(1, int(round(player.get_stack_bb(observed_state.big_blind))))
        resolved_stack = self._repository_adapter.resolve_stack_bb(
            source_id=self._source_id,
            requested_stack_bb=stack_bb,
        )
        mapper = StrategyNodeMapper(
            repository_adapter=self._repository_adapter,
            source_id=self._source_id,
            stack_bb=resolved_stack,
        )
        mapped = mapper.map_node_context(node_context.node_context)
        prior_policy = GtoPriorBuilder(
            repository_adapter=self._repository_adapter,
        ).build_policy(mapped)
        calibrated_policy = _calibrate_policy(
            prior_policy=prior_policy, node_stats=node_stats
        )
        action_name = _resolve_action_name(
            prior_policy=prior_policy, action=action, big_blind=observed_state.big_blind
        )
        posterior = update_posterior(
            prior=prior,
            calibrated_policy=calibrated_policy,
            action_name=action_name,
        )
        return posterior.posterior_range


def _collect_first_action_prefixes(
    observed_state: ObservedTableState,
) -> dict[int, tuple[int, list[PlayerAction]]]:
    prefixes: dict[int, tuple[int, list[PlayerAction]]] = {}
    current_prefix: list[PlayerAction] = []
    for index, action in enumerate(observed_state.action_history):
        if action.street != Street.PREFLOP:
            continue
        if action.player_index not in prefixes:
            prefixes[action.player_index] = (index, list(current_prefix))
        current_prefix.append(action)
    return prefixes


def _build_initial_prior_range(player: Player) -> PreflopRange:
    if player.player_id:
        frequency = 0.25
    else:
        frequency = 0.20
    if player.position == Position.BTN:
        frequency = 0.40
    elif player.position == Position.CO:
        frequency = 0.25
    elif player.position == Position.MP:
        frequency = 0.18
    elif player.position == Position.UTG:
        frequency = 0.15
    elif player.position == Position.SB:
        frequency = 0.35
    elif player.position == Position.BB:
        frequency = 0.50
    return PreflopRange(strategy=[frequency] * RANGE_169_LENGTH)


def _calibrate_policy(
    *,
    prior_policy: GtoPriorPolicy,
    node_stats: PlayerNodeStats,
) -> ActionPolicy:
    actions = tuple(
        ActionPolicyAction(
            action_name=action.action_name,
            range=PreflopRange(strategy=[action.blended_frequency] * RANGE_169_LENGTH),
        )
        for action in prior_policy.actions
    )
    action_policy = ActionPolicy(actions=actions)
    aggressive_actions = [
        action_name
        for action_name in action_policy.action_names
        if action_name.upper().startswith("R")
    ]
    target_mix: dict[str, float] = {}
    for action_name in action_policy.action_names:
        normalized = action_name.upper()
        if normalized == "F":
            target_mix[action_name] = node_stats.fold_probability
        elif normalized == "C":
            target_mix[action_name] = node_stats.call_probability
        else:
            target_mix[action_name] = node_stats.raise_probability / max(
                1, len(aggressive_actions)
            )
    calibrated = calibrate_multinomial_policy(action_policy, target_mix=target_mix)
    size_weights = _build_size_weights(
        aggressive_actions=aggressive_actions, node_stats=node_stats
    )
    return redistribute_aggressive_mass(calibrated, size_weights=size_weights)


def _build_size_weights(
    *,
    aggressive_actions: list[str],
    node_stats: PlayerNodeStats,
) -> dict[str, float] | None:
    if not aggressive_actions:
        return None
    ordered_weights = [
        node_stats.bet_0_40_probability,
        node_stats.bet_40_80_probability,
        node_stats.bet_80_120_probability,
        node_stats.bet_over_120_probability,
    ]
    weights: dict[str, float] = {}
    for index, action_name in enumerate(
        sorted(aggressive_actions, key=_raise_action_key)
    ):
        bucket_index = min(index, len(ordered_weights) - 1)
        weights[action_name] = ordered_weights[bucket_index]
    return weights


def _resolve_action_name(
    *,
    prior_policy: GtoPriorPolicy,
    action: PlayerAction,
    big_blind: float,
) -> str:
    if action.action_type == ActionType.FOLD:
        return "F"
    if action.action_type in {ActionType.CALL, ActionType.CHECK}:
        return "C"
    aggressive_actions = [
        action_name
        for action_name in prior_policy.action_names
        if action_name.upper().startswith("R")
    ]
    if not aggressive_actions:
        return "C"
    actual_size_bb = action.amount / big_blind if big_blind > 0 else 0.0
    return min(
        aggressive_actions,
        key=lambda action_name: abs(_raise_action_key(action_name) - actual_size_bb),
    )


def _raise_action_key(action_name: str) -> float:
    normalized = action_name.upper()
    if normalized == "RAI":
        return 1000.0
    if normalized.startswith("R"):
        try:
            return float(normalized[1:])
        except ValueError:
            return 0.0
    return 0.0
