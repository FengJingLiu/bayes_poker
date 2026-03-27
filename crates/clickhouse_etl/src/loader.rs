use crate::{EtlBatch, HandRow, PlayerActionRow, PlayerHandFactRow};
use anyhow::Result;
use clickhouse::{Client, Row};
use serde::Deserialize;
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct ClickHouseConfig {
    pub url: String,
    pub database: String,
    pub user: String,
    pub password: String,
}

impl ClickHouseConfig {
    pub fn new(
        url: impl Into<String>,
        database: impl Into<String>,
        user: impl Into<String>,
        password: impl Into<String>,
    ) -> Self {
        Self {
            url: url.into(),
            database: database.into(),
            user: user.into(),
            password: password.into(),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct LoadSummary {
    pub input_hands: usize,
    pub inserted_hands: usize,
    pub skipped_duplicate_hands: usize,
}

#[derive(Clone)]
pub struct ClickHouseLoader {
    client: Client,
}

#[derive(Debug, Clone, Deserialize, Row)]
struct HandHashOnly {
    hand_hash: String,
}

impl ClickHouseLoader {
    pub fn new(config: ClickHouseConfig) -> Self {
        let client = Client::default()
            .with_url(config.url)
            .with_database(config.database)
            .with_user(config.user)
            .with_password(config.password);
        Self { client }
    }

    pub async fn ensure_schema(&self) -> Result<()> {
        self.client.query(SCHEMA_HANDS).execute().await?;
        self.client.query(SCHEMA_FACTS).execute().await?;
        self.client.query(SCHEMA_ACTIONS).execute().await?;
        self.client
            .query("ALTER TABLE hands ADD COLUMN IF NOT EXISTS board String AFTER table_name")
            .execute()
            .await?;
        Ok(())
    }

    pub async fn load_batch(&self, batch: &EtlBatch) -> Result<LoadSummary> {
        let input_hands = batch.hands.len();
        let candidate_hashes: Vec<String> =
            batch.hands.iter().map(|r| r.hand_hash.clone()).collect();
        let existing = self.fetch_existing_hashes(&candidate_hashes).await?;

        let hands: Vec<HandRow> = batch
            .hands
            .iter()
            .filter(|r| !existing.contains(&r.hand_hash))
            .cloned()
            .collect();
        let inserted_hashes: HashSet<String> = hands.iter().map(|r| r.hand_hash.clone()).collect();

        let facts: Vec<PlayerHandFactRow> = batch
            .player_hand_facts
            .iter()
            .filter(|r| inserted_hashes.contains(&r.hand_hash))
            .cloned()
            .collect();
        let actions: Vec<PlayerActionRow> = batch
            .player_actions
            .iter()
            .filter(|r| inserted_hashes.contains(&r.hand_hash))
            .cloned()
            .collect();

        if !hands.is_empty() {
            let mut insert = self.client.insert("hands")?;
            for row in &hands {
                insert.write(row).await?;
            }
            insert.end().await?;
        }

        if !facts.is_empty() {
            let mut insert = self.client.insert("player_hand_facts")?;
            for row in &facts {
                insert.write(row).await?;
            }
            insert.end().await?;
        }

        if !actions.is_empty() {
            let mut insert = self.client.insert("player_actions")?;
            for row in &actions {
                insert.write(row).await?;
            }
            insert.end().await?;
        }

        Ok(LoadSummary {
            input_hands,
            inserted_hands: hands.len(),
            skipped_duplicate_hands: input_hands.saturating_sub(hands.len()),
        })
    }

    async fn fetch_existing_hashes(&self, hashes: &[String]) -> Result<HashSet<String>> {
        if hashes.is_empty() {
            return Ok(HashSet::new());
        }

        let mut existing = HashSet::new();
        for chunk in hashes.chunks(1000) {
            let quoted: Vec<String> = chunk
                .iter()
                .map(|h| format!("'{}'", h.replace('\'', "''")))
                .collect();
            let sql = format!(
                "SELECT hand_hash FROM hands WHERE hand_hash IN ({})",
                quoted.join(",")
            );
            let rows = self.client.query(&sql).fetch_all::<HandHashOnly>().await?;
            existing.extend(rows.into_iter().map(|r| r.hand_hash));
        }
        Ok(existing)
    }
}

const SCHEMA_HANDS: &str = r#"
CREATE TABLE IF NOT EXISTS hands (
    hand_hash String,
    source_name String,
    source_hand_id String,
    played_at Nullable(DateTime),
    table_name String,
    board String,
    seat_count UInt8,
    table_type UInt8,
    small_blind_cents Int64,
    big_blind_cents Int64,
    cash_drop_cents Int64,
    insurance_cost_cents Int64,
    raw_text String,
    normalized_text String
) ENGINE = ReplacingMergeTree ORDER BY (hand_hash)
"#;

const SCHEMA_FACTS: &str = r#"
CREATE TABLE IF NOT EXISTS player_hand_facts (
    hand_hash String,
    player_name String,
    seat_no UInt8,
    position UInt8,
    holdcard_index Nullable(UInt16),
    net_cents Int64,
    contributed_cents Int64,
    is_vpip UInt8,
    is_pfr UInt8,
    is_3bet UInt8,
    is_4bet UInt8,
    is_saw_flop UInt8,
    is_saw_turn UInt8,
    is_saw_river UInt8,
    is_went_to_showdown UInt8,
    is_winner UInt8,
    is_winner_at_showdown UInt8
) ENGINE = MergeTree ORDER BY (player_name, hand_hash)
"#;

const SCHEMA_ACTIONS: &str = r#"
CREATE TABLE IF NOT EXISTS player_actions (
    hand_hash String,
    player_name String,
    action_index UInt32,
    street UInt8,
    action_type UInt8,
    seat_no UInt8,
    position UInt8,
    amount_cents Int64,
    total_bet_cents Int64,
    pot_before_action_cents Int64,
    call_amount_cents Int64,
    num_callers UInt8,
    num_raises UInt8,
    spr Float32,
    sizing_pct Nullable(Float32),
    preflop_param_index Nullable(UInt16),
    postflop_param_index Nullable(UInt16),
    is_vpip UInt8,
    is_pfr UInt8,
    is_3bet UInt8,
    is_4bet UInt8,
    is_saw_flop UInt8,
    is_saw_turn UInt8,
    is_saw_river UInt8,
    is_went_to_showdown UInt8,
    is_winner UInt8,
    is_winner_at_showdown UInt8
) ENGINE = MergeTree ORDER BY (player_name, hand_hash, action_index)
"#;
