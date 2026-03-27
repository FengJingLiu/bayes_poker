use std::collections::{BTreeMap, HashMap};
use std::env;
use std::fs::{self, File};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use anyhow::{Context, Result};
use chrono::Utc;
use clickhouse::{Client, Row};
use clickhouse_etl::{ClickHouseConfig, StatisticsQueryService};
use flate2::write::GzEncoder;
use flate2::Compression;
use serde::{Deserialize, Serialize};

/// 导出 CLI 参数。
#[derive(Debug, Clone)]
struct ExportArgs {
    clickhouse_url: String,
    database: String,
    user: String,
    password: String,
    output_dir: PathBuf,
    table_type: Option<u8>,
    date_from: Option<String>,
    date_to: Option<String>,
}

/// `action_totals.csv.gz` 的一行记录。
#[derive(Debug, Clone, Deserialize, Row, Serialize)]
struct ActionTotalsRow {
    table_type: u8,
    preflop_param_index: u16,
    action_family: String,
    n_total: u64,
}

/// `exposed_combo_counts.csv.gz` 的一行记录。
#[derive(Debug, Clone, Deserialize, Row, Serialize)]
struct ExposedComboCountsRow {
    table_type: u8,
    preflop_param_index: u16,
    action_family: String,
    holdcard_index: u16,
    n_exposed: u64,
}

/// 导出产物的文件信息。
#[derive(Debug, Clone, Serialize)]
struct ManifestFiles {
    action_totals_csv: String,
    action_totals: String,
    exposed_combo_counts_csv: String,
    exposed_combo_counts: String,
}

/// 导出任务元信息。
#[derive(Debug, Clone, Serialize)]
struct ExportManifest {
    generated_at: String,
    table_type: Option<u8>,
    date_from: Option<String>,
    date_to: Option<String>,
    action_totals_rows: usize,
    exposed_combo_counts_rows: usize,
    files: ManifestFiles,
}

/// 解析导出参数。
///
/// Args:
///     raw_args: 原始命令行参数（包含可执行文件名）。
///
/// Returns:
///     结构化后的导出参数。
///
/// Raises:
///     `anyhow::Error`: 当缺少必选参数或参数值非法时抛出。
fn parse_args(raw_args: &[String]) -> Result<ExportArgs> {
    let mut clickhouse_url: Option<String> = None;
    let mut database: Option<String> = None;
    let mut user: Option<String> = None;
    let mut password: Option<String> = None;
    let mut output_dir: Option<PathBuf> = None;
    let mut table_type: Option<u8> = None;
    let mut date_from: Option<String> = None;
    let mut date_to: Option<String> = None;

    let mut index: usize = 1;
    while index < raw_args.len() {
        let key = &raw_args[index];
        if key == "--help" || key == "-h" {
            print_usage();
            std::process::exit(0);
        }

        let value = raw_args
            .get(index + 1)
            .with_context(|| format!("参数 `{key}` 缺少取值"))?;
        match key.as_str() {
            "--clickhouse-url" => clickhouse_url = Some(value.clone()),
            "--database" => database = Some(value.clone()),
            "--user" => user = Some(value.clone()),
            "--password" => password = Some(value.clone()),
            "--output-dir" => output_dir = Some(PathBuf::from(value)),
            "--table-type" => {
                table_type = Some(value.parse::<u8>().with_context(|| {
                    format!("`--table-type` 需要 UInt8, 当前值 `{value}` 非法")
                })?)
            }
            "--date-from" => date_from = Some(value.clone()),
            "--date-to" => date_to = Some(value.clone()),
            _ => {
                return Err(anyhow::anyhow!(
                    "未知参数 `{key}`。可用参数: --clickhouse-url --database --user --password --output-dir --table-type --date-from --date-to"
                ))
            }
        }
        index += 2;
    }

    Ok(ExportArgs {
        clickhouse_url: clickhouse_url.context("缺少必选参数 `--clickhouse-url`")?,
        database: database.context("缺少必选参数 `--database`")?,
        user: user.context("缺少必选参数 `--user`")?,
        password: password.context("缺少必选参数 `--password`")?,
        output_dir: output_dir.context("缺少必选参数 `--output-dir`")?,
        table_type,
        date_from,
        date_to,
    })
}

/// 打印命令行帮助。
fn print_usage() {
    eprintln!(
        "Usage: export_preflop_population_dataset \\
  --clickhouse-url <url> \\
  --database <db> \\
  --user <user> \\
  --password <password> \\
  --output-dir <path> \\
  [--table-type <u8>] \\
  [--date-from <YYYY-MM-DD>] \\
  [--date-to <YYYY-MM-DD>]"
    );
}

