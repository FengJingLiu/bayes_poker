#!/usr/bin/env python3
"""离线分析 preflop bucket 相似度并输出合并建议。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.preflop_strategy_repository import (
    PreflopStrategyRepository,
    SolverActionRecord,
)
from bayes_poker.strategy.strategy_engine.population_vb.bucket_similarity import (
    BucketNodeProfile,
    BucketStrategyProfile,
    ThresholdSweepRow,
    aggregate_bucket_profile,
    build_solver_node_bucket_mapping,
    cluster_buckets,
    compute_distance_matrix,
    compute_threshold_sweep,
    fold_action_families,
    select_representative_bucket,
)

_POSITION_TOKEN_TO_METRICS: dict[str, MetricsPosition] = {
    "UTG": MetricsPosition.UTG,
    "MP": MetricsPosition.HJ,
    "HJ": MetricsPosition.HJ,
    "CO": MetricsPosition.CO,
    "BTN": MetricsPosition.BUTTON,
    "SB": MetricsPosition.SMALL_BLIND,
    "BB": MetricsPosition.BIG_BLIND,
}


@dataclass(frozen=True, slots=True)
class BucketMergeSuggestion:
    """单行 bucket 合并建议。

    Attributes:
        cluster_id: 簇序号（从 1 开始）。
        bucket_param_index: 当前行对应的 bucket id。
        representative_param_index: 簇代表 bucket id。
        bucket_hits: 当前 bucket hits。
        representative_hits: 代表 bucket hits。
        cluster_size: 当前簇大小。
        action: 建议动作。`keep` 表示保留代表桶，`merge` 表示合并到代表桶。
    """

    cluster_id: int
    bucket_param_index: int
    representative_param_index: int
    bucket_hits: int
    representative_hits: int
    cluster_size: int
    action: str


@dataclass(frozen=True, slots=True)
class BucketSimilarityAnalysisResult:
    """bucket 相似度分析结果。

    Attributes:
        source_id: 分析使用的策略源 ID。
        requested_stack_bb: CLI 请求 stack。
        resolved_stack_bb: 实际使用 stack。
        total_solver_nodes: 扫描节点总数。
        mapped_solver_nodes: 可映射节点数。
        bucket_profiles: 聚合后的 bucket 画像映射。
        ordered_bucket_indices: 距离矩阵顺序对应的 bucket id。
        clusters: 阈值聚类后的 bucket 分组。
        hits_by_bucket: `param_index -> hits` 映射。
        threshold_sweep: 阈值扫描结果。
        selected_threshold: 最终使用的聚类阈值。
        recommended_threshold: 扫描推荐阈值。
        threshold_mode: `manual` 或 `auto_recommended`。
        suggestions: 展开后的 bucket 合并建议。
    """

    source_id: int
    requested_stack_bb: int
    resolved_stack_bb: int
    total_solver_nodes: int
    mapped_solver_nodes: int
    bucket_profiles: Mapping[int, BucketStrategyProfile]
    ordered_bucket_indices: tuple[int, ...]
    clusters: tuple[tuple[int, ...], ...]
    hits_by_bucket: Mapping[int, int]
    threshold_sweep: tuple[ThresholdSweepRow, ...]
    selected_threshold: float
    recommended_threshold: float
    threshold_mode: str
    suggestions: tuple[BucketMergeSuggestion, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。为空时使用进程参数。

    Returns:
        解析后的参数对象。
    """

    parser = argparse.ArgumentParser(
        description="离线分析 preflop bucket 相似度并输出合并建议。",
    )
    parser.add_argument("--strategy-db", type=Path, required=True, help="策略库 SQLite 路径。")
    parser.add_argument("--hits-csv", type=Path, required=True, help="hits CSV 路径。")
    parser.add_argument("--output-dir", type=Path, required=True, help="输出目录。")
    parser.add_argument(
        "--source-id",
        type=int,
        default=None,
        help="策略源 ID。未提供时要求库内只有一个 source。",
    )
    parser.add_argument("--stack-bb", type=int, default=100, help="目标 stack。默认 100。")
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=None,
        help="手动聚类阈值。未指定时使用扫描推荐值。",
    )
    return parser.parse_args(argv)


