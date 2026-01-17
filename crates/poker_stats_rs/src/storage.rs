use crate::PlayerStats;
use rusqlite::{params, params_from_iter, Connection, OptionalExtension, Result};
use std::collections::HashSet;

pub struct PlayerStatsRepository {
    conn: Connection,
}

const CREATE_PROCESSED_HANDS_TABLE: &str = "CREATE TABLE IF NOT EXISTS processed_hands (\
    hand_hash TEXT PRIMARY KEY,\
    processed_at TEXT NOT NULL\
)";

impl PlayerStatsRepository {
    pub fn open(path: &str) -> Result<Self> {
        let conn = Connection::open(path)?;
        let repo = Self { conn };
        repo.init_tables()?;
        Ok(repo)
    }

    fn init_tables(&self) -> Result<()> {
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                table_type INTEGER NOT NULL,
                vpip_positive INTEGER NOT NULL DEFAULT 0,
                vpip_total INTEGER NOT NULL DEFAULT 0,
                stats_binary BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, table_type)
            )",
            [],
        )?;
        self.ensure_processed_hands_schema()?;
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_player_name ON player_stats(player_name)",
            [],
        )?;
        Ok(())
    }

    fn ensure_processed_hands_schema(&self) -> Result<()> {
        let existing: Option<String> = self
            .conn
            .query_row(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands'",
                [],
                |row| row.get(0),
            )
            .optional()?;

        if existing.is_none() {
            self.conn.execute(CREATE_PROCESSED_HANDS_TABLE, [])?;
            return Ok(());
        }

        let mut stmt = self.conn.prepare("PRAGMA table_info(processed_hands)")?;
        let columns = stmt
            .query_map([], |row| row.get::<_, String>(1))?
            .collect::<Result<Vec<String>, _>>()?;

        let has_hand_hash = columns.iter().any(|c| c == "hand_hash");
        if has_hand_hash {
            return Ok(());
        }

        let has_hand_id = columns.iter().any(|c| c == "hand_id");
        if has_hand_id {
            let legacy: Option<String> = self
                .conn
                .query_row(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_hands_legacy'",
                    [],
                    |row| row.get(0),
                )
                .optional()?;

            if legacy.is_none() {
                self.conn.execute(
                    "ALTER TABLE processed_hands RENAME TO processed_hands_legacy",
                    [],
                )?;
            } else {
                self.conn.execute("DROP TABLE processed_hands", [])?;
            }
            self.conn.execute(CREATE_PROCESSED_HANDS_TABLE, [])?;
            return Ok(());
        }

        self.conn.execute("DROP TABLE processed_hands", [])?;
        self.conn.execute(CREATE_PROCESSED_HANDS_TABLE, [])?;
        Ok(())
    }

    pub fn upsert(&self, stats: &PlayerStats) -> Result<()> {
        let binary_data = stats.to_binary();

        self.conn.execute(
            "INSERT INTO player_stats (player_name, table_type, vpip_positive, vpip_total, stats_binary, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, CURRENT_TIMESTAMP)
             ON CONFLICT(player_name, table_type) DO UPDATE SET
                vpip_positive = vpip_positive + excluded.vpip_positive,
                vpip_total = vpip_total + excluded.vpip_total,
                stats_binary = ?5,
                updated_at = CURRENT_TIMESTAMP",
            params![
                stats.player_name,
                stats.table_type as u8,
                stats.vpip_positive,
                stats.vpip_total,
                binary_data,
            ],
        )?;
        Ok(())
    }

    pub fn upsert_batch(&mut self, stats_list: &[PlayerStats]) -> Result<()> {
        let tx = self.conn.transaction()?;

        for stats in stats_list {
            let existing = Self::get_existing(&tx, &stats.player_name, stats.table_type as u8)?;

            let final_stats = if let Some(mut existing_stats) = existing {
                existing_stats.merge(stats);
                existing_stats
            } else {
                stats.clone()
            };

            let binary_data = final_stats.to_binary();

            tx.execute(
                "INSERT INTO player_stats (player_name, table_type, vpip_positive, vpip_total, stats_binary, updated_at)
                 VALUES (?1, ?2, ?3, ?4, ?5, CURRENT_TIMESTAMP)
                 ON CONFLICT(player_name, table_type) DO UPDATE SET
                    vpip_positive = excluded.vpip_positive,
                    vpip_total = excluded.vpip_total,
                    stats_binary = excluded.stats_binary,
                    updated_at = CURRENT_TIMESTAMP",
                params![
                    final_stats.player_name,
                    final_stats.table_type as u8,
                    final_stats.vpip_positive,
                    final_stats.vpip_total,
                    binary_data,
                ],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn get_processed_hand_hashes(&self, hand_hashes: &[String]) -> Result<HashSet<String>> {
        if hand_hashes.is_empty() {
            return Ok(HashSet::new());
        }

        let mut processed = HashSet::new();
        let mut chunk_start = 0;
        let chunk_size = 900;

        while chunk_start < hand_hashes.len() {
            let chunk_end = (chunk_start + chunk_size).min(hand_hashes.len());
            let chunk = &hand_hashes[chunk_start..chunk_end];
            let placeholders = std::iter::repeat("?")
                .take(chunk.len())
                .collect::<Vec<_>>()
                .join(",");
            let sql = format!(
                "SELECT hand_hash FROM processed_hands WHERE hand_hash IN ({})",
                placeholders
            );
            let mut stmt = self.conn.prepare(&sql)?;
            let rows = stmt.query_map(params_from_iter(chunk.iter()), |row| row.get(0))?;
            for row in rows {
                processed.insert(row?);
            }
            chunk_start = chunk_end;
        }

        Ok(processed)
    }

    pub fn mark_hands_processed(&mut self, hand_hashes: &[String]) -> Result<()> {
        if hand_hashes.is_empty() {
            return Ok(());
        }

        let tx = self.conn.transaction()?;
        let mut stmt = tx.prepare(
            "INSERT OR IGNORE INTO processed_hands (hand_hash, processed_at) VALUES (?1, CURRENT_TIMESTAMP)",
        )?;
        for hand_hash in hand_hashes {
            stmt.execute(params![hand_hash])?;
        }
        drop(stmt);
        tx.commit()?;
        Ok(())
    }

    fn get_existing(
        conn: &Connection,
        player_name: &str,
        table_type: u8,
    ) -> Result<Option<PlayerStats>> {
        let mut stmt = conn.prepare(
            "SELECT stats_binary FROM player_stats WHERE player_name = ?1 AND table_type = ?2",
        )?;

        let mut rows = stmt.query(params![player_name, table_type])?;

        if let Some(row) = rows.next()? {
            let binary_data: Vec<u8> = row.get(0)?;
            match PlayerStats::from_binary(&binary_data) {
                Ok(stats) => Ok(Some(stats)),
                Err(_) => Ok(None),
            }
        } else {
            Ok(None)
        }
    }

    pub fn get(&self, player_name: &str, table_type: u8) -> Result<Option<PlayerStats>> {
        Self::get_existing(&self.conn, player_name, table_type)
    }

    pub fn load(&self, player_name: &str) -> Result<Option<PlayerStats>> {
        let mut stmt = self.conn.prepare(
            "SELECT stats_binary FROM player_stats WHERE player_name = ?1 ORDER BY table_type LIMIT 1"
        )?;

        let mut rows = stmt.query(params![player_name])?;

        if let Some(row) = rows.next()? {
            let binary_data: Vec<u8> = row.get(0)?;
            match PlayerStats::from_binary(&binary_data) {
                Ok(stats) => Ok(Some(stats)),
                Err(_) => Ok(None),
            }
        } else {
            Ok(None)
        }
    }

    pub fn count(&self) -> Result<i64> {
        self.conn
            .query_row("SELECT COUNT(*) FROM player_stats", [], |row| row.get(0))
    }

    pub fn count_distinct_players(&self) -> Result<i64> {
        self.conn.query_row(
            "SELECT COUNT(DISTINCT player_name) FROM player_stats",
            [],
            |row| row.get(0),
        )
    }

    /// 获取指定 table_type 下 vpip_total > min_hands 的所有玩家统计
    pub fn get_stats_by_min_hands(
        &self,
        table_type: u8,
        min_hands: i32,
    ) -> Result<Vec<PlayerStats>> {
        let mut stmt = self.conn.prepare(
            "SELECT stats_binary FROM player_stats WHERE table_type = ?1 AND vpip_total > ?2",
        )?;

        let rows = stmt.query_map(params![table_type, min_hands], |row| {
            let binary_data: Vec<u8> = row.get(0)?;
            Ok(binary_data)
        })?;

        let mut results = Vec::new();
        for row in rows {
            let binary_data = row?;
            if let Ok(stats) = PlayerStats::from_binary(&binary_data) {
                results.push(stats);
            }
        }

        Ok(results)
    }

    /// 聚合指定 table_type 下 vpip_total > min_hands 的所有玩家统计，并以 aggregated_name 写回数据库
    pub fn aggregate_and_upsert(
        &mut self,
        table_type: u8,
        min_hands: i32,
        aggregated_name: &str,
    ) -> Result<Option<PlayerStats>> {
        let stats_list = self.get_stats_by_min_hands(table_type, min_hands)?;

        if stats_list.is_empty() {
            return Ok(None);
        }

        let tt = crate::TableType::from_u8(table_type);
        let mut aggregated = PlayerStats::new(aggregated_name.to_string(), tt);

        for stats in &stats_list {
            aggregated.merge(stats);
        }

        self.upsert(&aggregated)?;
        Ok(Some(aggregated))
    }
}
