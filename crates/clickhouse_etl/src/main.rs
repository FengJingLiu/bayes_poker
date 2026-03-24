use std::env;
use std::path::PathBuf;
use anyhow::Result;
use clickhouse_etl::{ClickHouseConfig, ClickHouseLoader, EtlTransformer, GgTxtParser, DEFAULT_HAND_BATCH_SIZE};
use rayon::prelude::*;
use walkdir::WalkDir;

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 6 {
        eprintln!("Usage: clickhouse_etl <input_dir> <clickhouse_url> <database> <user> <password>");
        return Ok(());
    }

    let input_dir = PathBuf::from(&args[1]);
    let loader = ClickHouseLoader::new(ClickHouseConfig::new(&args[2], &args[3], &args[4], &args[5]));
    let parser = GgTxtParser::default();
    let transformer = EtlTransformer::default();

    loader.ensure_schema().await?;

    let files: Vec<PathBuf> = WalkDir::new(&input_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .map(|e| e.into_path())
        .filter(|p| p.extension().map(|e| e == "txt").unwrap_or(false))
        .collect();

    let parsed_hands: Vec<_> = files
        .par_iter()
        .map(|path| parser.parse_file(path))
        .collect::<Result<Vec<_>, _>>()?
        .into_iter()
        .flatten()
        .collect();

    for chunk in parsed_hands.chunks(DEFAULT_HAND_BATCH_SIZE) {
        let batch = transformer.transform_chunk(chunk)?;
        let summary = loader.load_batch(&batch).await?;
        println!("Batch: input={} inserted={} skipped={}",
            summary.input_hands, summary.inserted_hands, summary.skipped_duplicate_hands);
    }

    Ok(())
}
