use std::collections::{HashMap, HashSet};
use anyhow::Result;
use crate::*;

#[derive(Debug, Default)]
pub struct EtlTransformer;

impl EtlTransformer {
    pub fn transform_chunk(&self, hands: &[ParsedHand]) -> Result<EtlBatch> {
        let mut batch = EtlBatch::default();
        for hand in hands {
            let transformed = self.transform_hand(hand)?;
            batch.hands.extend(transformed.hands);
            batch.player_hand_facts.extend(transformed.player_hand_facts);
            batch.player_actions.extend(transformed.player_actions);
        }
        Ok(batch)
    }

    pub fn transform_hand(&self, hand: &ParsedHand) -> Result<EtlBatch> {
        let mut batch = EtlBatch::default();
        let hand_hash = compute_hand_hash(
            &hand.players.iter().map(|p| p.player_name.clone()).collect::<Vec<_>>(),
            &hand.canonical_actions,
        );

        let position_map = build_position_map(hand.button_seat, &hand.players);
        let param_index_by_action = build_action_param_index_map(hand, &position_map);
        let winner_set: HashSet<&str> = hand.winner_names.iter().map(String::as_str).collect();
        let showdown_set: HashSet<&str> = hand.showdown_players.iter().map(String::as_str).collect();
        let shown_holdcard_indexes_by_player: HashMap<&str, u16> = hand
            .shown_holdcard_indexes_by_player
            .iter()
            .map(|(player_name, holdcard_index)| (player_name.as_str(), *holdcard_index))
            .collect();
        let returned_cents_by_player: HashMap<&str, i64> = hand
            .returned_cents_by_player
            .iter()
            .fold(HashMap::new(), |mut acc, (player_name, cents)| {
                *acc.entry(player_name.as_str()).or_insert(0) += *cents;
                acc
            });

        let mut player_facts: HashMap<String, PlayerFact> = hand.players.iter().map(|p| {
            (p.player_name.clone(), PlayerFact {
                seat_no: p.seat_no as u8,
                position: *position_map.get(&p.player_name).unwrap_or(&Position::UTG) as u8,
                contributed_cents: p.blind_post_cents,
                ..Default::default()
            })
        }).collect();

        let mut active_players: HashSet<String> = hand.players.iter().map(|p| p.player_name.clone()).collect();
        let mut preflop_raise_count = 0i32;
        let mut num_raises = 0i32;
        let mut num_callers = 0i32;

        for action in &hand.actions {
            if action.action_type == ActionType::Fold {
                active_players.remove(&action.player_name);
            }

            if !player_facts.contains_key(&action.player_name) {
                continue;
            }

            if let Some(fact) = player_facts.get_mut(&action.player_name) {
                fact.contributed_cents += action.delta_cents;
            }

            if action.street == Street::PreFlop {
                if let Some(fact) = player_facts.get_mut(&action.player_name) {
                    if matches!(action.action_type, ActionType::Call | ActionType::Bet | ActionType::Raise | ActionType::AllIn) {
                        fact.is_vpip = 1;
                    }
                    if action.action_type.is_raise_action() {
                        fact.is_pfr = 1;
                        if preflop_raise_count == 1 { fact.is_3bet = 1; }
                        if preflop_raise_count == 2 { fact.is_4bet = 1; }
                    }
                }

                if action.action_type.is_raise_action() {
                    preflop_raise_count += 1;
                    num_raises += 1;
                    num_callers = 0;
                } else if action.action_type == ActionType::Call {
                    num_callers += 1;
                }
            }

            let (preflop_param_index, postflop_param_index) = param_index_by_action
                .get(&action.action_index)
                .copied()
                .unwrap_or((None, None));

            batch.player_actions.push(PlayerActionRow {
                hand_hash: hand_hash.clone(),
                player_name: action.player_name.clone(),
                action_index: action.action_index,
                street: action.street as u8,
                action_type: action.action_type as u8,
                seat_no: player_facts[&action.player_name].seat_no,
                position: player_facts[&action.player_name].position,
                amount_cents: action.delta_cents,
                total_bet_cents: action.total_bet_cents,
                pot_before_action_cents: action.pot_before_action_cents,
                call_amount_cents: action.call_amount_cents,
                num_callers: num_callers.max(0) as u8,
                num_raises: num_raises.max(0) as u8,
                spr: if action.pot_before_action_cents > 0 {
                    action.delta_cents as f32 / action.pot_before_action_cents as f32
                } else { 0.0 },
                sizing_pct: if action.pot_before_action_cents > 0 && action.action_type.is_raise_action() {
                    Some(action.delta_cents as f32 / action.pot_before_action_cents as f32)
                } else { None },
                preflop_param_index,
                postflop_param_index,
                is_vpip: player_facts[&action.player_name].is_vpip,
                is_pfr: player_facts[&action.player_name].is_pfr,
                is_3bet: player_facts[&action.player_name].is_3bet,
                is_4bet: player_facts[&action.player_name].is_4bet,
                is_saw_flop: 0,
                is_saw_turn: 0,
                is_saw_river: 0,
                is_went_to_showdown: 0,
                is_winner: 0,
                is_winner_at_showdown: 0,
            });
        }

        let mut active_at_flop: HashSet<String> = HashSet::new();
        let mut active_at_turn: HashSet<String> = HashSet::new();
        let mut active_at_river: HashSet<String> = HashSet::new();

        if hand.saw_flop {
            active_at_flop = active_players.iter()
                .filter(|p| {
                    hand.actions.iter()
                        .filter(|a| a.street == Street::PreFlop && &a.player_name == *p)
                        .all(|a| a.action_type != ActionType::Fold)
                })
                .cloned()
                .collect();
        }

        if hand.saw_turn {
            active_at_turn = active_players.iter()
                .filter(|p| {
                    hand.actions.iter()
                        .filter(|a| (a.street == Street::PreFlop || a.street == Street::Flop) && &a.player_name == *p)
                        .all(|a| a.action_type != ActionType::Fold)
                })
                .cloned()
                .collect();
        }

        if hand.saw_river {
            active_at_river = active_players.iter()
                .filter(|p| {
                    hand.actions.iter()
                        .filter(|a| a.street != Street::River && &a.player_name == *p)
                        .all(|a| a.action_type != ActionType::Fold)
                })
                .cloned()
                .collect();
        }

        for player in &hand.players {
            let fact = &player_facts[&player.player_name];
            let returned_cents = returned_cents_by_player
                .get(player.player_name.as_str())
                .copied()
                .unwrap_or(0);
            let contributed_cents = fact.contributed_cents.saturating_sub(returned_cents);
            let is_saw_flop = active_at_flop.contains(&player.player_name) as u8;
            let is_saw_turn = active_at_turn.contains(&player.player_name) as u8;
            let is_saw_river = active_at_river.contains(&player.player_name) as u8;
            let is_went_to_showdown = showdown_set.contains(player.player_name.as_str()) as u8;
            let is_winner = winner_set.contains(player.player_name.as_str()) as u8;
            let is_winner_at_showdown = (is_went_to_showdown == 1 && is_winner == 1) as u8;

            batch.player_hand_facts.push(PlayerHandFactRow {
                hand_hash: hand_hash.clone(),
                player_name: player.player_name.clone(),
                seat_no: fact.seat_no,
                position: fact.position,
                holdcard_index: shown_holdcard_indexes_by_player
                    .get(player.player_name.as_str())
                    .copied(),
                net_cents: hand.collected_cents_by_player.iter()
                    .find(|(n, _)| n == &player.player_name)
                    .map(|(_, c)| *c)
                    .unwrap_or(0) - contributed_cents,
                contributed_cents,
                is_vpip: fact.is_vpip,
                is_pfr: fact.is_pfr,
                is_3bet: fact.is_3bet,
                is_4bet: fact.is_4bet,
                is_saw_flop,
                is_saw_turn,
                is_saw_river,
                is_went_to_showdown,
                is_winner,
                is_winner_at_showdown,
            });
        }

        batch.hands.push(HandRow {
            hand_hash,
            source_name: hand.source_name.clone(),
            source_hand_id: hand.source_hand_id.clone(),
            played_at: hand.played_at.map(|dt| dt.timestamp() as u32),
            table_name: hand.table_name.clone(),
            board: hand.board.clone(),
            seat_count: hand.seat_count as u8,
            table_type: hand.table_type as u8,
            small_blind_cents: hand.small_blind_cents,
            big_blind_cents: hand.big_blind_cents,
            cash_drop_cents: hand.cash_drop_cents,
            insurance_cost_cents: hand.insurance_cost_cents,
            raw_text: hand.raw_text.clone(),
            normalized_text: hand.normalized_text.clone(),
        });

        Ok(batch)
    }
}

