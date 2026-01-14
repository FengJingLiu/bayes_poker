use serde::Deserialize;
use std::fs;
use std::path::Path;
use crate::{Action, Hand};

#[derive(Debug, Deserialize)]
struct PhhsHand {
    #[serde(default)]
    players: Vec<String>,
    #[serde(default)]
    actions: Vec<String>,
    #[serde(default)]
    blinds_or_straddles: Vec<i64>,
    #[serde(default)]
    antes: Vec<i64>,
    #[serde(default)]
    seat_count: Option<usize>,
}

pub fn parse_phhs_file(path: &Path) -> Vec<Hand> {
    let content = match fs::read_to_string(path) {
        Ok(c) => c.replace("\r\n", "\n"),
        Err(_) => return Vec::new(),
    };

    let mut hands = Vec::new();
    let mut current_block = String::new();
    let mut in_block = false;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            if in_block && !current_block.is_empty() {
                if let Some(hand) = parse_single_hand(&current_block) {
                    hands.push(hand);
                }
            }
            current_block.clear();
            in_block = true;
        } else if in_block {
            current_block.push_str(line);
            current_block.push('\n');
        }
    }

    if in_block && !current_block.is_empty() {
        if let Some(hand) = parse_single_hand(&current_block) {
            hands.push(hand);
        }
    }

    hands
}

fn parse_single_hand(toml_content: &str) -> Option<Hand> {
    let phhs: PhhsHand = toml::from_str(toml_content).ok()?;
    
    if phhs.players.is_empty() {
        return None;
    }

    let blinds = phhs.blinds_or_straddles;
    let antes = phhs.antes;
    let players = phhs.players;

    let mut pot_size: i64 = antes.iter().sum::<i64>() + blinds.iter().sum::<i64>();
    let mut current_bet: i64 = blinds.iter().cloned().max().unwrap_or(0);
    let mut player_bets: Vec<i64> = blinds.iter().cloned().chain(std::iter::repeat(0)).take(players.len()).collect();
    
    let mut actions = Vec::new();
    let mut current_street = "preflop";
    let mut board_cards = 0;

    for action_str in &phhs.actions {
        let action_str = action_str.trim();
        if action_str.is_empty() {
            continue;
        }

        let parts: Vec<&str> = action_str.split_whitespace().collect();
        if parts.len() < 2 {
            continue;
        }

        let actor = parts[0];

        if actor == "d" {
            let action_code = parts.get(1).copied().unwrap_or("");
            if action_code == "db" {
                let cards_str = parts.get(2).copied().unwrap_or("");
                let new_cards = cards_str.len() / 2;
                board_cards += new_cards;
                current_street = match board_cards {
                    3 => "flop",
                    4 => "turn",
                    5 => "river",
                    _ => current_street,
                };
                for bet in player_bets.iter_mut() {
                    *bet = 0;
                }
                current_bet = 0;
            }
            continue;
        }

        if !actor.starts_with('p') {
            continue;
        }

        let player_idx: usize = match actor[1..].parse::<usize>() {
            Ok(n) if n > 0 && n <= players.len() => n - 1,
            _ => continue,
        };

        let player_name = &players[player_idx];
        let action_code = parts.get(1).copied().unwrap_or("");
        let mut amount: i64 = parts.get(2).and_then(|s| s.parse().ok()).unwrap_or(0);

        let action_type;
        let old_bet = player_bets[player_idx];

        match action_code.to_lowercase().as_str() {
            "f" => {
                action_type = "fold";
            }
            "cc" => {
                if current_bet <= old_bet {
                    action_type = "check";
                } else {
                    action_type = "call";
                    if amount <= 0 {
                        amount = current_bet;
                    }
                }
            }
            "cbr" => {
                action_type = "raise";
            }
            "bet" | "b" => {
                action_type = "bet";
            }
            _ => continue,
        }

        let call_amount = current_bet - old_bet;
        
        actions.push(Action {
            street: current_street.to_string(),
            player: player_name.clone(),
            action_type: action_type.to_string(),
            amount,
            pot_size_before: pot_size,
            call_amount: call_amount.max(0),
        });

        if action_type == "call" || action_type == "bet" || action_type == "raise" {
            let new_contribution = amount - old_bet;
            if new_contribution > 0 {
                pot_size += new_contribution;
            }
            player_bets[player_idx] = amount;
            if amount > current_bet {
                current_bet = amount;
            }
        }
    }

    Some(Hand {
        players,
        actions,
        blinds: blinds.clone(),
        antes: antes.clone(),
    })
}

pub fn load_phhs_directory(dir_path: &Path) -> Vec<Hand> {
    use walkdir::WalkDir;

    let mut all_hands = Vec::new();
    
    for entry in WalkDir::new(dir_path)
        .into_iter()
        .filter_map(|e| e.ok())
    {
        let path = entry.path();
        if path.extension().map(|e| e == "phhs").unwrap_or(false) {
            let hands = parse_phhs_file(path);
            all_hands.extend(hands);
        }
    }

    all_hands
}