/// 构建 ClickHouse 客户端。
///
/// Args:
///     config: ClickHouse 连接配置。
///
/// Returns:
///     可复用的 ClickHouse 客户端。
fn build_client(config: &ClickHouseConfig) -> Client {
    Client::default()
        .with_url(config.url.clone())
        .with_database(config.database.clone())
        .with_user(config.user.clone())
        .with_password(config.password.clone())
}

/// 基于可选筛选条件扩展基础 SQL。
///
/// Args:
///     base_sql: 基础查询 SQL。
///     args: 导出参数。
///
/// Returns:
///     附加筛选后的 SQL 字符串。
fn with_filters(base_sql: &str, args: &ExportArgs) -> String {
    let mut sql = String::from(base_sql);
    if let Some(table_type) = args.table_type {
        sql = append_filter_before_group_by(&sql, &format!("h.table_type = {table_type}"));
    }
    if let Some(date_from) = args.date_from.as_ref() {
        let escaped = date_from.replace('\'', "''");
        sql =
            append_filter_before_group_by(&sql, &format!("h.played_at >= toDateTime('{escaped}')"));
    }
    if let Some(date_to) = args.date_to.as_ref() {
        let escaped = date_to.replace('\'', "''");
        sql =
            append_filter_before_group_by(&sql, &format!("h.played_at < toDateTime('{escaped}')"));
    }
    sql
}

/// 在 `GROUP BY` 之前插入 `AND` 条件。
///
/// Args:
///     sql: 原始 SQL。
///     predicate: 要追加的筛选条件，不包含 `AND` 前缀。
///
/// Returns:
///     新 SQL。如果找不到 `GROUP BY`，则在末尾直接附加条件。
fn append_filter_before_group_by(sql: &str, predicate: &str) -> String {
    if let Some(group_by_index) = sql.find("GROUP BY") {
        let mut next = String::new();
        next.push_str(&sql[..group_by_index]);
        next.push_str(&format!("  AND {predicate}\n"));
        next.push_str(&sql[group_by_index..]);
        return next;
    }
    format!("{sql}\n  AND {predicate}")
}

/// 把 1326 组合索引转换为 169 hand class 索引。
///
/// Args:
///     holdcard_index: 0-1325 的组合索引。
///
/// Returns:
///     0-168 的 hand class 索引。
///
/// Raises:
///     `anyhow::Error`: 当输入越界或映射失败时抛出。
fn to_169_bucket_holdcard_index(holdcard_index: u16) -> Result<u16> {
    if holdcard_index >= 1326 {
        return Err(anyhow::anyhow!(
            "holdcard_index 超出范围: {}, 期望 [0, 1325]",
            holdcard_index
        ));
    }
    let (card1, card2) = decode_combo_index_1326(holdcard_index);
    let hand_key = combo_cards_to_hand_key(card1, card2);
    hand_key_to_169_index(&hand_key).ok_or_else(|| {
        anyhow::anyhow!(
            "无法把 hand_key 映射到 169 索引: holdcard_index={}, hand_key={}",
            holdcard_index,
            hand_key
        )
    })
}

/// 把导出的 exposed 行按 169 桶降维并聚合计数。
///
/// Args:
///     rows: 原始 exposed 行, `holdcard_index` 为 1326 组合索引。
///
/// Returns:
///     降维聚合后的行, `holdcard_index` 为 169 桶索引。
///
/// Raises:
///     `anyhow::Error`: 当任意行的索引映射失败时抛出。
fn reduce_exposed_combo_counts_to_169_bucket(
    rows: Vec<ExposedComboCountsRow>,
) -> Result<Vec<ExposedComboCountsRow>> {
    let mut grouped: BTreeMap<(u8, u16, String, u16), u64> = BTreeMap::new();
    for row in rows {
        let bucket_index = to_169_bucket_holdcard_index(row.holdcard_index)?;
        let key = (
            row.table_type,
            row.preflop_param_index,
            row.action_family,
            bucket_index,
        );
        *grouped.entry(key).or_insert(0) += row.n_exposed;
    }

    let mut reduced: Vec<ExposedComboCountsRow> = Vec::with_capacity(grouped.len());
    for ((table_type, preflop_param_index, action_family, holdcard_index), n_exposed) in grouped {
        reduced.push(ExposedComboCountsRow {
            table_type,
            preflop_param_index,
            action_family,
            holdcard_index,
            n_exposed,
        });
    }
    Ok(reduced)
}