def load_hits_csv(hits_csv_path: Path) -> dict[int, int]:
    """读取 bucket hits CSV。

    Args:
        hits_csv_path: 命中量 CSV 路径。

    Returns:
        `preflop_param_index -> hits` 映射。重复 bucket 会累加。

    Raises:
        ValueError: 当列缺失或数据格式非法时抛出。
    """

    with hits_csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        field_names = set(reader.fieldnames or ())
        required_columns = {"preflop_param_index", "hits"}
        if not required_columns.issubset(field_names):
            raise ValueError(
                "hits CSV 缺少必要列。"
                f"required={sorted(required_columns)} actual={sorted(field_names)}"
            )
        hits_by_bucket: dict[int, int] = defaultdict(int)
        for row_number, row in enumerate(reader, start=2):
            raw_param_index = str(row.get("preflop_param_index", "")).strip()
            raw_hits = str(row.get("hits", "")).strip()
            if not raw_param_index and not raw_hits:
                continue
            try:
                param_index = int(raw_param_index)
            except ValueError as exc:
                raise ValueError(
                    f"第 {row_number} 行 preflop_param_index 非法: {raw_param_index!r}"
                ) from exc
            hits_by_bucket[param_index] += _parse_hits_value(raw_hits, row_number=row_number)
    return dict(hits_by_bucket)


def resolve_source_id(repository: PreflopStrategyRepository, requested_source_id: int | None) -> int:
    """解析要分析的 source_id。

    Args:
        repository: 已连接的策略仓库。
        requested_source_id: CLI 传入 source_id。

    Returns:
        最终用于分析的 source_id。

    Raises:
        ValueError: 当 source 不满足解析条件时抛出。
    """

    sources = repository.list_sources()
    if not sources:
        raise ValueError("策略库中没有可用 source。")
    if requested_source_id is not None:
        source_ids = {source.source_id for source in sources}
        if requested_source_id not in source_ids:
            raise ValueError(f"source_id={requested_source_id} 不存在。")
        return requested_source_id
    if len(sources) == 1:
        return sources[0].source_id
    source_id_list = ",".join(str(source.source_id) for source in sources)
    raise ValueError(
        "检测到多个 source，请显式传入 --source-id。"
        f"可选值: {source_id_list}"
    )


def load_solver_nodes(
    repository: PreflopStrategyRepository,
    *,
    source_id: int,
    stack_bb: int,
) -> tuple[dict[str, object], ...]:
    """读取指定 source 与 stack 的 solver 节点。

    Args:
        repository: 已连接的策略仓库。
        source_id: 策略源 ID。
        stack_bb: 筹码深度。

    Returns:
        节点字典元组。
    """

    cursor = repository.conn.cursor()
    cursor.execute(
        """
        SELECT
            node_id,
            history_full,
            history_actions,
            acting_position,
            actor_position,
            call_count,
            raise_time,
            is_in_position
        FROM solver_nodes
        WHERE source_id = ? AND stack_bb = ?
        ORDER BY node_id ASC
        """,
        (source_id, stack_bb),
    )
    return tuple(dict(row) for row in cursor.fetchall())


def build_bucket_profiles(
    *,
    solver_nodes: Sequence[Mapping[str, object]],
    actions_by_node: Mapping[int, Sequence[SolverActionRecord]],
    hits_by_bucket: Mapping[int, int],
) -> tuple[dict[int, BucketStrategyProfile], int]:
    """从 solver 节点构建 bucket 聚合画像。

    Args:
        solver_nodes: solver 节点序列。
        actions_by_node: `node_id -> action_records` 映射。
        hits_by_bucket: `param_index -> hits` 映射。

    Returns:
        `(bucket_profiles, mapped_node_count)`。
    """

    bucket_node_profiles: dict[int, list[BucketNodeProfile]] = defaultdict(list)
    bucket_history_actions: dict[int, set[str]] = defaultdict(set)
    mapped_node_count = 0

    for solver_node in solver_nodes:
        mapping_result = build_solver_node_bucket_mapping(solver_node)
        param_index = mapping_result.param_index
        if param_index is None:
            param_index = infer_param_index_from_node_columns(solver_node)
        if param_index is None:
            continue
        mapped_node_count += 1

        node_id = int(solver_node.get("node_id", -1))
        action_records = actions_by_node.get(node_id, ())
        if not action_records:
            continue
        probs_fcr = fold_action_families(action_records)
        total_combos = sum(
            max(float(action_record.total_combos), 0.0)
            for action_record in action_records
        )
        if total_combos <= 0.0:
            continue

        bucket_node_profiles[param_index].append(
            BucketNodeProfile(probs_fcr=probs_fcr, total_combos=total_combos)
        )
        bucket_history_actions[param_index].add(mapping_result.history_actions)

    bucket_profiles: dict[int, BucketStrategyProfile] = {}
    for param_index in sorted(bucket_node_profiles):
        bucket_profiles[param_index] = aggregate_bucket_profile(
            param_index=param_index,
            node_profiles=tuple(bucket_node_profiles[param_index]),
            history_actions=tuple(sorted(bucket_history_actions[param_index])),
            hits=max(int(hits_by_bucket.get(param_index, 0)), 0),
        )
    return bucket_profiles, mapped_node_count


