use clickhouse_etl::{GgTxtParser, EtlTransformer};
use std::path::Path;

fn main() -> anyhow::Result<()> {
    let parser = GgTxtParser::default();
    let transformer = EtlTransformer::default();

    let test_file = Path::new("/tmp/clickhouse_test/11152599hhd_RushCash_11_NLH2SH_2025-02-06.txt");

    println!("解析文件: {:?}", test_file);
    let hands = parser.parse_file(test_file)?;
    println!("解析到 {} 手牌", hands.len());

    if hands.is_empty() {
        println!("警告: 没有解析到任何手牌");
        return Ok(());
    }

    println!("\n转换前 3 手牌...");
    let sample = &hands[..hands.len().min(3)];
    let batch = transformer.transform_chunk(sample)?;

    println!("\n统计:");
    println!("- hands: {}", batch.hands.len());
    println!("- player_hand_facts: {}", batch.player_hand_facts.len());
    println!("- player_actions: {}", batch.player_actions.len());

    if let Some(hand) = batch.hands.first() {
        println!("\n示例手牌:");
        println!("  hash: {}", hand.hand_hash);
        println!("  source_hand_id: {}", hand.source_hand_id);
        println!("  table_name: {}", hand.table_name);
        println!("  seat_count: {}", hand.seat_count);
    }

    if let Some(fact) = batch.player_hand_facts.first() {
        println!("\n示例玩家统计:");
        println!("  player: {}", fact.player_name);
        println!("  position: {}", fact.position);
        println!("  vpip: {}, pfr: {}", fact.is_vpip, fact.is_pfr);
        println!("  saw_flop: {}, saw_turn: {}, saw_river: {}",
            fact.is_saw_flop, fact.is_saw_turn, fact.is_saw_river);
    }

    Ok(())
}
