use std::collections::HashMap;
use std::path::Path;

use anyhow::{Context, Result, anyhow};
use chrono::{DateTime, NaiveDateTime, Utc};
use once_cell::sync::Lazy;
use regex::Regex;

use crate::{ActionType, ParsedAction, ParsedHand, SeatPlayer, Street, TableType};

static HAND_SPLIT: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?m)^PokerStars Hand #").unwrap()
});

static HAND_ID: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"PokerStars Hand #(\d+):").unwrap()
});

static DATETIME: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(\d{4})/(\d{2})/(\d{2}) (\d{1,2}):(\d{2}):(\d{2})").unwrap()
});

static TABLE_NAME: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"Table '([^']+)'").unwrap()
});

static SUMMARY_BOARD: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?m)^Board \[([^\]]+)\]").unwrap()
});

static SEAT_COUNT: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(\d+)-max").unwrap()
});

static BUTTON_SEAT: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"Seat #(\d+) is the button").unwrap()
});

static BLINDS: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\(\$([0-9.]+)/\$([0-9.]+)\)").unwrap()
});

static SEAT_LINE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"Seat (\d+): (.+?) \(\$([0-9.]+) in chips\)").unwrap()
});

static CASH_DROP: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"Cash Drop to Pot\s*:\s*total\s*\$([0-9.]+)").unwrap()
});

static INSURANCE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(.+?): Pays Cashout Risk \(\$([0-9.]+)\)").unwrap()
});

static COLLECTED: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(.+?) collected \$([0-9.]+) from pot").unwrap()
});

static UNCALLED_RETURN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?m)^Uncalled bet \(\$([0-9.]+)\) returned to (.+)$").unwrap()
});

static SHOWS_HOLE_CARDS: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"^(.+?): shows \[([2-9TJQKA][cdhs]) ([2-9TJQKA][cdhs])\]").unwrap()
});

static SUMMARY_SHOWED_HOLE_CARDS: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"^Seat \d+: (.+?)(?: \([^)]*\))? showed \[([2-9TJQKA][cdhs]) ([2-9TJQKA][cdhs])\]",
    )
    .unwrap()
});

#[derive(Debug, Clone, Copy)]
enum ParsedActionAmount {
    Delta(i64),
    TotalBet(i64),
}

#[derive(Debug, Default)]
pub struct GgTxtParser;

impl GgTxtParser {
    pub fn parse_file(&self, path: &Path) -> Result<Vec<ParsedHand>> {
        let content = std::fs::read_to_string(path)
            .with_context(|| format!("Failed to read file: {:?}", path))?;
        self.parse_text(path.to_string_lossy().as_ref(), &content)
    }

    pub fn parse_text(&self, source_name: &str, text: &str) -> Result<Vec<ParsedHand>> {
        let normalized = self.normalize_text(text);
        let raw_hand_texts = self.split_hands(text);
        let normalized_hand_texts = self.split_hands(&normalized);

        if raw_hand_texts.len() != normalized_hand_texts.len() {
            return Err(anyhow!(
                "Raw and normalized hand count mismatch: raw={}, normalized={}",
                raw_hand_texts.len(),
                normalized_hand_texts.len(),
            ));
        }

        raw_hand_texts
            .into_iter()
            .zip(normalized_hand_texts)
            .map(|(raw_hand_text, normalized_hand_text)| {
                self.parse_single_hand(source_name, raw_hand_text, normalized_hand_text)
            })
            .collect()
    }

    fn normalize_text(&self, text: &str) -> String {
        let mut text = text.replace("\r\n", "\n");

        // Handle Run It Twice/Three
        if text.contains("*** FIRST FLOP ***") {
            text = text.replace("*** FIRST FLOP ***", "*** FLOP ***");
            text = text.replace("*** FIRST TURN ***", "*** TURN ***");
            text = text.replace("*** FIRST RIVER ***", "*** RIVER ***");
            text = text.replace("*** FIRST SHOWDOWN ***", "*** SHOWDOWN ***");

            let re_second = Regex::new(r"(?m)^\*\*\* SECOND (?:FLOP|TURN|RIVER|SHOWDOWN) \*\*\*.*\n").unwrap();
            text = re_second.replace_all(&text, "").to_string();

            let re_third = Regex::new(r"(?m)^\*\*\* THIRD (?:FLOP|TURN|RIVER|SHOWDOWN) \*\*\*.*\n").unwrap();
            text = re_third.replace_all(&text, "").to_string();
        }

        text
    }

