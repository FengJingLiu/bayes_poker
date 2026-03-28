"""ClickHouse preflop 分桶验证工具。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from collections.abc import Callable
from typing import TypeAlias

_ACTION_FAMILIES: tuple[str, ...] = ("F", "C", "R")

QueryRows: TypeAlias = list[dict[str, str]]
QueryExecutor: TypeAlias = Callable[[str], QueryRows]


@dataclass(frozen=True)
class ValidationConfig:
    """分桶验证配置。

    Attributes:
        table_name: ClickHouse 动作表名。
        preflop_street: preflop 的街道编码。
        min_bucket: 合法桶最小值。
        max_bucket: 合法桶最大值。
        min_valid_pct: 合法桶占比最低阈值。
        unhandled_limit: 非法样本抽样上限。
        micro_top_n: 每个微观桶返回的 top 历史数量。
        micro_bucket_a: 微观抽样桶 A。
        micro_bucket_b: 微观抽样桶 B。
    """

    table_name: str = "default.player_actions"
    preflop_street: int = 1
    min_bucket: int = 0
    max_bucket: int = 64
    min_valid_pct: float = 98.0
    unhandled_limit: int = 20
    micro_top_n: int = 5
    micro_bucket_a: int = 45
    micro_bucket_b: int = 47


@dataclass(frozen=True)
class ValidationIssue:
    """验证问题条目。

    Attributes:
        level: 问题级别。`ERROR` 或 `WARN`。
        message: 问题描述。
    """

    level: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """分桶验证结果。

    Attributes:
        total_preflop_rows: preflop 总行数。
        valid_rows: 落在合法桶范围内的行数。
        valid_pct: 合法行占比。
        null_rows: `preflop_param_index` 为空的行数。
        out_of_bounds_rows: 超出桶范围的行数。
        missing_bucket_indices: 完全没有命中的桶索引。
        action_family_gaps: 缺失的 `(bucket, action_family)` 组合。
        unhandled_examples: 非法样本聚类明细。
        density_rows: 桶命中分布明细。
        micro_rows: 微观语义抽样明细。
        issues: 汇总问题列表。
    """

    total_preflop_rows: int
    valid_rows: int
    valid_pct: float
    null_rows: int
    out_of_bounds_rows: int
    missing_bucket_indices: tuple[int, ...]
    action_family_gaps: tuple[tuple[int, str], ...]
    unhandled_examples: tuple[dict[str, str], ...]
    density_rows: tuple[tuple[int, int], ...]
    micro_rows: tuple[dict[str, str], ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def passed(self) -> bool:
        """返回验证是否通过。

        Returns:
            当不存在 `ERROR` 级问题时返回 True。
        """

        return all(issue.level != "ERROR" for issue in self.issues)


def parse_tsv_with_header(raw_text: str) -> QueryRows:
    """解析 `TSVWithNames` 文本。

    Args:
        raw_text: ClickHouse 查询返回文本。

    Returns:
        行字典列表。
    """

    text = raw_text.strip()
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return [dict(row) for row in reader]


def build_bucket_status_query(config: ValidationConfig) -> str:
    """构建宏观漏斗查询。

    Args:
        config: 验证配置。

    Returns:
        SQL 字符串。
    """

    return (
        "WITH "
        f"(SELECT count() FROM {config.table_name} WHERE street = {config.preflop_street}) AS total "
        "SELECT "
        "multiIf("
        "isNull(preflop_param_index), 'Unhandled (NULL)', "
        f"preflop_param_index > {config.max_bucket}, 'Out of Bounds (>{config.max_bucket})', "
        f"'Valid ({config.min_bucket}-{config.max_bucket})'"
        ") AS bucket_status, "
        "count() AS cnt, "
        "round(count() / total * 100, 6) AS pct "
        f"FROM {config.table_name} "
        f"WHERE street = {config.preflop_street} "
        "GROUP BY bucket_status "
        "ORDER BY cnt DESC"
    )


def build_unhandled_query(config: ValidationConfig) -> str:
    """构建非法样本聚类查询。

    Args:
        config: 验证配置。

    Returns:
        SQL 字符串。
    """

    return (
        "SELECT "
        "position, action_type, num_raises, num_callers, count() AS cnt "
        f"FROM {config.table_name} "
        f"WHERE street = {config.preflop_street} "
        f"AND (isNull(preflop_param_index) OR preflop_param_index > {config.max_bucket}) "
        "GROUP BY position, action_type, num_raises, num_callers "
        "ORDER BY cnt DESC "
        f"LIMIT {config.unhandled_limit}"
    )


def build_density_query(config: ValidationConfig) -> str:
    """构建桶密度查询。

    Args:
        config: 验证配置。

    Returns:
        SQL 字符串。
    """

    return (
        "SELECT preflop_param_index, count() AS hits "
        f"FROM {config.table_name} "
        f"WHERE street = {config.preflop_street} AND preflop_param_index IS NOT NULL "
        "GROUP BY preflop_param_index "
        "ORDER BY preflop_param_index ASC"
    )


def build_action_family_query(config: ValidationConfig) -> str:
    """构建动作族覆盖查询。

    Args:
        config: 验证配置。

    Returns:
        SQL 字符串。
    """

    return (
        "SELECT "
        "preflop_param_index, "
        "multiIf(action_type = 0, 'F', action_type IN (1, 2), 'C', 'R') AS action_family, "
        "count() AS hits "
        f"FROM {config.table_name} "
        f"WHERE street = {config.preflop_street} AND preflop_param_index IS NOT NULL "
        "GROUP BY preflop_param_index, action_family "
        "ORDER BY preflop_param_index, action_family"
    )


def build_micro_query(config: ValidationConfig) -> str:
    """构建 45/47 桶历史抽样查询。

    Args:
        config: 验证配置。

    Returns:
        SQL 字符串。
    """

    return (
        "WITH target AS ("
        "SELECT hand_hash, action_index, preflop_param_index "
        f"FROM {config.table_name} "
        f"WHERE street = {config.preflop_street} "
        f"AND preflop_param_index IN ({config.micro_bucket_a}, {config.micro_bucket_b})"
        ") "
        "SELECT preflop_param_index, history_actions, count() AS freq "
        "FROM ("
        "SELECT "
        "t.preflop_param_index, t.hand_hash, t.action_index, "
        "arrayStringConcat("
        "arrayMap(x -> x.2, "
        "arraySort(x -> x.1, "
        "groupArray(("
        "a.action_index, "
        "multiIf(a.action_type = 0, 'F', a.action_type IN (1, 2), 'C', 'R')"
        "))"
        ")"
        "), "
        "'-'"
        ") AS history_actions "
        "FROM target AS t "
        f"LEFT JOIN {config.table_name} AS a "
        f"ON a.hand_hash = t.hand_hash AND a.street = {config.preflop_street} "
        "AND a.action_index < t.action_index "
        "GROUP BY t.preflop_param_index, t.hand_hash, t.action_index"
        ") "
        "GROUP BY preflop_param_index, history_actions "
        "ORDER BY preflop_param_index ASC, freq DESC "
        f"LIMIT {config.micro_top_n} BY preflop_param_index"
    )


def _safe_int(value: str | None) -> int:
    """将字符串安全转为 int。

    Args:
        value: 原始字符串。

    Returns:
        整数值。为空时返回 0。
    """

    if value is None or value == "":
        return 0
    return int(value)


def _safe_float(value: str | None) -> float:
    """将字符串安全转为 float。

    Args:
        value: 原始字符串。

    Returns:
        浮点值。为空时返回 0.0。
    """

    if value is None or value == "":
        return 0.0
    return float(value)


def _extract_bucket_status(
    rows: QueryRows,
    config: ValidationConfig,
) -> tuple[int, int, float, int, int]:
    """从桶状态查询结果提取关键指标。

    Args:
        rows: 桶状态查询结果。
        config: 验证配置。

    Returns:
        `(total, valid, valid_pct, null_rows, out_of_bounds_rows)`。
    """

    valid_label = f"Valid ({config.min_bucket}-{config.max_bucket})"
    null_label = "Unhandled (NULL)"
    out_label = f"Out of Bounds (>{config.max_bucket})"
    valid_rows = 0
    null_rows = 0
    out_rows = 0
    total_rows = 0
    valid_pct = 0.0
    for row in rows:
        status = row.get("bucket_status", "")
        cnt = _safe_int(row.get("cnt"))
        pct = _safe_float(row.get("pct"))
        total_rows += cnt
        if status == valid_label:
            valid_rows = cnt
            valid_pct = pct
        elif status == null_label:
            null_rows = cnt
        elif status == out_label:
            out_rows = cnt
    return total_rows, valid_rows, valid_pct, null_rows, out_rows


def _find_missing_indices(
    density_rows: QueryRows,
    config: ValidationConfig,
) -> tuple[int, ...]:
    """计算缺失桶索引。

    Args:
        density_rows: 桶密度查询结果。
        config: 验证配置。

    Returns:
        缺失桶索引元组。
    """

    existing = {_safe_int(row.get("preflop_param_index")) for row in density_rows}
    return tuple(
        index
        for index in range(config.min_bucket, config.max_bucket + 1)
        if index not in existing
    )


def _find_action_family_gaps(
    rows: QueryRows,
    config: ValidationConfig,
) -> tuple[tuple[int, str], ...]:
    """计算缺失的 `(bucket, action_family)` 组合。

    Args:
        rows: 动作族覆盖查询结果。
        config: 验证配置。

    Returns:
        缺失组合元组。
    """

    existing = {
        (_safe_int(row.get("preflop_param_index")), str(row.get("action_family", "")))
        for row in rows
    }
    gaps: list[tuple[int, str]] = []
    for index in range(config.min_bucket, config.max_bucket + 1):
        for action_family in _ACTION_FAMILIES:
            if (index, action_family) not in existing:
                gaps.append((index, action_family))
    return tuple(gaps)


def validate_clickhouse_buckets(
    executor: QueryExecutor,
    config: ValidationConfig,
) -> ValidationReport:
    """执行 ClickHouse 分桶验证。

    Args:
        executor: SQL 执行器。输入 SQL, 输出行字典列表。
        config: 验证配置。

    Returns:
        验证报告对象。
    """

    status_rows = executor(build_bucket_status_query(config))
    unhandled_rows = executor(build_unhandled_query(config))
    density_rows_raw = executor(build_density_query(config))
    action_family_rows = executor(build_action_family_query(config))
    micro_rows = executor(build_micro_query(config))

    total, valid, valid_pct, null_rows, out_rows = _extract_bucket_status(
        rows=status_rows,
        config=config,
    )
    missing_indices = _find_missing_indices(
        density_rows=density_rows_raw,
        config=config,
    )
    action_family_gaps = _find_action_family_gaps(
        rows=action_family_rows,
        config=config,
    )
    density_rows = tuple(
        (
            _safe_int(row.get("preflop_param_index")),
            _safe_int(row.get("hits")),
        )
        for row in density_rows_raw
    )

    issues: list[ValidationIssue] = []
    if valid_pct < config.min_valid_pct:
        issues.append(
            ValidationIssue(
                level="ERROR",
                message=(
                    f"合法桶占比过低: {valid_pct:.4f}% < {config.min_valid_pct:.4f}%"
                ),
            )
        )
    if out_rows > 0:
        issues.append(
            ValidationIssue(
                level="ERROR",
                message=f"存在越界桶样本: {out_rows}",
            )
        )
    if missing_indices:
        issues.append(
            ValidationIssue(
                level="WARN",
                message=f"存在空桶索引: {','.join(str(index) for index in missing_indices)}",
            )
        )
    if action_family_gaps:
        issues.append(
            ValidationIssue(
                level="WARN",
                message=f"存在缺失动作组合数: {len(action_family_gaps)}",
            )
        )
    if null_rows > 0:
        issues.append(
            ValidationIssue(
                level="WARN",
                message=f"存在 NULL 桶样本: {null_rows}",
            )
        )

    return ValidationReport(
        total_preflop_rows=total,
        valid_rows=valid,
        valid_pct=valid_pct,
        null_rows=null_rows,
        out_of_bounds_rows=out_rows,
        missing_bucket_indices=missing_indices,
        action_family_gaps=action_family_gaps,
        unhandled_examples=tuple(unhandled_rows),
        density_rows=density_rows,
        micro_rows=tuple(micro_rows),
        issues=tuple(issues),
    )


def format_validation_report(report: ValidationReport) -> str:
    """格式化验证报告文本。

    Args:
        report: 验证报告对象。

    Returns:
        可读文本。
    """

    lines: list[str] = []
    lines.append("## 宏观漏斗")
    lines.append(
        f"total={report.total_preflop_rows} valid={report.valid_rows} "
        f"valid_pct={report.valid_pct:.6f}% null={report.null_rows} "
        f"oob={report.out_of_bounds_rows}"
    )
    lines.append("## 空桶")
    if report.missing_bucket_indices:
        lines.append(
            "missing_indices="
            + ",".join(str(index) for index in report.missing_bucket_indices)
        )
    else:
        lines.append("missing_indices=<none>")
    lines.append("## 缺失动作组合")
    if report.action_family_gaps:
        preview = ",".join(
            f"{index}:{family}"
            for index, family in report.action_family_gaps[:20]
        )
        lines.append(f"gaps={len(report.action_family_gaps)} preview={preview}")
    else:
        lines.append("gaps=0")
    lines.append("## 非法样本 Top")
    if report.unhandled_examples:
        for row in report.unhandled_examples[:10]:
            lines.append(
                f"position={row.get('position')} action_type={row.get('action_type')} "
                f"num_raises={row.get('num_raises')} num_callers={row.get('num_callers')} "
                f"cnt={row.get('cnt')}"
            )
    else:
        lines.append("<none>")
    lines.append("## 微观抽样")
    if report.micro_rows:
        for row in report.micro_rows:
            lines.append(
                f"bucket={row.get('preflop_param_index')} "
                f"history={row.get('history_actions')} freq={row.get('freq')}"
            )
    else:
        lines.append("<none>")
    lines.append("## 结论")
    lines.append(f"passed={report.passed}")
    if report.issues:
        for issue in report.issues:
            lines.append(f"{issue.level}: {issue.message}")
    else:
        lines.append("无问题。")
    return "\n".join(lines)