/// 解码 1326 组合索引为两张牌的 52 索引（`card1 < card2`）。
///
/// Args:
///     combo_index: 0-1325 组合索引。
///
/// Returns:
///     `(card1, card2)`，两者均在 `[0, 51]`。
fn decode_combo_index_1326(combo_index: u16) -> (u16, u16) {
    let mut remaining: u16 = combo_index;
    let mut card1: u16 = 0;
    let mut block_size: u16 = 51;
    while block_size > 0 && remaining >= block_size {
        remaining -= block_size;
        card1 += 1;
        block_size -= 1;
    }
    let card2 = card1 + 1 + remaining;
    (card1, card2)
}

/// 把两张牌的 52 索引转换为 hand key（如 `AKs`、`QJo`、`TT`）。
///
/// Args:
///     card1: 第一张牌索引。
///     card2: 第二张牌索引。
///
/// Returns:
///     标准化 hand key（高点数在前）。
fn combo_cards_to_hand_key(card1: u16, card2: u16) -> String {
    let mut rank1: u16 = card1 / 4;
    let mut suit1: u16 = card1 % 4;
    let mut rank2: u16 = card2 / 4;
    let mut suit2: u16 = card2 % 4;
    if rank1 < rank2 {
        std::mem::swap(&mut rank1, &mut rank2);
        std::mem::swap(&mut suit1, &mut suit2);
    }

    let rank_chars: [char; 13] = [
        '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A',
    ];
    let r1 = rank_chars[usize::from(rank1)];
    let r2 = rank_chars[usize::from(rank2)];
    if rank1 == rank2 {
        return format!("{r1}{r2}");
    }
    if suit1 == suit2 {
        return format!("{r1}{r2}s");
    }
    format!("{r1}{r2}o")
}

/// 查询 hand key 对应的 169 桶索引。
///
/// Args:
///     hand_key: 手牌键（如 `AKs`）。
///
/// Returns:
///     命中时返回 0-168 索引，否则返回 `None`。
fn hand_key_to_169_index(hand_key: &str) -> Option<u16> {
    static HAND_KEY_TO_169_INDEX: OnceLock<HashMap<String, u16>> = OnceLock::new();
    let mapping = HAND_KEY_TO_169_INDEX.get_or_init(|| {
        let rank_chars: [char; 13] = [
            '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A',
        ];
        let mut keys: Vec<String> = Vec::with_capacity(169);
        for high in 0..13 {
            for low in 0..=high {
                let h = rank_chars[high];
                let l = rank_chars[low];
                if high == low {
                    keys.push(format!("{h}{l}"));
                } else {
                    keys.push(format!("{h}{l}o"));
                    keys.push(format!("{h}{l}s"));
                }
            }
        }
        keys.sort_unstable();
        keys.into_iter()
            .enumerate()
            .map(|(index, key)| (key, index as u16))
            .collect()
    });
    mapping.get(hand_key).copied()
}

/// 将结构化行写出到 gzip 压缩 CSV。
///
/// Args:
///     path: 输出路径。
///     rows: 待写出的行集合。
///
/// Returns:
///     写入完成后返回 `Ok(())`。
///
/// Raises:
///     `anyhow::Error`: 当文件创建或序列化失败时抛出。
fn write_csv_gz<T>(path: &Path, rows: &[T]) -> Result<()>
where
    T: Serialize,
{
    let file =
        File::create(path).with_context(|| format!("创建输出文件失败: {}", path.display()))?;
    let encoder = GzEncoder::new(file, Compression::default());
    let mut writer = csv::Writer::from_writer(encoder);
    for row in rows {
        writer
            .serialize(row)
            .with_context(|| format!("写入 CSV 行失败: {}", path.display()))?;
    }
    let encoder = writer
        .into_inner()
        .with_context(|| format!("完成 CSV flush 失败: {}", path.display()))?;
    encoder
        .finish()
        .with_context(|| format!("完成 GZip 写入失败: {}", path.display()))?;
    Ok(())
}

