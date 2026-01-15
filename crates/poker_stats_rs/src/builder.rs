use crate::{
    ActionType, BetSizingCategory, Hand, PlayerStats, Position, PostFlopParams, PreFlopParams,
    PreflopPotType, Street, TableType,
};
use rayon::prelude::*;
use std::collections::HashMap;

pub fn build_player_stats_parallel(hands: &[Hand], table_type: TableType) -> Vec<PlayerStats> {
    let mut player_hands: HashMap<String, Vec<&Hand>> = HashMap::new();

    for hand in hands {
        for player in &hand.players {
            player_hands.entry(player.clone()).or_default().push(hand);
        }
    }

    let player_names: Vec<String> = player_hands.keys().cloned().collect();

    player_names
        .par_iter()
        .map(|player_name| {
            let hands_for_player = &player_hands[player_name];
            compute_stats_for_player(player_name, hands_for_player, table_type)
        })
        .collect()
}

fn compute_stats_for_player(
    player_name: &str,
    hands: &[&Hand],
    table_type: TableType,
) -> PlayerStats {
    let mut stats = PlayerStats::new(player_name.to_string(), table_type);

    for hand in hands {
        process_hand_for_player(&mut stats, hand, player_name);
    }

    stats
}

fn process_hand_for_player(stats: &mut PlayerStats, hand: &Hand, player_name: &str) {
    let player_index = match hand.get_player_index(player_name) {
        Some(idx) => idx,
        None => return,
    };

    let num_players = hand.players.len();
    let position = Position::from_index(player_index, num_players);

    let mut active_players: Vec<String> = hand.players.clone();
    let mut all_in_players: Vec<String> = Vec::new();

    let mut last_player_action = ActionType::Fold;
    let mut player_put_money_in_pot = false;
    let mut player_folded_or_allin = false;

    let mut num_raises = 0i32;
    let mut num_callers = 0i32;

    let mut preflop_raise_count = 0i32;
    let mut preflop_aggressor: Option<String> = None;

    for action in &hand.actions {
        if action.get_street() != Street::PreFlop {
            continue;
        }
        if player_folded_or_allin || active_players.len() <= 1 {
            break;
        }

        let action_type = action.get_action_type();

        if action.player == player_name {
            let num_active = active_players.len() + all_in_players.len();
            let in_pos = in_position(&active_players, player_name, num_active);

            let preflop_params = PreFlopParams::new(
                stats.table_type,
                position,
                num_callers.min(1),
                num_raises.min(2),
                num_active as i32,
                last_player_action,
                in_pos,
            );

            let idx = preflop_params.to_index();
            if idx < stats.preflop_stats.len() {
                stats.preflop_stats[idx].add_sample(action_type, None);
            }

            if action_type == ActionType::Fold || action_type == ActionType::AllIn {
                player_folded_or_allin = true;
            }

            if action_type.is_raise_action() || action_type == ActionType::Call {
                player_put_money_in_pot = true;
            }

            last_player_action = action_type;
        } else {
            match action_type {
                ActionType::Fold => {
                    active_players.retain(|p| p != &action.player);
                }
                ActionType::AllIn => {
                    active_players.retain(|p| p != &action.player);
                    all_in_players.push(action.player.clone());
                }
                _ => {}
            }
        }

        if action_type.is_raise_action() {
            num_raises += 1;
            num_callers = 0;
            preflop_raise_count += 1;
            preflop_aggressor = Some(action.player.clone());
        } else if action_type == ActionType::Call {
            num_callers += 1;
        }
    }

    stats.vpip_total += 1;
    if player_put_money_in_pot {
        stats.vpip_positive += 1;
    }

    let pot_type = PreflopPotType::from_raise_count(preflop_raise_count);
    let is_aggressor = preflop_aggressor
        .as_ref()
        .map(|s| s == player_name)
        .unwrap_or(false);

    for street in [Street::Flop, Street::Turn, Street::River] {
        if player_folded_or_allin || active_players.len() <= 1 {
            break;
        }

        let mut round = 0i32;
        let mut num_bets = 0i32;

        for action in &hand.actions {
            if action.get_street() != street {
                continue;
            }

            let action_type = action.get_action_type();

            if action.player == player_name {
                let num_active = active_players.len() + all_in_players.len();
                let in_pos = in_position(&active_players, player_name, num_active);

                let postflop_params = PostFlopParams::new(
                    stats.table_type,
                    street,
                    round.min(1),
                    last_player_action,
                    num_bets.min(2),
                    in_pos,
                    (num_active as i32).min(3),
                    pot_type,
                    is_aggressor,
                );

                let idx = postflop_params.to_index();
                if idx < stats.postflop_stats.len() {
                    let sizing =
                        if action_type == ActionType::Bet || action_type == ActionType::Raise {
                            action
                                .get_pot_percentage()
                                .map(BetSizingCategory::from_pot_percentage)
                        } else {
                            None
                        };
                    stats.postflop_stats[idx].add_sample(action_type, sizing);
                }

                if action_type == ActionType::Fold || action_type == ActionType::AllIn {
                    player_folded_or_allin = true;
                    break;
                }

                last_player_action = action_type;
                round += 1;
            } else {
                match action_type {
                    ActionType::Fold => {
                        active_players.retain(|p| p != &action.player);
                    }
                    ActionType::AllIn => {
                        active_players.retain(|p| p != &action.player);
                        all_in_players.push(action.player.clone());
                    }
                    _ => {}
                }
            }

            if action_type.is_raise_action() {
                num_bets += 1;
            }
        }
    }
}

fn in_position(active_players: &[String], player_name: &str, num_players: usize) -> bool {
    if active_players.is_empty() {
        return false;
    }
    if num_players == 2 {
        active_players.first().map(|s| s.as_str()) == Some(player_name)
    } else {
        active_players.last().map(|s| s.as_str()) == Some(player_name)
    }
}