#[derive(Debug, Default, Clone)]
struct PlayerFact {
    seat_no: u8,
    position: u8,
    contributed_cents: i64,
    is_vpip: u8,
    is_pfr: u8,
    is_3bet: u8,
    is_4bet: u8,
}

#[derive(Debug, Clone)]
struct ActionComputationState {
    active_players: Vec<String>,
    all_in_players: Vec<String>,
    last_action_by_player: HashMap<String, ActionType>,
    current_street: Street,
    num_raises: i32,
    num_callers: i32,
    preflop_raise_count: i32,
    preflop_aggressor: Option<String>,
}

fn build_position_map(button_seat: usize, players: &[SeatPlayer]) -> HashMap<String, Position> {
    let mut map = HashMap::new();
    let seat_count = players.len();

    // 按钮位置后的环形顺序：BTN -> SB -> BB -> UTG -> HJ -> CO
    let mut sorted_players: Vec<_> = players.iter().collect();
    sorted_players.sort_by_key(|p| {
        let offset = if p.seat_no >= button_seat {
            p.seat_no - button_seat
        } else {
            p.seat_no + seat_count - button_seat
        };
        offset
    });

    for (idx, player) in sorted_players.iter().enumerate() {
        let position = if seat_count == 2 {
            if idx == 0 { Position::SmallBlind } else { Position::BigBlind }
        } else if idx == 0 {
            Position::Button
        } else if idx == 1 {
            Position::SmallBlind
        } else if idx == 2 {
            Position::BigBlind
        } else if idx == 3 {
            Position::UTG
        } else if idx == 4 {
            Position::HJ
        } else {
            Position::CutOff
        };
        map.insert(player.player_name.clone(), position);
    }
    map
}