/// 将结构化行写出到 plain CSV。
///
/// Args:
///     path: 输出路径。
///     rows: 待写出的行集合。
///
/// Returns:
///     写入完成后返回 `Ok(())`。
///
/// Raises:
///     `anyhow::Error`: 当文件创建或序列化失败时抛出。
fn write_csv<T>(path: &Path, rows: &[T]) -> Result<()>
where
    T: Serialize,
{
    let file =
        File::create(path).with_context(|| format!("创建输出文件失败: {}", path.display()))?;
    let mut writer = csv::Writer::from_writer(file);
    for row in rows {
        writer
            .serialize(row)
            .with_context(|| format!("写入 CSV 行失败: {}", path.display()))?;
    }
    writer
        .flush()
        .with_context(|| format!("完成 CSV flush 失败: {}", path.display()))?;
    Ok(())
}

/// 同时写出 plain csv 与 gzip csv。
///
/// Args:
///     output_dir: 输出目录。
///     stem: 文件名前缀（不带扩展名）。
///     rows: 待写出的行集合。
///
/// Returns:
///     `(plain_csv_filename, gzip_csv_filename)`。
///
/// Raises:
///     `anyhow::Error`: 当任一格式写入失败时抛出。
fn write_dual_csv_outputs<T>(output_dir: &Path, stem: &str, rows: &[T]) -> Result<(String, String)>
where
    T: Serialize,
{
    let csv_name = format!("{stem}.csv");
    let csv_gz_name = format!("{stem}.csv.gz");
    let csv_path = output_dir.join(&csv_name);
    let csv_gz_path = output_dir.join(&csv_gz_name);
    write_csv(&csv_path, rows)?;
    write_csv_gz(&csv_gz_path, rows)?;
    Ok((csv_name, csv_gz_name))
}