def infer_param_index_from_node_columns(solver_node: Mapping[str, object]) -> int | None:
    """在严格历史映射失败时，用节点列字段回退推导 param_index。

    Args:
        solver_node: solver 节点字典。

    Returns:
        回退推导的 `param_index`。无法推导时返回 `None`。
    """

    raw_position = str(
        solver_node.get("actor_position") or solver_node.get("acting_position") or ""
    ).strip()
    metrics_position = _POSITION_TOKEN_TO_METRICS.get(raw_position)
    if metrics_position is None:
        return None
    try:
        num_callers = min(max(int(solver_node.get("call_count", 0)), 0), 1)
        num_raises = max(int(solver_node.get("raise_time", 0)), 0)
    except (TypeError, ValueError):
        return None

    params = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=metrics_position,
        num_callers=num_callers,
        num_raises=num_raises,
        num_active_players=6,
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=_parse_bool_like(solver_node.get("is_in_position")),
        aggressor_first_in=True,
        hero_invest_raises=0,
    )
    index_value = params.to_index()
    return int(index_value) if index_value >= 0 else None


def build_merge_suggestions(
    *,
    clusters: Sequence[Sequence[int]],
    hits_by_bucket: Mapping[int, int],
) -> tuple[BucketMergeSuggestion, ...]:
    """根据聚类结果展开 bucket 合并建议。

    Args:
        clusters: bucket 聚类结果。
        hits_by_bucket: `param_index -> hits` 映射。

    Returns:
        合并建议元组。
    """

    suggestions: list[BucketMergeSuggestion] = []
    for cluster_id, cluster in enumerate(clusters, start=1):
        normalized_cluster = tuple(sorted(int(member) for member in cluster))
        representative = select_representative_bucket(normalized_cluster, hits_by_bucket)
        representative_hits = max(int(hits_by_bucket.get(representative, 0)), 0)
        for member in normalized_cluster:
            suggestions.append(
                BucketMergeSuggestion(
                    cluster_id=cluster_id,
                    bucket_param_index=member,
                    representative_param_index=representative,
                    bucket_hits=max(int(hits_by_bucket.get(member, 0)), 0),
                    representative_hits=representative_hits,
                    cluster_size=len(normalized_cluster),
                    action="keep" if member == representative else "merge",
                )
            )
    return tuple(suggestions)


