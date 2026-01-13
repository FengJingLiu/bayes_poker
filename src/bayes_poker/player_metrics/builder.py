from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pokerkit import HandHistory

from .enums import ActionType, Position, Street, TableType
from .models import ActionStats, BetSizingCategory, PlayerStats, StatValue
from .params import PostFlopParams, PreFlopParams

if TYPE_CHECKING:
    pass


@dataclass
class ParsedAction:
    street: Street
    player_name: str
    action_type: ActionType
    amount: int
    pot_size_before_action: int = 0


def get_player_position(player_index: int, num_players: int) -> Position:
    if player_index == 0:
        return Position.SMALL_BLIND
    elif player_index == 1:
        return Position.BIG_BLIND
    elif player_index == num_players - 1:
        return Position.BUTTON
    elif player_index == num_players - 2:
        return Position.CO
    elif player_index == num_players - 3:
        return Position.HJ
    elif player_index == num_players - 4:
        return Position.UTG
    return Position.EMPTY


def is_in_position(active_players: list[str], player_name: str, num_players: int) -> bool:
    if not active_players:
        return False
    if num_players == 2:
        return active_players[0] == player_name
    return active_players[-1] == player_name


def _get_street_from_board_count(board_card_count: int) -> Street:
    if board_card_count == 0:
        return Street.PREFLOP
    elif board_card_count == 3:
        return Street.FLOP
    elif board_card_count == 4:
        return Street.TURN
    elif board_card_count == 5:
        return Street.RIVER
    return Street.UNKNOWN


def _map_pokerkit_action(action_str: str) -> ActionType:
    action_lower = action_str.lower()
    if "fold" in action_lower:
        return ActionType.FOLD
    elif "check" in action_lower:
        return ActionType.CHECK
    elif "call" in action_lower:
        return ActionType.CALL
    elif "bet" in action_lower:
        return ActionType.BET
    elif "raise" in action_lower or "cbr" in action_lower:
        return ActionType.RAISE
    elif "all" in action_lower or "allin" in action_lower:
        return ActionType.ALL_IN
    return ActionType.NO_ACTION


def calculate_bet_sizing_category(bet_amount: int, pot_size: int) -> str:
    if pot_size <= 0:
        return BetSizingCategory.BET_OVER_100
    ratio = bet_amount / pot_size
    if ratio < 0.33:
        return BetSizingCategory.BET_0_33
    elif ratio < 0.66:
        return BetSizingCategory.BET_33_66
    elif ratio < 1.0:
        return BetSizingCategory.BET_66_100
    else:
        return BetSizingCategory.BET_OVER_100


def extract_actions_from_hand_history(hh: HandHistory) -> Iterator[ParsedAction]:
    players = list(hh.players) if hh.players else []
    actions = hh.actions if hh.actions else []
    antes = list(hh.antes) if hh.antes else []
    blinds_or_straddles = list(hh.blinds_or_straddles) if hh.blinds_or_straddles else []

    current_street = Street.PREFLOP
    board_cards = 0
    pot_size = sum(antes) + sum(blinds_or_straddles)
    player_bets: dict[str, int] = {}
    for i, player_name in enumerate(players):
        if i < len(blinds_or_straddles):
            player_bets[player_name] = blinds_or_straddles[i]
        else:
            player_bets[player_name] = 0

    for action_str in actions:
        action_str = action_str.strip()
        if not action_str:
            continue

        parts = action_str.split()
        if len(parts) < 2:
            continue

        actor = parts[0]

        if actor == "d":
            action_code = parts[1] if len(parts) > 1 else ""
            if action_code == "db":
                cards_str = parts[2] if len(parts) > 2 else ""
                new_cards = len(cards_str) // 2 if cards_str else 0
                board_cards += new_cards
                current_street = _get_street_from_board_count(board_cards)
                for pn in players:
                    player_bets[pn] = 0
            continue

        if not actor.startswith("p"):
            continue

        try:
            player_idx = int(actor[1:]) - 1
        except ValueError:
            continue

        if player_idx < 0 or player_idx >= len(players):
            continue

        player_name = players[player_idx]
        action_code = parts[1] if len(parts) > 1 else ""
        amount = 0

        if len(parts) > 2:
            try:
                amount = int(parts[2])
            except ValueError:
                pass

        action_type = _map_pokerkit_action(action_code)
        if action_type == ActionType.NO_ACTION:
            continue

        current_pot_size = pot_size

        yield ParsedAction(
            street=current_street,
            player_name=player_name,
            action_type=action_type,
            amount=amount,
            pot_size_before_action=current_pot_size,
        )

        if action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            old_bet = player_bets.get(player_name, 0)
            new_contribution = amount - old_bet
            if new_contribution > 0:
                pot_size += new_contribution
            player_bets[player_name] = amount