/// 将 manifest 写出为 JSON。
///
/// Args:
///     path: manifest 输出路径。
///     manifest: 结构化 manifest 数据。
///
/// Returns:
///     写入完成后返回 `Ok(())`。
///
/// Raises:
///     `anyhow::Error`: 当序列化或写文件失败时抛出。
fn write_manifest(path: &Path, manifest: &ExportManifest) -> Result<()> {
    let bytes = serde_json::to_vec_pretty(manifest).context("序列化 manifest 失败")?;
    fs::write(path, bytes).with_context(|| format!("写入 manifest 失败: {}", path.display()))?;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    let raw_args: Vec<String> = env::args().collect();
    if raw_args.len() <= 1 {
        print_usage();
        return Ok(());
    }

    let args = parse_args(&raw_args)?;
    fs::create_dir_all(&args.output_dir)
        .with_context(|| format!("创建输出目录失败: {}", args.output_dir.display()))?;

    let config = ClickHouseConfig::new(
        args.clickhouse_url.clone(),
        args.database.clone(),
        args.user.clone(),
        args.password.clone(),
    );
    let client = build_client(&config);

    let action_totals_sql = with_filters(
        StatisticsQueryService::preflop_population_action_totals_sql(),
        &args,
    );
    let exposed_combo_counts_sql = with_filters(
        StatisticsQueryService::preflop_population_exposed_combo_counts_sql(),
        &args,
    );
    let action_totals_rows = client
        .query(&action_totals_sql)
        .fetch_all::<ActionTotalsRow>()
        .await
        .context("查询 action totals 失败")?;
    let exposed_combo_counts_rows = client
        .query(&exposed_combo_counts_sql)
        .fetch_all::<ExposedComboCountsRow>()
        .await
        .context("查询 exposed combo counts 失败")?;
    let exposed_combo_counts_rows =
        reduce_exposed_combo_counts_to_169_bucket(exposed_combo_counts_rows)
            .context("把 exposed combo 从 1326 降维到 169 失败")?;

    let manifest_path = args.output_dir.join("manifest.json");
    let (action_totals_csv_name, action_totals_csv_gz_name) =
        write_dual_csv_outputs(&args.output_dir, "action_totals", &action_totals_rows)?;
    let (exposed_combo_counts_csv_name, exposed_combo_counts_csv_gz_name) = write_dual_csv_outputs(
        &args.output_dir,
        "exposed_combo_counts",
        &exposed_combo_counts_rows,
    )?;

    let manifest = ExportManifest {
        generated_at: Utc::now().to_rfc3339(),
        table_type: args.table_type,
        date_from: args.date_from.clone(),
        date_to: args.date_to.clone(),
        action_totals_rows: action_totals_rows.len(),
        exposed_combo_counts_rows: exposed_combo_counts_rows.len(),
        files: ManifestFiles {
            action_totals_csv: action_totals_csv_name,
            action_totals: action_totals_csv_gz_name,
            exposed_combo_counts_csv: exposed_combo_counts_csv_name,
            exposed_combo_counts: exposed_combo_counts_csv_gz_name,
        },
    };
    write_manifest(&manifest_path, &manifest)?;

    println!(
        "Export completed: action_totals={} exposed_combo_counts={} output_dir={}",
        action_totals_rows.len(),
        exposed_combo_counts_rows.len(),
        args.output_dir.display(),
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::io::Read;
    use std::time::{SystemTime, UNIX_EPOCH};

    use flate2::read::GzDecoder;
    use serde::Serialize;

    use super::{
        reduce_exposed_combo_counts_to_169_bucket, to_169_bucket_holdcard_index,
        write_dual_csv_outputs, ExposedComboCountsRow,
    };

    #[derive(Debug, Clone, Serialize)]
    struct DummyRow {
        value: u32,
        name: String,
    }

    #[test]
    fn write_dual_csv_outputs_writes_both_csv_and_gz() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("系统时钟异常")
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!(
            "export_preflop_population_dataset_test_{}_{}",
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&temp_dir).expect("创建临时目录失败");

        let rows = vec![
            DummyRow {
                value: 1,
                name: String::from("alpha"),
            },
            DummyRow {
                value: 2,
                name: String::from("beta"),
            },
        ];

        let (csv_name, gz_name) =
            write_dual_csv_outputs(&temp_dir, "dummy", &rows).expect("写双份 CSV 输出失败");
        let csv_path = temp_dir.join(csv_name);
        let gz_path = temp_dir.join(gz_name);

        assert!(csv_path.exists(), "应生成 plain csv");
        assert!(gz_path.exists(), "应生成 gzip csv");

        let csv_content = fs::read_to_string(&csv_path).expect("读取 plain csv 失败");
        assert!(
            csv_content.contains("value,name"),
            "plain csv 应包含 header"
        );
        assert!(
            csv_content.contains("1,alpha"),
            "plain csv 应包含第一行数据"
        );
        assert!(csv_content.contains("2,beta"), "plain csv 应包含第二行数据");

        let gz_file = fs::File::open(&gz_path).expect("打开 gzip csv 失败");
        let mut decoder = GzDecoder::new(gz_file);
        let mut gz_content = String::new();
        decoder
            .read_to_string(&mut gz_content)
            .expect("解压 gzip csv 失败");
        assert!(gz_content.contains("value,name"), "gzip csv 应包含 header");
        assert!(gz_content.contains("1,alpha"), "gzip csv 应包含第一行数据");
        assert!(gz_content.contains("2,beta"), "gzip csv 应包含第二行数据");

        fs::remove_dir_all(&temp_dir).expect("清理临时目录失败");
    }

    #[test]
    fn to_169_bucket_holdcard_index_maps_known_values() {
        assert_eq!(to_169_bucket_holdcard_index(0).expect("0 应可映射"), 0);
        assert_eq!(to_169_bucket_holdcard_index(1).expect("1 应可映射"), 0);
        assert_eq!(to_169_bucket_holdcard_index(546).expect("546 应可映射"), 15);
        assert_eq!(
            to_169_bucket_holdcard_index(1325).expect("1325 应可映射"),
            80
        );
    }

    #[test]
    fn to_169_bucket_holdcard_index_rejects_out_of_range() {
        assert!(
            to_169_bucket_holdcard_index(1326).is_err(),
            "1326 超出 1326 组合上界, 应报错"
        );
    }

    #[test]
    fn reduce_exposed_combo_counts_to_169_bucket_merges_same_hand_class() {
        let rows = vec![
            ExposedComboCountsRow {
                table_type: 6,
                preflop_param_index: 10,
                action_family: String::from("R"),
                holdcard_index: 0,
                n_exposed: 3,
            },
            ExposedComboCountsRow {
                table_type: 6,
                preflop_param_index: 10,
                action_family: String::from("R"),
                holdcard_index: 1,
                n_exposed: 4,
            },
            ExposedComboCountsRow {
                table_type: 6,
                preflop_param_index: 10,
                action_family: String::from("R"),
                holdcard_index: 546,
                n_exposed: 5,
            },
        ];

        let reduced = reduce_exposed_combo_counts_to_169_bucket(rows).expect("降维应成功");
        let same_class = reduced
            .iter()
            .find(|row| row.holdcard_index == 0)
            .expect("应存在 22 桶");
        assert_eq!(same_class.n_exposed, 7);
        assert!(
            reduced.iter().all(|row| row.holdcard_index < 169),
            "降维后 holdcard_index 必须在 [0, 168]"
        );
    }
}