def run_analysis(args: argparse.Namespace) -> BucketSimilarityAnalysisResult:
    """执行 bucket 相似度分析主流程。

    Args:
        args: CLI 参数对象。

    Returns:
        分析结果对象。

    Raises:
        ValueError: 当输入数据不满足分析条件时抛出。
    """

    if args.distance_threshold is not None and args.distance_threshold < 0.0:
        raise ValueError("distance-threshold 不能小于 0。")

    hits_by_bucket = load_hits_csv(args.hits_csv)
    with PreflopStrategyRepository(args.strategy_db) as repository:
        source_id = resolve_source_id(repository, args.source_id)
        resolved_stack_bb = repository.resolve_stack_bb(
            source_id=source_id,
            requested_stack_bb=int(args.stack_bb),
        )
        solver_nodes = load_solver_nodes(
            repository,
            source_id=source_id,
            stack_bb=resolved_stack_bb,
        )
        if not solver_nodes:
            raise ValueError(
                f"source_id={source_id}, stack_bb={resolved_stack_bb} 下没有 solver 节点。"
            )
        node_ids = [int(node["node_id"]) for node in solver_nodes]
        actions_by_node = repository.get_actions_for_nodes(node_ids)

    bucket_profiles, mapped_node_count = build_bucket_profiles(
        solver_nodes=solver_nodes,
        actions_by_node=actions_by_node,
        hits_by_bucket=hits_by_bucket,
    )
    if not bucket_profiles:
        raise ValueError("未能构建任何 bucket 画像，请检查策略库和映射规则。")

    ordered_bucket_indices, distance_matrix = compute_distance_matrix(bucket_profiles)
    threshold_sweep = compute_threshold_sweep(
        distance_matrix,
        hits_by_bucket,
        ordered_bucket_indices=ordered_bucket_indices,
    )
    recommended_row = next((row for row in threshold_sweep if row.recommended), threshold_sweep[0])
    recommended_threshold = float(recommended_row.threshold)
    selected_threshold = (
        float(args.distance_threshold)
        if args.distance_threshold is not None
        else recommended_threshold
    )

    clusters = tuple(
        tuple(ordered_bucket_indices[index] for index in cluster)
        for cluster in cluster_buckets(distance_matrix, threshold=selected_threshold)
    )
    suggestions = build_merge_suggestions(clusters=clusters, hits_by_bucket=hits_by_bucket)

    return BucketSimilarityAnalysisResult(
        source_id=source_id,
        requested_stack_bb=int(args.stack_bb),
        resolved_stack_bb=resolved_stack_bb,
        total_solver_nodes=len(solver_nodes),
        mapped_solver_nodes=mapped_node_count,
        bucket_profiles=bucket_profiles,
        ordered_bucket_indices=ordered_bucket_indices,
        clusters=clusters,
        hits_by_bucket=hits_by_bucket,
        threshold_sweep=threshold_sweep,
        selected_threshold=selected_threshold,
        recommended_threshold=recommended_threshold,
        threshold_mode=("manual" if args.distance_threshold is not None else "auto_recommended"),
        suggestions=suggestions,
    )