    fn split_hands<'a>(&self, text: &'a str) -> Vec<&'a str> {
        let mut hands = Vec::new();
        let mut last_pos = 0;

        for mat in HAND_SPLIT.find_iter(text) {
            if mat.start() > last_pos {
                hands.push(&text[last_pos..mat.start()]);
            }
            last_pos = mat.start();
        }

        if last_pos < text.len() {
            hands.push(&text[last_pos..]);
        }

        hands
    }

    fn parse_single_hand(
        &self,
        source_name: &str,
        raw_text: &str,
        normalized_text: &str,
    ) -> Result<ParsedHand> {
        let source_hand_id = HAND_ID.captures(normalized_text)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();

        let played_at = self.parse_datetime(normalized_text);
        let table_name = TABLE_NAME.captures(normalized_text)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();
        let board = self.parse_board(normalized_text);

        let seat_count = SEAT_COUNT.captures(normalized_text)
            .and_then(|c| c.get(1))
            .and_then(|m| m.as_str().parse().ok())
            .unwrap_or(6);

        let button_seat = BUTTON_SEAT.captures(normalized_text)
            .and_then(|c| c.get(1))
            .and_then(|m| m.as_str().parse().ok())
            .unwrap_or(1);

        let table_type = if seat_count <= 2 {
            TableType::HeadsUp
        } else {
            TableType::SixMax
        };

        let (small_blind_cents, big_blind_cents) = self.parse_blinds(normalized_text);
        let cash_drop_cents = self.parse_cash_drop(normalized_text);
        let insurance_cost_cents = self.parse_insurance(normalized_text);
        let players = self.parse_players(normalized_text);
        let (actions, canonical_actions) = self.parse_actions(normalized_text, &players);
        let (winner_names, collected_cents_by_player) = self.parse_winners(normalized_text);
        let shown_holdcard_indexes_by_player = self.parse_shown_holdcard_indexes(normalized_text);
        let returned_cents_by_player = self.parse_returns(normalized_text);
        let showdown_players = self.parse_showdown_players(normalized_text);

        let saw_flop = normalized_text.contains("*** FLOP ***");
        let saw_turn = normalized_text.contains("*** TURN ***");
        let saw_river = normalized_text.contains("*** RIVER ***");

        Ok(ParsedHand {
            source_name: source_name.to_string(),
            source_hand_id,
            played_at,
            table_name,
            board,
            seat_count,
            button_seat,
            table_type,
            small_blind_cents,
            big_blind_cents,
            cash_drop_cents,
            insurance_cost_cents,
            players,
            actions,
            canonical_actions,
            winner_names,
            showdown_players,
            shown_holdcard_indexes_by_player,
            collected_cents_by_player,
            returned_cents_by_player,
            saw_flop,
            saw_turn,
            saw_river,
            raw_text: raw_text.to_string(),
            normalized_text: normalized_text.to_string(),
        })
    }

    fn parse_datetime(&self, text: &str) -> Option<DateTime<Utc>> {
        DATETIME.captures(text).and_then(|c| {
            let year = c.get(1)?.as_str().parse().ok()?;
            let month = c.get(2)?.as_str().parse().ok()?;
            let day = c.get(3)?.as_str().parse().ok()?;
            let hour = c.get(4)?.as_str().parse().ok()?;
            let min = c.get(5)?.as_str().parse().ok()?;
            let sec = c.get(6)?.as_str().parse().ok()?;

            NaiveDateTime::new(
                chrono::NaiveDate::from_ymd_opt(year, month, day)?,
                chrono::NaiveTime::from_hms_opt(hour, min, sec)?
            ).and_local_timezone(Utc).single()
        })
    }

    /// 解析最终公共牌字符串。
    ///
    /// Args:
    ///     text: 单手牌规范化文本。
    ///
    /// Returns:
    ///     最终公共牌字符串, 无公共牌时返回空串。
    fn parse_board(&self, text: &str) -> String {
        SUMMARY_BOARD
            .captures(text)
            .and_then(|captures| captures.get(1))
            .map(|matched| matched.as_str().trim().to_string())
            .unwrap_or_default()
    }

    fn parse_blinds(&self, text: &str) -> (i64, i64) {
        BLINDS.captures(text)
            .and_then(|c| {
                let sb = self.parse_dollars(c.get(1)?.as_str()).ok()?;
                let bb = self.parse_dollars(c.get(2)?.as_str()).ok()?;
                Some((sb, bb))
            })
            .unwrap_or((1, 2))
    }

    fn parse_cash_drop(&self, text: &str) -> i64 {
        CASH_DROP.captures(text)
            .and_then(|c| self.parse_dollars(c.get(1)?.as_str()).ok())
            .unwrap_or(0)
    }

    fn parse_insurance(&self, text: &str) -> i64 {
        INSURANCE.captures_iter(text)
            .filter_map(|c| self.parse_dollars(c.get(2)?.as_str()).ok())
            .sum()
    }

    fn parse_dollars(&self, s: &str) -> Result<i64> {
        let value = s.replace(",", "");
        let parts: Vec<&str> = value.split('.').collect();

        let dollars = parts.get(0).unwrap_or(&"0").parse::<i64>()?;
        let cents = if parts.len() > 1 {
            let frac = format!("{:0<2}", parts[1]);
            frac[..2].parse::<i64>()?
        } else {
            0
        };

        Ok(dollars * 100 + cents)
    }

    fn parse_players(&self, text: &str) -> Vec<SeatPlayer> {
        let mut players = Vec::new();
        let mut blind_posts = HashMap::new();

        for line in text.lines() {
            if line.contains("posts small blind") {
                if let Some(name) = line.split(':').next() {
                    if let Some(amount_str) = line.split('$').nth(1) {
                        if let Ok(cents) = self.parse_dollars(amount_str.split_whitespace().next().unwrap_or("0")) {
                            blind_posts.insert(name.trim().to_string(), cents);
                        }
                    }
                }
            } else if line.contains("posts big blind") {
                if let Some(name) = line.split(':').next() {
                    if let Some(amount_str) = line.split('$').nth(1) {
                        if let Ok(cents) = self.parse_dollars(amount_str.split_whitespace().next().unwrap_or("0")) {
                            blind_posts.insert(name.trim().to_string(), cents);
                        }
                    }
                }
            }
        }

        for cap in SEAT_LINE.captures_iter(text) {
            if let (Some(seat_no), Some(name), Some(stack)) = (cap.get(1), cap.get(2), cap.get(3)) {
                if let (Ok(seat), Ok(stack_cents)) = (seat_no.as_str().parse(), self.parse_dollars(stack.as_str())) {
                    let player_name = name.as_str().to_string();
                    let blind_post_cents = blind_posts.get(&player_name).copied().unwrap_or(0);

                    players.push(SeatPlayer {
                        seat_no: seat,
                        player_name,
                        starting_stack_cents: stack_cents,
                        blind_post_cents,
                    });
                }
            }
        }

        players
    }

    fn parse_actions(&self, text: &str, players: &[SeatPlayer]) -> (Vec<ParsedAction>, Vec<String>) {
        let mut actions = Vec::new();
        let mut canonical = Vec::new();
        let mut action_index = 0u32;
        let mut current_street = Street::PreFlop;
        let mut player_bets: HashMap<String, i64> = players.iter()
            .map(|p| (p.player_name.clone(), p.blind_post_cents))
            .collect();
        let mut pot_cents = players.iter().map(|p| p.blind_post_cents).sum::<i64>();

        for line in text.lines() {
            if line.contains("*** FLOP ***") {
                current_street = Street::Flop;
                player_bets.values_mut().for_each(|v| *v = 0);
            } else if line.contains("*** TURN ***") {
                current_street = Street::Turn;
                player_bets.values_mut().for_each(|v| *v = 0);
            } else if line.contains("*** RIVER ***") {
                current_street = Street::River;
                player_bets.values_mut().for_each(|v| *v = 0);
            }

            if let Some((player_name, action_type, amount)) = self.parse_action_line(line) {
                let current_bet = player_bets.get(&player_name).copied().unwrap_or(0);
                let max_bet = player_bets.values().copied().max().unwrap_or(0);
                let call_amount = max_bet.saturating_sub(current_bet);
                let (delta_cents, new_bet) = match amount {
                    ParsedActionAmount::Delta(delta_cents) => (
                        delta_cents,
                        current_bet + delta_cents,
                    ),
                    ParsedActionAmount::TotalBet(total_bet_cents) => (
                        total_bet_cents.saturating_sub(current_bet),
                        total_bet_cents,
                    ),
                };

                actions.push(ParsedAction {
                    action_index,
                    street: current_street,
                    player_name: player_name.clone(),
                    action_type,
                    delta_cents,
                    total_bet_cents: new_bet,
                    pot_before_action_cents: pot_cents,
                    call_amount_cents: call_amount,
                });

                canonical.push(format!("{:?}:{:?}", player_name, action_type));
                player_bets.insert(player_name, new_bet);
                pot_cents += delta_cents;
                action_index += 1;
            }
        }

        (actions, canonical)
    }

    fn parse_action_line(&self, line: &str) -> Option<(String, ActionType, ParsedActionAmount)> {
        let parts: Vec<&str> = line.split(':').collect();
        if parts.len() < 2 {
            return None;
        }

        let player_name = parts[0].trim().to_string();
        let action_part = parts[1].trim();

        if action_part.starts_with("folds") {
            Some((player_name, ActionType::Fold, ParsedActionAmount::Delta(0)))
        } else if action_part.starts_with("checks") {
            Some((player_name, ActionType::Check, ParsedActionAmount::Delta(0)))
        } else if action_part.starts_with("calls") {
            let amount = self.extract_amount(action_part).unwrap_or(0);
            Some((player_name, ActionType::Call, ParsedActionAmount::Delta(amount)))
        } else if action_part.starts_with("bets") {
            let amount = self.extract_amount(action_part).unwrap_or(0);
            Some((player_name, ActionType::Bet, ParsedActionAmount::Delta(amount)))
        } else if action_part.starts_with("raises") {
            let amount = self.extract_raise_to_amount(action_part).unwrap_or(0);
            let action_type = if action_part.contains("all-in") {
                ActionType::AllIn
            } else {
                ActionType::Raise
            };
            Some((player_name, action_type, ParsedActionAmount::TotalBet(amount)))
        } else {
            None
        }
    }

    fn extract_amount(&self, text: &str) -> Option<i64> {
        text.split('$').nth(1)
            .and_then(|s| s.split_whitespace().next())
            .and_then(|s| self.parse_dollars(s).ok())
    }

    fn extract_raise_to_amount(&self, text: &str) -> Option<i64> {
        let parts: Vec<&str> = text.split('$').collect();
        if parts.len() >= 3 {
            parts[2].split_whitespace().next()
                .and_then(|s| self.parse_dollars(s).ok())
        } else {
            None
        }
    }

    fn parse_winners(&self, text: &str) -> (Vec<String>, Vec<(String, i64)>) {
        let mut winners = Vec::new();
        let mut collected = Vec::new();

        for cap in COLLECTED.captures_iter(text) {
            if let (Some(name), Some(amount)) = (cap.get(1), cap.get(2)) {
                let player_name = name.as_str().to_string();
                if let Ok(cents) = self.parse_dollars(amount.as_str()) {
                    winners.push(player_name.clone());
                    collected.push((player_name, cents));
                }
            }
        }

        (winners, collected)
    }

    fn parse_returns(&self, text: &str) -> Vec<(String, i64)> {
        let mut returns = Vec::new();

        for cap in UNCALLED_RETURN.captures_iter(text) {
            if let (Some(amount), Some(name)) = (cap.get(1), cap.get(2)) {
                if let Ok(cents) = self.parse_dollars(amount.as_str()) {
                    returns.push((name.as_str().trim().to_string(), cents));
                }
            }
        }

        returns
    }

    fn parse_showdown_players(&self, text: &str) -> Vec<String> {
        let mut players = Vec::new();
        let mut in_showdown = false;
        let mut in_summary = false;

        for line in text.lines() {
            if line.contains("*** SHOWDOWN ***") {
                in_showdown = true;
            } else if line.contains("*** SUMMARY ***") {
                in_showdown = false;
                in_summary = true;
            } else if in_showdown && line.contains(": shows") {
                if let Some(name) = line.split(':').next() {
                    players.push(name.trim().to_string());
                }
            } else if in_summary && line.contains(": showed") {
                if let Some(name) = line.split(':').next() {
                    let player_name = name.trim().to_string();
                    if !players.contains(&player_name) {
                        players.push(player_name);
                    }
                }
            }
        }

        players
    }

    /// 解析文本里明确展示的底牌并映射为 1326 索引。
    ///
    /// Args:
    ///     text: 单手牌规范化文本。
    ///
    /// Returns:
    ///     `(player_name, holdcard_index)` 列表。只有明确出现 `shows/showed` 的玩家才会被返回。
    fn parse_shown_holdcard_indexes(&self, text: &str) -> Vec<(String, u16)> {
        let mut shown_holdcard_indexes_by_player: HashMap<String, u16> = HashMap::new();

        for line in text.lines() {
            if let Some((player_name, holdcard_index)) =
                self.parse_shown_holdcard_index_line(line)
            {
                shown_holdcard_indexes_by_player.insert(player_name, holdcard_index);
            }
        }

        shown_holdcard_indexes_by_player.into_iter().collect()
    }

    /// 从单行文本中提取明确展示的底牌索引。
    ///
    /// Args:
    ///     line: 原始单行文本。
    ///
    /// Returns:
    ///     命中时返回 `(player_name, holdcard_index)`。未明确展示底牌时返回 `None`。
    fn parse_shown_holdcard_index_line(&self, line: &str) -> Option<(String, u16)> {
        if let Some(captures) = SHOWS_HOLE_CARDS.captures(line) {
            return Some((
                captures.get(1)?.as_str().trim().to_string(),
                self.cards_to_index1326(
                    captures.get(2)?.as_str(),
                    captures.get(3)?.as_str(),
                )?,
            ));
        }

        if let Some(captures) = SUMMARY_SHOWED_HOLE_CARDS.captures(line) {
            return Some((
                captures.get(1)?.as_str().trim().to_string(),
                self.cards_to_index1326(
                    captures.get(2)?.as_str(),
                    captures.get(3)?.as_str(),
                )?,
            ));
        }

        None
    }

    /// 将两张明确展示的牌转换为 1326 组合索引。
    ///
    /// Args:
    ///     card1: 第一张牌, 如 `As`。
    ///     card2: 第二张牌, 如 `Qs`。
    ///
    /// Returns:
    ///     0-1325 的组合索引。输入非法时返回 `None`。
    fn cards_to_index1326(&self, card1: &str, card2: &str) -> Option<u16> {
        let mut card1_idx = self.card_to_index52(card1)?;
        let mut card2_idx = self.card_to_index52(card2)?;
        if card1_idx > card2_idx {
            std::mem::swap(&mut card1_idx, &mut card2_idx);
        }

        let mut offset = 0u16;
        for idx in 0..card1_idx {
            offset += 51u16.saturating_sub(idx);
        }

        Some(offset + card2_idx - card1_idx - 1)
    }

    /// 将单张牌转换为 52 索引。
    ///
    /// Args:
    ///     card: 两字符牌面, 如 `As`。
    ///
    /// Returns:
    ///     0-51 的牌索引。输入非法时返回 `None`。
    fn card_to_index52(&self, card: &str) -> Option<u16> {
        let mut chars = card.chars();
        let rank = chars.next()?;
        let suit = chars.next()?;
        if chars.next().is_some() {
            return None;
        }

        let rank_index = match rank {
            '2' => 0,
            '3' => 1,
            '4' => 2,
            '5' => 3,
            '6' => 4,
            '7' => 5,
            '8' => 6,
            '9' => 7,
            'T' => 8,
            'J' => 9,
            'Q' => 10,
            'K' => 11,
            'A' => 12,
            _ => return None,
        };
        let suit_index = match suit {
            'c' => 0,
            'd' => 1,
            'h' => 2,
            's' => 3,
            _ => return None,
        };

        Some(rank_index * 4 + suit_index)
    }
}

#[cfg(test)]
mod tests {
    use super::GgTxtParser;

    const MULTI_HAND_TEXT: &str = r#"PokerStars Hand #100: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:27
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

PokerStars Hand #101: Hold'em No Limit ($0.01/$0.02) - 2025/02/06 17:30:28
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

    #[test]
    fn parse_text_keeps_first_hand_in_multi_hand_file() {
        let parser = GgTxtParser::default();

        let hands = parser.parse_text("sample.txt", MULTI_HAND_TEXT).unwrap();

        assert_eq!(hands.len(), 2);
        assert_eq!(hands[0].source_hand_id, "100");
        assert_eq!(hands[1].source_hand_id, "101");
    }
}
