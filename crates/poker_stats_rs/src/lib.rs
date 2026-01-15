mod action_stats;
mod builder;
mod enums;
mod hand;
mod hand_hash;
mod phhs_parser;
mod player_stats;
mod postflop_params;
mod preflop_params;
mod storage;

pub use action_stats::ActionStats;
pub use builder::build_player_stats_parallel;
pub use enums::*;
pub use hand::{Action, Hand};
pub use phhs_parser::{load_phhs_directory, parse_phhs_file};
pub use player_stats::PlayerStats;
pub use postflop_params::PostFlopParams;
pub use preflop_params::PreFlopParams;
pub use storage::PlayerStatsRepository;

use pyo3::prelude::*;
use std::path::Path;

#[pymodule]
fn poker_stats_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyPlayerStats>()?;
    m.add_class::<PyPlayerStatsFull>()?;
    m.add_function(wrap_pyfunction!(py_build_stats, m)?)?;
    m.add_function(wrap_pyfunction!(py_build_and_save_stats, m)?)?;
    m.add_function(wrap_pyfunction!(py_batch_process_phhs, m)?)?;
    m.add_function(wrap_pyfunction!(py_load_player_stats, m)?)?;
    m.add_function(wrap_pyfunction!(py_load_player_stats_full, m)?)?;
    Ok(())
}

#[pyclass]
#[derive(Clone)]
struct PyPlayerStats {
    #[pyo3(get)]
    player_name: String,
    #[pyo3(get)]
    table_type: u8,
    #[pyo3(get)]
    vpip_positive: i32,
    #[pyo3(get)]
    vpip_total: i32,
}

#[pyclass]
#[derive(Clone)]
struct PyPlayerStatsFull {
    #[pyo3(get)]
    player_name: String,
    #[pyo3(get)]
    table_type: u8,
    #[pyo3(get)]
    vpip_positive: i32,
    #[pyo3(get)]
    vpip_total: i32,
    #[pyo3(get)]
    preflop_stats: Vec<(i32, i32, i32, i32, i32, i32, i32)>,
    #[pyo3(get)]
    postflop_stats: Vec<(i32, i32, i32, i32, i32, i32, i32)>,
}

#[pyfunction]
fn py_build_stats(hands_json: Vec<String>, table_type: u8) -> PyResult<Vec<PyPlayerStats>> {
    let hands: Vec<Hand> = hands_json
        .iter()
        .filter_map(|s| serde_json::from_str(s).ok())
        .collect();

    let tt = TableType::from_u8(table_type);
    let stats = build_player_stats_parallel(&hands, tt);

    Ok(stats
        .into_iter()
        .map(|s| PyPlayerStats {
            player_name: s.player_name,
            table_type: s.table_type as u8,
            vpip_positive: s.vpip_positive,
            vpip_total: s.vpip_total,
        })
        .collect())
}