def write_analysis_outputs(output_dir: Path, result: BucketSimilarityAnalysisResult) -> None:
    """写出分析产物。

    Args:
        output_dir: 输出目录。
        result: 分析结果对象。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_summary_json(output_dir / "bucket_merge_summary.json", result)
    _write_suggestions_csv(output_dir / "bucket_merge_suggestions.csv", result)
    _write_threshold_sweep_csv(
        output_dir / "bucket_merge_threshold_sweep.csv",
        result.threshold_sweep,
    )


def _write_summary_json(summary_path: Path, result: BucketSimilarityAnalysisResult) -> None:
    """写入 bucket 合并摘要 JSON。

    Args:
        summary_path: 摘要文件路径。
        result: 分析结果对象。
    """

    total_hits = sum(
        max(int(result.hits_by_bucket.get(bucket_index, 0)), 0)
        for bucket_index in result.ordered_bucket_indices
    )
    cluster_payload: list[dict[str, object]] = []
    merged_bucket_count = 0
    merged_hits = 0
    for cluster_id, cluster in enumerate(result.clusters, start=1):
        representative = select_representative_bucket(cluster, result.hits_by_bucket)
        cluster_hits = sum(
            max(int(result.hits_by_bucket.get(bucket_index, 0)), 0)
            for bucket_index in cluster
        )
        if len(cluster) > 1:
            merged_bucket_count += len(cluster)
            merged_hits += cluster_hits
        cluster_payload.append(
            {
                "cluster_id": cluster_id,
                "cluster_size": len(cluster),
                "buckets": list(cluster),
                "representative_param_index": representative,
                "cluster_hits": cluster_hits,
                "cluster_hit_ratio": (cluster_hits / total_hits) if total_hits > 0 else 0.0,
            }
        )

    payload = {
        "source_id": result.source_id,
        "requested_stack_bb": result.requested_stack_bb,
        "resolved_stack_bb": result.resolved_stack_bb,
        "total_solver_nodes": result.total_solver_nodes,
        "mapped_solver_nodes": result.mapped_solver_nodes,
        "bucket_profile_count": len(result.bucket_profiles),
        "distance_threshold": {
            "selected": result.selected_threshold,
            "recommended": result.recommended_threshold,
            "mode": result.threshold_mode,
        },
        "cluster_count": len(result.clusters),
        "merged_bucket_count": merged_bucket_count,
        "merged_hit_ratio": (merged_hits / total_hits) if total_hits > 0 else 0.0,
        "total_hits": total_hits,
        "clusters": cluster_payload,
        "threshold_sweep": [
            {
                "threshold": row.threshold,
                "cluster_count": row.cluster_count,
                "merged_bucket_count": row.merged_bucket_count,
                "merged_hit_ratio": row.merged_hit_ratio,
                "guardrail_ok": row.guardrail_ok,
                "recommended": row.recommended,
            }
            for row in result.threshold_sweep
        ],
    }
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_suggestions_csv(
    suggestions_path: Path,
    result: BucketSimilarityAnalysisResult,
) -> None:
    """写入 bucket 合并建议 CSV。

    Args:
        suggestions_path: 建议 CSV 路径。
        result: 分析结果对象。
    """

    with suggestions_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "cluster_id",
                "bucket_param_index",
                "representative_param_index",
                "bucket_hits",
                "representative_hits",
                "cluster_size",
                "action",
            ],
        )
        writer.writeheader()
        for suggestion in result.suggestions:
            writer.writerow(
                {
                    "cluster_id": suggestion.cluster_id,
                    "bucket_param_index": suggestion.bucket_param_index,
                    "representative_param_index": suggestion.representative_param_index,
                    "bucket_hits": suggestion.bucket_hits,
                    "representative_hits": suggestion.representative_hits,
                    "cluster_size": suggestion.cluster_size,
                    "action": suggestion.action,
                }
            )


def _write_threshold_sweep_csv(
    threshold_sweep_path: Path,
    threshold_sweep: Sequence[ThresholdSweepRow],
) -> None:
    """写入阈值扫描 CSV。

    Args:
        threshold_sweep_path: 阈值扫描 CSV 路径。
        threshold_sweep: 阈值扫描结果序列。
    """

    with threshold_sweep_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "threshold",
                "cluster_count",
                "merged_bucket_count",
                "merged_hit_ratio",
                "guardrail_ok",
                "recommended",
            ],
        )
        writer.writeheader()
        for row in threshold_sweep:
            writer.writerow(
                {
                    "threshold": row.threshold,
                    "cluster_count": row.cluster_count,
                    "merged_bucket_count": row.merged_bucket_count,
                    "merged_hit_ratio": row.merged_hit_ratio,
                    "guardrail_ok": row.guardrail_ok,
                    "recommended": row.recommended,
                }
            )


def _parse_hits_value(raw_hits: str, *, row_number: int) -> int:
    """解析单行 hits 字段。

    Args:
        raw_hits: 原始 hits 字符串。
        row_number: CSV 行号（含表头偏移）。

    Returns:
        非负整数 hits。

    Raises:
        ValueError: 当 hits 非法时抛出。
    """

    try:
        return max(int(raw_hits), 0)
    except ValueError:
        try:
            float_hits = float(raw_hits)
        except ValueError as exc:
            raise ValueError(f"第 {row_number} 行 hits 非法: {raw_hits!r}") from exc
        if not float_hits.is_integer():
            raise ValueError(f"第 {row_number} 行 hits 必须为整数: {raw_hits!r}")
        return max(int(float_hits), 0)


def _parse_bool_like(value: object) -> bool:
    """解析 sqlite bool-like 字段。

    Args:
        value: 任意输入值。

    Returns:
        解析后的布尔值。空值按 `False`。
    """

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def main(argv: list[str] | None = None) -> int:
    """CLI 入口函数。

    Args:
        argv: 可选参数列表。为空时使用进程参数。

    Returns:
        进程退出码。
    """

    args = parse_args(argv)
    try:
        result = run_analysis(args)
        write_analysis_outputs(args.output_dir, result)
    except Exception as exc:  # noqa: BLE001
        print(f"bucket 相似度分析失败: {exc}", file=sys.stderr)
        return 1

    print(
        "bucket 相似度分析完成: "
        f"source_id={result.source_id}, "
        f"stack_bb={result.resolved_stack_bb}, "
        f"bucket_count={len(result.bucket_profiles)}, "
        f"threshold={result.selected_threshold:.6f}, "
        f"output_dir={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