fn build_action_param_index_map(
    hand: &ParsedHand,
    position_map: &HashMap<String, Position>,
) -> HashMap<u32, (Option<u16>, Option<u16>)> {
    let mut result: HashMap<u32, (Option<u16>, Option<u16>)> = HashMap::new();
    let mut state = ActionComputationState {
        active_players: build_metrics_ordered_players(hand, position_map),
        all_in_players: Vec::new(),
        last_action_by_player: hand
            .players
            .iter()
            .map(|player| (player.player_name.clone(), ActionType::Fold))
            .collect(),
        current_street: Street::PreFlop,
        num_raises: 0,
        num_callers: 0,
        preflop_raise_count: 0,
        preflop_aggressor: None,
    };

    for action in &hand.actions {
        if action.street != state.current_street {
            state.current_street = action.street;
            state.num_raises = 0;
            state.num_callers = 0;
        }

        let preflop_param_index = if action.street == Street::PreFlop {
            Some(build_preflop_param_index(
                hand,
                position_map,
                &state,
                &action.player_name,
            ))
        } else {
            None
        };
        let postflop_param_index = if action.street != Street::PreFlop {
            Some(build_postflop_param_index(
                hand,
                position_map,
                &state,
                action,
            ))
        } else {
            None
        };
        result.insert(
            action.action_index,
            (
                preflop_param_index.map(|idx| idx as u16),
                postflop_param_index.map(|idx| idx as u16),
            ),
        );

        state
            .last_action_by_player
            .insert(action.player_name.clone(), action.action_type);

        match action.action_type {
            ActionType::Fold => {
                state.active_players.retain(|player| player != &action.player_name);
            }
            ActionType::AllIn => {
                state.active_players.retain(|player| player != &action.player_name);
                if !state.all_in_players.contains(&action.player_name) {
                    state.all_in_players.push(action.player_name.clone());
                }
            }
            _ => {}
        }

        if action.street == Street::PreFlop {
            if action.action_type.is_raise_action() {
                state.num_raises += 1;
                state.num_callers = 0;
                state.preflop_raise_count += 1;
                state.preflop_aggressor = Some(action.player_name.clone());
            } else if action.action_type == ActionType::Call {
                state.num_callers += 1;
            }
        } else if action.action_type.is_raise_action() {
            state.num_raises += 1;
        }
    }

    result
}

