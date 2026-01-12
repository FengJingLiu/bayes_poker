from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pokerkit import HandHistory

from .enums import ActionType, Position, Street, TableType
from .models import ActionStats, PlayerStats, StatValue
from .params import PostFlopParams, PreFlopParams

if TYPE_CHECKING:
    pass


@dataclass
class ParsedAction:
    street: Street
    player_name: str
    action_type: ActionType
    amount: int


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


def extract_actions_from_hand_history(hh: HandHistory) -> Iterator[ParsedAction]:
    players = list(hh.players) if hh.players else []
    actions = hh.actions if hh.actions else []

    current_street = Street.PREFLOP
    board_cards = 0

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

        yield ParsedAction(
            street=current_street,
            player_name=player_name,
            action_type=action_type,
            amount=amount,
        )


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
                        player_stats.postflop_stats[idx].add_sample(action.action_type)
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
