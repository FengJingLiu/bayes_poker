pub mod derive;
pub mod loader;
pub mod parser;
pub mod query;

use chrono::{DateTime, Utc};
use clickhouse::Row;
use serde::{Deserialize, Serialize};

pub use derive::EtlTransformer;
pub use loader::{ClickHouseConfig, ClickHouseLoader, LoadSummary};
pub use parser::GgTxtParser;
pub use poker_stats_rs::{
    compute_hand_hash, ActionType, Position, PostFlopParams, PreFlopParams, PreflopPotType, Street,
    TableType,
};
pub use query::StatisticsQueryService;

pub const DEFAULT_HAND_BATCH_SIZE: usize = 10000;

#[derive(Debug, Clone, Serialize, Deserialize, Row)]
pub struct HandRow {
    pub hand_hash: String,
    pub source_name: String,
    pub source_hand_id: String,
    pub played_at: Option<u32>,
    pub table_name: String,
    pub board: String,
    pub seat_count: u8,
    pub table_type: u8,
    pub small_blind_cents: i64,
    pub big_blind_cents: i64,
    pub cash_drop_cents: i64,
    pub insurance_cost_cents: i64,
    pub raw_text: String,
    pub normalized_text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Row)]
pub struct PlayerHandFactRow {
    pub hand_hash: String,
    pub player_name: String,
    pub seat_no: u8,
    pub position: u8,
    pub holdcard_index: Option<u16>,
    pub net_cents: i64,
    pub contributed_cents: i64,
    pub is_vpip: u8,
    pub is_pfr: u8,
    pub is_3bet: u8,
    pub is_4bet: u8,
    pub is_saw_flop: u8,
    pub is_saw_turn: u8,
    pub is_saw_river: u8,
    pub is_went_to_showdown: u8,
    pub is_winner: u8,
    pub is_winner_at_showdown: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize, Row)]
pub struct PlayerActionRow {
    pub hand_hash: String,
    pub player_name: String,
    pub action_index: u32,
    pub street: u8,
    pub action_type: u8,
    pub seat_no: u8,
    pub position: u8,
    pub amount_cents: i64,
    pub total_bet_cents: i64,
    pub pot_before_action_cents: i64,
    pub call_amount_cents: i64,
    pub num_callers: u8,
    pub num_raises: u8,
    pub spr: f32,
    pub sizing_pct: Option<f32>,
    pub preflop_param_index: Option<u16>,
    pub postflop_param_index: Option<u16>,
    pub is_vpip: u8,
    pub is_pfr: u8,
    pub is_3bet: u8,
    pub is_4bet: u8,
    pub is_saw_flop: u8,
    pub is_saw_turn: u8,
    pub is_saw_river: u8,
    pub is_went_to_showdown: u8,
    pub is_winner: u8,
    pub is_winner_at_showdown: u8,
}

#[derive(Debug, Clone, Default)]
pub struct EtlBatch {
    pub hands: Vec<HandRow>,
    pub player_hand_facts: Vec<PlayerHandFactRow>,
    pub player_actions: Vec<PlayerActionRow>,
}

#[derive(Debug, Clone)]
pub struct ParsedHand {
    /// 解析阶段提取出的明确展示底牌索引。
    ///
    /// 仅当文本里明确出现 `shows/showed [.. ..]` 时才填充。
    pub source_name: String,
    pub source_hand_id: String,
    pub played_at: Option<DateTime<Utc>>,
    pub table_name: String,
    pub board: String,
    pub seat_count: usize,
    pub button_seat: usize,
    pub table_type: TableType,
    pub small_blind_cents: i64,
    pub big_blind_cents: i64,
    pub cash_drop_cents: i64,
    pub insurance_cost_cents: i64,
    pub players: Vec<SeatPlayer>,
    pub actions: Vec<ParsedAction>,
    pub canonical_actions: Vec<String>,
    pub winner_names: Vec<String>,
    pub showdown_players: Vec<String>,
    pub shown_holdcard_indexes_by_player: Vec<(String, u16)>,
    pub collected_cents_by_player: Vec<(String, i64)>,
    pub returned_cents_by_player: Vec<(String, i64)>,
    pub saw_flop: bool,
    pub saw_turn: bool,
    pub saw_river: bool,
    pub raw_text: String,
    pub normalized_text: String,
}

#[derive(Debug, Clone)]
pub struct SeatPlayer {
    pub seat_no: usize,
    pub player_name: String,
    pub starting_stack_cents: i64,
    pub blind_post_cents: i64,
}

#[derive(Debug, Clone)]
pub struct ParsedAction {
    pub action_index: u32,
    pub street: Street,
    pub player_name: String,
    pub action_type: ActionType,
    pub delta_cents: i64,
    pub total_bet_cents: i64,
    pub pot_before_action_cents: i64,
    pub call_amount_cents: i64,
}