fn build_preflop_param_index(
    hand: &ParsedHand,
    position_map: &HashMap<String, Position>,
    state: &ActionComputationState,
    player_name: &str,
) -> usize {
    let num_active_players = state.active_players.len() + state.all_in_players.len();
    let in_position_on_flop = is_in_position(
        &state.active_players,
        player_name,
        num_active_players,
    );
    let position = *position_map
        .get(player_name)
        .unwrap_or(&Position::UTG);
    let previous_action = *state
        .last_action_by_player
        .get(player_name)
        .unwrap_or(&ActionType::Fold);

    PreFlopParams::new(
        hand.table_type,
        position,
        state.num_callers.min(1),
        state.num_raises.min(2),
        num_active_players as i32,
        previous_action,
        in_position_on_flop,
    )
    .to_index()
}

fn build_postflop_param_index(
    hand: &ParsedHand,
    position_map: &HashMap<String, Position>,
    state: &ActionComputationState,
    action: &ParsedAction,
) -> usize {
    let num_active_players = state.active_players.len() + state.all_in_players.len();
    let in_position = is_in_position(
        &state.active_players,
        &action.player_name,
        num_active_players,
    );
    let previous_action = *state
        .last_action_by_player
        .get(&action.player_name)
        .unwrap_or(&ActionType::Fold);
    let preflop_pot_type = PreflopPotType::from_raise_count(state.preflop_raise_count);
    let is_preflop_aggressor = state
        .preflop_aggressor
        .as_ref()
        .map(|player| player == &action.player_name)
        .unwrap_or(false);

    let _position = position_map.get(&action.player_name);

    PostFlopParams::new(
        hand.table_type,
        action.street,
        0,
        previous_action,
        state.num_raises.min(2),
        in_position,
        (num_active_players as i32).min(3),
        preflop_pot_type,
        is_preflop_aggressor,
    )
    .to_index()
}

fn build_metrics_ordered_players(
    hand: &ParsedHand,
    position_map: &HashMap<String, Position>,
) -> Vec<String> {
    let mut ordered_players: Vec<&SeatPlayer> = hand.players.iter().collect();
    ordered_players.sort_by_key(|player| {
        position_map
            .get(&player.player_name)
            .copied()
            .unwrap_or(Position::UTG) as u8
    });
    ordered_players
        .into_iter()
        .map(|player| player.player_name.clone())
        .collect()
}

fn is_in_position(active_players: &[String], player_name: &str, num_players: usize) -> bool {
    if active_players.is_empty() {
        return false;
    }
    if num_players == 2 {
        return active_players.first().map(String::as_str) == Some(player_name);
    }
    active_players.last().map(String::as_str) == Some(player_name)
}

#[cfg(test)]
mod tests {
    use super::EtlTransformer;
    use crate::GgTxtParser;

    const OPEN_WIN_HAND_TEXT: &str = r#"PokerStars Hand #03305054561: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:27
Table 'GG_RushAndCash19527879' 6-max Seat #1 is the button
Seat 1: shadro ($1.40 in chips)
Seat 2: 6uperUs3r ($3.35 in chips)
Seat 3: Dekadence ($2.12 in chips)
Seat 4: RedZitteraal ($2.86 in chips)
Seat 5: aladepollo ($1.23 in chips)
Seat 6: Konetblizok ($5.18 in chips)
6uperUs3r: posts small blind $0.01
Dekadence: posts big blind $0.02
*** HOLE CARDS ***
RedZitteraal: raises $0.04 to $0.06
aladepollo: folds
Konetblizok: folds
shadro: folds
6uperUs3r: folds
Dekadence: folds
Uncalled bet ($0.04) returned to RedZitteraal
*** SHOWDOWN ***
RedZitteraal collected $0.05 from pot
*** SUMMARY ***
Total pot $0.05 | Rake $0.00 | Jackpot $0.00 | Bingo $0 | Fortune $0 | Tax $0
"#;

