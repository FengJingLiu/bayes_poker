use poker_stats_rs::PlayerStatsRepository;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../data/database/player_stats.db"
    );
    let mut repo = PlayerStatsRepository::open(db_path)?;

    let result = repo.aggregate_and_upsert(6, 100, "aggregated_sixmax_100")?;

    match result {
        Some(stats) => {
            println!("聚合完成:");
            println!("  player_name: {}", stats.player_name);
            println!("  vpip: {}/{}", stats.vpip_positive, stats.vpip_total);
            println!("  preflop_stats count: {}", stats.preflop_stats.len());
            println!("  postflop_stats count: {}", stats.postflop_stats.len());
        }
        None => {
            println!("没有找到符合条件的玩家 (table_type=6, vpip_total>100)");
        }
    }

    Ok(())
}