def increment_player_stats(
    player_stats: PlayerStats,
    hh: HandHistory,
) -> None:
    players = list(hh.players) if hh.players else []
    player_name = player_stats.player_name

    if player_name not in players:
        return

    player_index = players.index(player_name)
    num_players = len(players)
    table_type = player_stats.table_type

    all_in_list: list[str] = []
    active_players = list(players)
    position = get_player_position(player_index, num_players)
    last_player_action = ActionType.FOLD
    player_put_money_in_pot = False
    player_folded_or_all_in = False

    num_raises = 0
    num_callers = 0
    current_street = Street.PREFLOP

    for action in extract_actions_from_hand_history(hh):
        if action.street != current_street:
            current_street = action.street
            num_raises = 0
            num_callers = 0

        if current_street == Street.PREFLOP:
            if player_folded_or_all_in or len(active_players) <= 1:
                continue

            if action.player_name == player_name:
                current_num_players = len(active_players) + len(all_in_list)
                in_pos = is_in_position(active_players, player_name, current_num_players)

                preflop_params = PreFlopParams(
                    table_type=table_type,
                    position=position,
                    num_callers=min(num_callers, 1),
                    num_raises=min(num_raises, 2),
                    num_active_players=current_num_players,
                    previous_action=last_player_action,
                    in_position_on_flop=in_pos,
                )

                try:
                    idx = preflop_params.to_index()
                    if 0 <= idx < len(player_stats.preflop_stats):
                        player_stats.preflop_stats[idx].add_sample(action.action_type)
                except (ValueError, AssertionError):
                    pass

                if action.action_type in (ActionType.FOLD, ActionType.ALL_IN):
                    player_folded_or_all_in = True

                if action.action_type in (
                    ActionType.RAISE,
                    ActionType.BET,
                    ActionType.CALL,
                    ActionType.ALL_IN,
                ):
                    player_put_money_in_pot = True

                last_player_action = action.action_type
            else:
                if action.action_type == ActionType.FOLD:
                    if action.player_name in active_players:
                        active_players.remove(action.player_name)
                elif action.action_type == ActionType.ALL_IN:
                    if action.player_name in active_players:
                        active_players.remove(action.player_name)
                        all_in_list.append(action.player_name)

            if action.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
                num_raises += 1
                num_callers = 0
            elif action.action_type == ActionType.CALL:
                num_callers += 1

        else:
            if player_folded_or_all_in or len(active_players) <= 1:
                continue

            if action.player_name == player_name:
                current_num_players = len(active_players) + len(all_in_list)
                in_pos = is_in_position(active_players, player_name, current_num_players)

                postflop_params = PostFlopParams(
                    table_type=table_type,
                    street=current_street,
                    round=0,
                    prev_action=last_player_action,
                    num_bets=min(num_raises, 2),
                    in_position=in_pos,
                    num_players=min(current_num_players, 3),
                )

                try:
                    idx = postflop_params.to_index()
                    if 0 <= idx < len(player_stats.postflop_stats):
                        sizing_category = None
                        if action.action_type == ActionType.BET:
                            sizing_category = calculate_bet_sizing_category(
                                action.amount, action.pot_size_before_action
                            )
                        player_stats.postflop_stats[idx].add_sample(
                            action.action_type, sizing_category=sizing_category
                        )
                except (ValueError, AssertionError):
                    pass

                if action.action_type in (ActionType.FOLD, ActionType.ALL_IN):
                    player_folded_or_all_in = True

                last_player_action = action.action_type
            else:
                if action.action_type == ActionType.FOLD:
                    if action.player_name in active_players:
                        active_players.remove(action.player_name)
                elif action.action_type == ActionType.ALL_IN:
                    if action.player_name in active_players:
                        active_players.remove(action.player_name)
                        all_in_list.append(action.player_name)

            if action.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
                num_raises += 1

    player_stats.vpip.add_sample(player_put_money_in_pot)


def build_player_stats_from_hands(
    hands: list[HandHistory],
    table_type: TableType,
) -> dict[str, PlayerStats]:
    player_names: set[str] = set()
    for hh in hands:
        if hh.players:
            player_names.update(hh.players)

    player_stats_map: dict[str, PlayerStats] = {}
    for name in player_names:
        player_stats_map[name] = PlayerStats(player_name=name, table_type=table_type)

    for hh in hands:
        if not hh.players:
            continue
        for player_name in hh.players:
            if player_name in player_stats_map:
                increment_player_stats(player_stats_map[player_name], hh)

    return player_stats_map


def calculate_total_hands(player_stats: PlayerStats) -> int:
    total = 0
    all_params = PreFlopParams.get_all_params(player_stats.table_type)
    for i, params in enumerate(all_params):
        if params.previous_action == ActionType.FOLD:
            total += player_stats.preflop_stats[i].total_samples()
    return total


def calculate_pfr(player_stats: PlayerStats) -> tuple[int, int]:
    total_ad = ActionStats()
    all_params = PreFlopParams.get_all_params(player_stats.table_type)
    for i, params in enumerate(all_params):
        if params.num_raises == 0:
            total_ad.append(player_stats.preflop_stats[i])
    return total_ad.bet_raise_samples, total_ad.total_samples()


def calculate_aggression(player_stats: PlayerStats) -> tuple[int, int]:
    total_forced = ActionStats()
    total_unforced = ActionStats()
    all_params = PostFlopParams.get_all_params(player_stats.table_type)
    for i, params in enumerate(all_params):
        if params.num_bets > 0:
            total_forced.append(player_stats.postflop_stats[i])
        else:
            total_unforced.append(player_stats.postflop_stats[i])
    raise_count = total_forced.bet_raise_samples + total_unforced.bet_raise_samples
    total_count = raise_count + total_forced.check_call_samples
    return raise_count, total_count


def calculate_wtp(player_stats: PlayerStats) -> tuple[int, int]:
    total_forced = ActionStats()
    all_params = PostFlopParams.get_all_params(player_stats.table_type)
    for i, params in enumerate(all_params):
        if params.num_bets > 0:
            total_forced.append(player_stats.postflop_stats[i])
    positive_count = total_forced.check_call_samples + total_forced.bet_raise_samples
    total_count = positive_count + total_forced.fold_samples
    return positive_count, total_count