    const POSTFLOP_HAND_TEXT: &str = r#"PokerStars Hand #03305054562: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:27
Table 'GG_RushAndCash19527880' 6-max Seat #1 is the button
Seat 1: maikuto ($2.00 in chips)
Seat 2: S-pb2784 ($2.00 in chips)
Seat 3: Assum- ($2.74 in chips)
Seat 4: bldLucas ($2.08 in chips)
Seat 5: Tsui Shu ($1.94 in chips)
Seat 6: Patito93 ($1.62 in chips)
S-pb2784: posts small blind $0.01
Assum-: posts big blind $0.02
*** HOLE CARDS ***
bldLucas: folds
Tsui Shu: folds
Patito93: folds
maikuto: raises $0.03 to $0.05
S-pb2784: folds
Assum-: calls $0.03
*** FLOP *** [Jh 3s 6c]
Assum-: checks
maikuto: bets $0.04
Assum-: calls $0.04
*** TURN *** [Jh 3s 6c] [2d]
Assum-: checks
maikuto: checks
*** RIVER *** [Jh 3s 6c 2d] [4c]
Assum-: bets $0.25
maikuto: folds
Uncalled bet ($0.25) returned to Assum-
*** SHOWDOWN ***
Assum- collected $0.18 from pot
*** SUMMARY ***
Total pot $0.19 | Rake $0.01 | Jackpot $0.00 | Bingo $0 | Fortune $0 | Tax $0
"#;

