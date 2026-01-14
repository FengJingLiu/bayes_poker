use rusqlite::{Connection, Result, params};
use crate::PlayerStats;

pub struct PlayerStatsRepository {
    conn: Connection,
}

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
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_player_name ON player_stats(player_name)",
            [],
        )?;
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

    fn get_existing(conn: &Connection, player_name: &str, table_type: u8) -> Result<Option<PlayerStats>> {
        let mut stmt = conn.prepare(
            "SELECT stats_binary FROM player_stats WHERE player_name = ?1 AND table_type = ?2"
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
}