#[pyfunction]
fn py_build_and_save_stats(
    hands_json: Vec<String>,
    table_type: u8,
    db_path: String,
) -> PyResult<usize> {
    let hands: Vec<Hand> = hands_json
        .iter()
        .filter_map(|s| serde_json::from_str(s).ok())
        .collect();

    let tt = TableType::from_u8(table_type);
    let stats = build_player_stats_parallel(&hands, tt);

    let mut repo = PlayerStatsRepository::open(&db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let count = stats.len();
    repo.upsert_batch(&stats)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    Ok(count)
}

#[pyfunction]
#[pyo3(signature = (phhs_dir, db_path, max_files_in_memory=None))]
fn py_batch_process_phhs(
    phhs_dir: String,
    db_path: String,
    max_files_in_memory: Option<usize>,
) -> PyResult<(usize, usize, usize)> {
    use std::collections::HashSet;
    use std::io::{self, Write};
    use std::time::Instant;
    use walkdir::WalkDir;

    use crate::hand_hash::compute_hand_hash;

    let dir_path = Path::new(&phhs_dir);

    let mut phhs_files = Vec::new();
    for entry in WalkDir::new(dir_path).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.extension().map(|e| e == "phhs").unwrap_or(false) {
            phhs_files.push(path.to_path_buf());
        }
    }

    if phhs_files.is_empty() {
        return Ok((0, 0, 0));
    }

    let total_files = phhs_files.len();
    let chunk_size = max_files_in_memory.unwrap_or(total_files).max(1);
    let total_chunks = (total_files + chunk_size - 1) / chunk_size;

    let started_at = Instant::now();
    let mut last_print_at = Instant::now();
    let mut processed_files: usize = 0;
    let mut total_parsed_hands: usize = 0;
    let mut total_new_hands: usize = 0;
    let mut total_skipped_hands: usize = 0;

    println!(
        "开始处理 PHHS：目录={}，文件数={}，分批大小={}，DB={}",
        phhs_dir, total_files, chunk_size, db_path
    );
    if max_files_in_memory.is_none() {
        println!("提示：未设置 max_files_in_memory，将一次性加载全部文件，可能导致内存占用过高；建议设置 BAYES_POKER_MAX_FILES_IN_MEMORY。");
    }
    let _ = io::stdout().flush();

    let mut repo = PlayerStatsRepository::open(&db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    for (chunk_index, chunk) in phhs_files.chunks(chunk_size).enumerate() {
        let chunk_start_file = chunk_index * chunk_size + 1;
        let chunk_end_file = chunk_index * chunk_size + chunk.len();
        println!(
            "开始处理批次 {}/{}（文件 {}..{}）",
            chunk_index + 1,
            total_chunks,
            chunk_start_file,
            chunk_end_file
        );
        let _ = io::stdout().flush();
        let mut hands = Vec::new();

        for path in chunk {
            let parsed = parse_phhs_file(path);
            total_parsed_hands += parsed.len();
            hands.extend(parsed);
            processed_files += 1;

            let should_print =
                processed_files == total_files || last_print_at.elapsed().as_secs_f64() >= 1.0;
            if should_print {
                let elapsed = started_at.elapsed().as_secs_f64();
                let pct = (processed_files as f64) * 100.0 / (total_files as f64);
                let files_per_sec = if elapsed > 0.0 {
                    processed_files as f64 / elapsed
                } else {
                    0.0
                };
                let hands_per_sec = if elapsed > 0.0 {
                    total_parsed_hands as f64 / elapsed
                } else {
                    0.0
                };
                let remaining_files = total_files.saturating_sub(processed_files);
                let eta_sec = if files_per_sec > 0.0 {
                    remaining_files as f64 / files_per_sec
                } else {
                    0.0
                };

                println!(
                    "进度：{}/{} 文件 ({:.1}%)，累计手牌={}，耗时={:.1}s，速度={:.0} hands/s，ETA={:.1}s",
                    processed_files,
                    total_files,
                    pct,
                    total_parsed_hands,
                    elapsed,
                    hands_per_sec,
                    eta_sec
                );
                let _ = io::stdout().flush();
                last_print_at = Instant::now();
            }
        }

        if hands.is_empty() {
            continue;
        }

        let mut hands_with_hash = Vec::with_capacity(hands.len());
        let mut unique_hashes = Vec::new();
        let mut unique_seen = HashSet::new();

        for hand in hands {
            let hand_hash = compute_hand_hash(&hand.players, &hand.raw_actions);
            if unique_seen.insert(hand_hash.clone()) {
                unique_hashes.push(hand_hash.clone());
            }
            hands_with_hash.push((hand, hand_hash));
        }

        let processed_hashes = repo
            .get_processed_hand_hashes(&unique_hashes)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let mut new_hands = Vec::new();
        let mut new_hashes = Vec::new();
        let mut batch_seen = HashSet::new();
        let mut batch_skipped_hands: usize = 0;

        for (hand, hand_hash) in hands_with_hash {
            if processed_hashes.contains(&hand_hash) {
                batch_skipped_hands += 1;
                continue;
            }
            if !batch_seen.insert(hand_hash.clone()) {
                batch_skipped_hands += 1;
                continue;
            }
            new_hashes.push(hand_hash);
            new_hands.push(hand);
        }

        let batch_new_hands = new_hands.len();
        let batch_parsed_hands = batch_new_hands + batch_skipped_hands;
        total_new_hands += batch_new_hands;
        total_skipped_hands += batch_skipped_hands;

        if new_hands.is_empty() {
            println!(
                "批次 {}/{} 跳过写入：本批无新增手牌（解析={}，跳过={}，累计新增={}，累计跳过={}）",
                chunk_index + 1,
                total_chunks,
                batch_parsed_hands,
                batch_skipped_hands,
                total_new_hands,
                total_skipped_hands
            );
            let _ = io::stdout().flush();
            continue;
        }

        let hu_hands: Vec<Hand> = new_hands
            .iter()
            .filter(|h| h.players.len() == 2)
            .cloned()
            .collect();
        let six_max_hands: Vec<Hand> = new_hands
            .iter()
            .filter(|h| h.players.len() > 2)
            .cloned()
            .collect();

        let mut all_stats = Vec::new();

        if !hu_hands.is_empty() {
            let stats = build_player_stats_parallel(&hu_hands, TableType::HeadsUp);
            all_stats.extend(stats);
        }

        if !six_max_hands.is_empty() {
            let stats = build_player_stats_parallel(&six_max_hands, TableType::SixMax);
            all_stats.extend(stats);
        }

        if !all_stats.is_empty() {
            repo.upsert_batch(&all_stats)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            println!(
                "批次 {}/{} 写入完成：本批新增手牌={}（解析={}，跳过={}，累计新增={}，累计跳过={}）",
                chunk_index + 1,
                total_chunks,
                batch_new_hands,
                batch_parsed_hands,
                batch_skipped_hands,
                total_new_hands,
                total_skipped_hands
            );
            let _ = io::stdout().flush();
        } else {
            println!(
                "批次 {}/{} 跳过写入：本批无统计条目（解析={}，跳过={}，累计新增={}，累计跳过={}）",
                chunk_index + 1,
                total_chunks,
                batch_parsed_hands,
                batch_skipped_hands,
                total_new_hands,
                total_skipped_hands
            );
            let _ = io::stdout().flush();
        }

        repo.mark_hands_processed(&new_hashes)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
    }

    let distinct_players = repo
        .count_distinct_players()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let elapsed = started_at.elapsed().as_secs_f64();
    let hands_per_sec = if elapsed > 0.0 {
        total_new_hands as f64 / elapsed
    } else {
        0.0
    };
    println!(
        "完成：文件数={}，解析手牌={}，新增手牌={}，跳过手牌={}，玩家数={}，耗时={:.1}s，速度={:.0} hands/s",
        total_files,
        total_parsed_hands,
        total_new_hands,
        total_skipped_hands,
        distinct_players,
        elapsed,
        hands_per_sec
    );
    let _ = io::stdout().flush();

    Ok((
        total_new_hands,
        distinct_players as usize,
        total_skipped_hands,
    ))
}

#[pyfunction]
fn py_load_player_stats(
    db_path: String,
    player_names: Vec<String>,
) -> PyResult<Vec<PyPlayerStats>> {
    let repo = PlayerStatsRepository::open(&db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let mut results = Vec::new();
    for name in &player_names {
        if let Ok(Some(stats)) = repo.load(name) {
            results.push(PyPlayerStats {
                player_name: stats.player_name,
                table_type: stats.table_type as u8,
                vpip_positive: stats.vpip_positive,
                vpip_total: stats.vpip_total,
            });
        }
    }

    Ok(results)
}

#[pyfunction]
#[pyo3(signature = (db_path, player_names, table_type=None))]
fn py_load_player_stats_full(
    db_path: String,
    player_names: Vec<String>,
    table_type: Option<u8>,
) -> PyResult<Vec<PyPlayerStatsFull>> {
    let repo = PlayerStatsRepository::open(&db_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    let mut results = Vec::new();
    for name in &player_names {
        let maybe_stats = match table_type {
            Some(tt) => repo.get(name, tt).ok().flatten(),
            None => repo.load(name).ok().flatten(),
        };

        let Some(stats) = maybe_stats else {
            continue;
        };

        let preflop_stats = stats
            .preflop_stats
            .iter()
            .map(|s| {
                (
                    s.bet_0_40,
                    s.bet_40_80,
                    s.bet_80_120,
                    s.bet_over_120,
                    s.raise_samples,
                    s.check_call_samples,
                    s.fold_samples,
                )
            })
            .collect();

        let postflop_stats = stats
            .postflop_stats
            .iter()
            .map(|s| {
                (
                    s.bet_0_40,
                    s.bet_40_80,
                    s.bet_80_120,
                    s.bet_over_120,
                    s.raise_samples,
                    s.check_call_samples,
                    s.fold_samples,
                )
            })
            .collect();

        results.push(PyPlayerStatsFull {
            player_name: stats.player_name,
            table_type: stats.table_type as u8,
            vpip_positive: stats.vpip_positive,
            vpip_total: stats.vpip_total,
            preflop_stats,
            postflop_stats,
        });
    }

    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::py_batch_process_phhs;
    use std::fs;
    use tempfile::tempdir;

    const SAMPLE_HAND: &str = "[hand]\nplayers = [\"Alice\", \"Bob\"]\nactions = [\"p1 f\", \"p2 cc 100\"]\nblinds_or_straddles = [50, 100]\nantes = [0, 0]\n";

    #[test]
    fn batch_process_skips_duplicate_hands() {
        let temp_dir = tempdir().expect("创建临时目录失败");
        let phhs_dir = temp_dir.path().join("phhs");
        fs::create_dir_all(&phhs_dir).expect("创建 PHHS 目录失败");

        let first_file = phhs_dir.join("hand_1.phhs");
        let second_file = phhs_dir.join("hand_2.phhs");
        fs::write(&first_file, SAMPLE_HAND).expect("写入 hand_1 失败");
        fs::write(&second_file, SAMPLE_HAND).expect("写入 hand_2 失败");

        let db_path = temp_dir.path().join("stats.db");
        let (new_hands, players, skipped_hands) = py_batch_process_phhs(
            phhs_dir.to_string_lossy().to_string(),
            db_path.to_string_lossy().to_string(),
            Some(1),
        )
        .expect("批处理失败");

        assert_eq!(new_hands, 1);
        assert_eq!(skipped_hands, 1);
        assert_eq!(players, 2);

        let (new_hands_again, _players_again, skipped_hands_again) = py_batch_process_phhs(
            phhs_dir.to_string_lossy().to_string(),
            db_path.to_string_lossy().to_string(),
            Some(1),
        )
        .expect("二次批处理失败");

        assert_eq!(new_hands_again, 0);
        assert_eq!(skipped_hands_again, 2);
    }
}