    const SUMMARY_SHOWED_HAND_TEXT: &str = r#"PokerStars Hand #03305054560: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:27
Table 'GG_RushAndCash19527878' 6-max Seat #1 is the button
Seat 1: mocos ($2.00 in chips)
Seat 2: MoonKiss ($2.26 in chips)
Seat 3: allin990 ($2.04 in chips)
Seat 4: Leolei ($2.18 in chips)
Seat 5: eleone ($4.38 in chips)
Seat 6: ntzdev ($3.01 in chips)
MoonKiss: posts small blind $0.01
allin990: posts big blind $0.02
*** HOLE CARDS ***
Leolei: folds
eleone: folds
ntzdev: folds
mocos: folds
MoonKiss: raises $0.02 to $0.04
allin990: calls $0.02
*** FLOP *** [5s 4c 2c]
MoonKiss: bets $0.03
allin990: calls $0.03
*** TURN *** [5s 4c 2c] [7c]
MoonKiss: checks
allin990: checks
*** RIVER *** [5s 4c 2c 7c] [Jd]
MoonKiss: checks
allin990: checks
*** SHOWDOWN ***
MoonKiss collected $0.14 from pot
*** SUMMARY ***
Total pot $0.14 | Rake $0.00 | Jackpot $0.00 | Bingo $0 | Fortune $0 | Tax $0
Board [5s 4c 2c 7c Jd]
Seat 1: mocos (button) folded before Flop (didn't bet)
Seat 2: MoonKiss (small blind) showed [As Qs] and won ($0.14)
Seat 3: allin990 (big blind) showed [Ac 8h] and lost
Seat 4: Leolei folded before Flop (didn't bet)
Seat 5: eleone folded before Flop (didn't bet)
Seat 6: ntzdev folded before Flop (didn't bet)
"#;

    const SHOWS_HAND_TEXT: &str = r#"PokerStars Hand #999: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:27
Table 'GG_RushAndCash19520000' 6-max Seat #1 is the button
Seat 1: Alpha ($2.00 in chips)
Seat 2: Bravo ($2.00 in chips)
Seat 3: Charlie ($2.00 in chips)
Seat 4: Delta ($2.00 in chips)
Seat 5: Echo ($2.00 in chips)
Seat 6: Foxtrot ($2.00 in chips)
Bravo: posts small blind $0.01
Charlie: posts big blind $0.02
*** HOLE CARDS ***
Delta: folds
Echo: folds
Foxtrot: folds
Alpha: folds
Bravo: calls $0.01
Charlie: checks
*** FLOP *** [2c 3d 4s]
Bravo: checks
Charlie: checks
*** TURN *** [2c 3d 4s] [5h]
Bravo: checks
Charlie: checks
*** RIVER *** [2c 3d 4s 5h] [6c]
Bravo: bets $0.02
Charlie: calls $0.02
Bravo: shows [5c 5d]
Charlie: shows [8s Js]
*** SHOWDOWN ***
Bravo collected $0.08 from pot
*** SUMMARY ***
Total pot $0.08 | Rake $0.00 | Jackpot $0.00 | Bingo $0 | Fortune $0 | Tax $0
Board [2c 3d 4s 5h 6c]
Seat 1: Alpha (button) folded before Flop (didn't bet)
Seat 2: Bravo (small blind) showed [5c 5d] and won ($0.08)
Seat 3: Charlie (big blind) showed [8s Js] and lost
Seat 4: Delta folded before Flop (didn't bet)
Seat 5: Echo folded before Flop (didn't bet)
Seat 6: Foxtrot folded before Flop (didn't bet)
"#;

    fn parse_single_hand(text: &str) -> crate::ParsedHand {
        let parser = GgTxtParser::default();
        let mut hands = parser.parse_text("sample.txt", text).unwrap();
        assert_eq!(hands.len(), 1);
        hands.remove(0)
    }

    #[test]
    fn transform_hand_preserves_hand_text_columns() {
        let hand = parse_single_hand(OPEN_WIN_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let hand_row = batch.hands.first().unwrap();

        assert_eq!(hand_row.raw_text, OPEN_WIN_HAND_TEXT);
        assert_eq!(hand_row.normalized_text, OPEN_WIN_HAND_TEXT);
    }

    #[test]
    fn transform_hand_uses_total_raise_size_for_action_amounts() {
        let hand = parse_single_hand(OPEN_WIN_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let raise_action = batch.player_actions.first().unwrap();
        let first_fold = batch.player_actions.get(1).unwrap();

        assert_eq!(raise_action.player_name, "RedZitteraal");
        assert_eq!(raise_action.amount_cents, 6);
        assert_eq!(raise_action.total_bet_cents, 6);
        assert_eq!(first_fold.pot_before_action_cents, 9);
    }

    #[test]
    fn transform_hand_accounts_for_uncalled_return_in_player_profit() {
        let hand = parse_single_hand(OPEN_WIN_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let winner_fact = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "RedZitteraal")
            .unwrap();

        assert_eq!(winner_fact.contributed_cents, 2);
        assert_eq!(winner_fact.net_cents, 3);
    }

    #[test]
    fn transform_hand_counts_postflop_contributions_in_player_facts() {
        let hand = parse_single_hand(POSTFLOP_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let hero_fact = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "maikuto")
            .unwrap();
        let villain_fact = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "Assum-")
            .unwrap();

        assert_eq!(hero_fact.contributed_cents, 9);
        assert_eq!(hero_fact.net_cents, -9);
        assert_eq!(villain_fact.contributed_cents, 9);
        assert_eq!(villain_fact.net_cents, 9);
    }

    #[test]
    fn transform_hand_fills_holdcard_index_from_summary_showed_lines() {
        let hand = parse_single_hand(SUMMARY_SHOWED_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let moonkiss = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "MoonKiss")
            .unwrap();
        let allin990 = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "allin990")
            .unwrap();
        let mocos = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "mocos")
            .unwrap();

        assert_eq!(moonkiss.holdcard_index, Some(1297));
        assert_eq!(allin990.holdcard_index, Some(1022));
        assert_eq!(mocos.holdcard_index, None);
    }

    #[test]
    fn transform_hand_fills_holdcard_index_from_showdown_show_lines() {
        let hand = parse_single_hand(SHOWS_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let bravo = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "Bravo")
            .unwrap();
        let charlie = batch
            .player_hand_facts
            .iter()
            .find(|row| row.player_name == "Charlie")
            .unwrap();

        assert_eq!(bravo.holdcard_index, Some(546));
        assert_eq!(charlie.holdcard_index, Some(1037));
    }

    #[test]
    fn transform_hand_writes_final_board_string() {
        let hand = parse_single_hand(SUMMARY_SHOWED_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let hand_row = batch.hands.first().unwrap();

        assert_eq!(hand_row.board, "5s 4c 2c 7c Jd");
    }

    #[test]
    fn transform_hand_sets_preflop_param_index_using_python_builder_logic() {
        let hand = parse_single_hand(OPEN_WIN_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let redzitteraal_action = batch
            .player_actions
            .iter()
            .find(|row| row.player_name == "RedZitteraal" && row.action_index == 0)
            .unwrap();

        assert_eq!(redzitteraal_action.preflop_param_index, Some(10));
        assert_eq!(redzitteraal_action.postflop_param_index, None);
    }

    #[test]
    fn transform_hand_sets_postflop_param_index_using_python_builder_logic() {
        let hand = parse_single_hand(POSTFLOP_HAND_TEXT);
        let transformer = EtlTransformer::default();

        let batch = transformer.transform_hand(&hand).unwrap();
        let maikuto_flop_bet = batch
            .player_actions
            .iter()
            .find(|row| row.player_name == "maikuto" && row.action_index == 7)
            .unwrap();

        assert_eq!(maikuto_flop_bet.preflop_param_index, None);
        assert_eq!(maikuto_flop_bet.postflop_param_index, Some(864));
    }
}
