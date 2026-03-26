use std::env;
use std::fs::{self, File};
use std::path::{Path, PathBuf};

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
    action_totals: String,
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
        clickhouse_url: clickhouse_url
            .context("缺少必选参数 `--clickhouse-url`")?,
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
        sql = append_filter_before_group_by(
            &sql,
            &format!("h.played_at >= toDateTime('{escaped}')"),
        );
    }
    if let Some(date_to) = args.date_to.as_ref() {
        let escaped = date_to.replace('\'', "''");
        sql = append_filter_before_group_by(
            &sql,
            &format!("h.played_at < toDateTime('{escaped}')"),
        );
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
    let file = File::create(path)
        .with_context(|| format!("创建输出文件失败: {}", path.display()))?;
    let encoder = GzEncoder::new(file, Compression::default());
    let mut writer = csv::Writer::from_writer(encoder);
    for row in rows {
        writer.serialize(row).with_context(|| {
            format!("写入 CSV 行失败: {}", path.display())
        })?;
    }
    let encoder = writer.into_inner().with_context(|| {
        format!("完成 CSV flush 失败: {}", path.display())
    })?;
    encoder.finish().with_context(|| {
        format!("完成 GZip 写入失败: {}", path.display())
    })?;
    Ok(())
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
    let bytes = serde_json::to_vec_pretty(manifest)
        .context("序列化 manifest 失败")?;
    fs::write(path, bytes).with_context(|| {
        format!("写入 manifest 失败: {}", path.display())
    })?;
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
    fs::create_dir_all(&args.output_dir).with_context(|| {
        format!("创建输出目录失败: {}", args.output_dir.display())
    })?;

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

    let action_totals_path = args.output_dir.join("action_totals.csv.gz");
    let exposed_combo_counts_path = args.output_dir.join("exposed_combo_counts.csv.gz");
    let manifest_path = args.output_dir.join("manifest.json");

    write_csv_gz(&action_totals_path, &action_totals_rows)?;
    write_csv_gz(&exposed_combo_counts_path, &exposed_combo_counts_rows)?;

    let manifest = ExportManifest {
        generated_at: Utc::now().to_rfc3339(),
        table_type: args.table_type,
        date_from: args.date_from.clone(),
        date_to: args.date_to.clone(),
        action_totals_rows: action_totals_rows.len(),
        exposed_combo_counts_rows: exposed_combo_counts_rows.len(),
        files: ManifestFiles {
            action_totals: String::from("action_totals.csv.gz"),
            exposed_combo_counts: String::from("exposed_combo_counts.csv.gz"),
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
