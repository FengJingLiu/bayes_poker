"""Preflop 分桶相似度基础能力。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from bayes_poker.domain.table import Position as DomainPosition
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.strategy.range import RANGE_169_ORDER, PreflopRange, combos_per_hand
from bayes_poker.strategy.preflop_parse import (
    is_in_position,
    normalize_token,
    resolve_action_positions,
    resolve_position,
    split_history_tokens,
)

_DOMAIN_TO_METRICS_POSITION: dict[DomainPosition, MetricsPosition] = {
    DomainPosition.SB: MetricsPosition.SMALL_BLIND,
    DomainPosition.BB: MetricsPosition.BIG_BLIND,
    DomainPosition.UTG: MetricsPosition.UTG,
    DomainPosition.MP: MetricsPosition.HJ,
    DomainPosition.HJ: MetricsPosition.HJ,
    DomainPosition.CO: MetricsPosition.CO,
    DomainPosition.BTN: MetricsPosition.BUTTON,
}

_CANONICAL_6MAX_POSITION: dict[DomainPosition, DomainPosition] = {
    DomainPosition.HJ: DomainPosition.MP,
}

_ACTION_FAMILY_TO_INDEX: dict[str, int] = {
    "F": 0,
    "C": 1,
    "R": 2,
}

_COMBO_WEIGHTS_169: np.ndarray = np.array(
    [float(combos_per_hand(hand_key)) for hand_key in RANGE_169_ORDER],
    dtype=np.float64,
)


@dataclass(frozen=True, slots=True)
class SolverNodeBucketMapping:
    """solver 节点到 preflop 分桶的映射结果。

    Attributes:
        history_full: 原始历史字符串。
        history_actions: 去量后的历史签名。
        acting_position: 当前待行动位置字符串。
        actor_position: 解析后的业务位置。
        metrics_position: 对应统计层位置枚举。
        previous_action: 当前 actor 在决策点前的最近一次动作。
        num_callers: 当前决策点前的 caller 计数（压缩前）。
        num_raises: 当前决策点前的激进行动次数。
        in_position_on_flop: 当前 actor 相对最后 aggressor 是否有位置优势。
        aggressor_first_in: 最后 aggressor 在本轮是否 first-in。
        hero_invest_raises: 当前 actor 在前缀中的激进行动次数。
        param_index: 映射得到的 preflop 参数桶索引。
    """

    history_full: str
    history_actions: str
    acting_position: str
    actor_position: DomainPosition | None
    metrics_position: MetricsPosition | None
    previous_action: MetricsActionType
    num_callers: int
    num_raises: int
    in_position_on_flop: bool
    aggressor_first_in: bool
    hero_invest_raises: int
    param_index: int | None


@dataclass(frozen=True, slots=True)
class BucketStrategyProfile:
    """单个分桶的策略画像。

    Attributes:
        table_type: 桌型编码。
        param_index: preflop 分桶索引。
        probs_fcr: `169 x 3` 的 F/C/R 概率矩阵。
        node_count: 参与聚合的节点数。
        total_node_weight: 节点总权重（按 `total_combos` 语义聚合）。
        history_actions: 参与聚合的行动线签名集合。
        hits: 当前分桶命中量（来自外部统计）。
    """

    table_type: int
    param_index: int
    probs_fcr: np.ndarray
    node_count: int
    total_node_weight: float
    history_actions: tuple[str, ...] = ()
    hits: int = 0

    @property
    def total_weight(self) -> float:
        """返回总节点权重的兼容别名。

        Returns:
            与 `total_node_weight` 等值的权重。
        """

        return self.total_node_weight


@dataclass(frozen=True, slots=True)
class BucketNodeProfile:
    """单节点画像及其组合权重输入。

    Attributes:
        probs_fcr: 单节点 `169 x 3` 画像矩阵。
        total_combos: 节点组合权重。聚合时按该值加权。
    """

    probs_fcr: np.ndarray
    total_combos: float


@dataclass(frozen=True, slots=True)
class ThresholdSweepRow:
    """阈值扫描结果行。

    Attributes:
        threshold: 当前距离阈值。
        cluster_count: 在该阈值下的簇数量。
        merged_bucket_count: 被合并覆盖的桶数量。
        merged_hit_ratio: 被合并覆盖的 hits 占比。
        guardrail_ok: 该阈值是否通过推荐护栏。
        recommended: 是否为推荐阈值行。
    """

    threshold: float
    cluster_count: int
    merged_bucket_count: int
    merged_hit_ratio: float
    guardrail_ok: bool = False
    recommended: bool = False


def fold_action_families(action_records: Sequence[object]) -> np.ndarray:
    """把动作序列折叠为单节点 `169 x 3` 的 F/C/R 画像。

    Args:
        action_records: 动作记录序列。每条记录需提供:
            - `action_family` 或 `action_code`
            - `strategy` 或 `preflop_range`（`PreflopRange`）

    Returns:
        单节点 `169 x 3` 概率矩阵。每行按 `F/C/R` 归一化, 零行保持零值。

    Raises:
        ValueError: 当动作族无法识别时抛出。
        TypeError: 当动作记录缺少可读 `PreflopRange` 时抛出。
    """

    probs_fcr = np.zeros((169, 3), dtype=np.float64)
    for action_record in action_records:
        family_index = _resolve_action_family_index(action_record)
        if family_index is None:
            msg = "动作记录缺少可识别的 action_family/action_code。"
            raise ValueError(msg)

        preflop_range = _extract_preflop_range(action_record)
        strategy, _ = preflop_range.to_list()
        probs_fcr[:, family_index] += np.asarray(strategy, dtype=np.float64)

    return _normalize_fcr_rows(probs_fcr)


def aggregate_bucket_profile(
    *,
    param_index: int,
    node_profiles: Sequence[BucketNodeProfile],
    table_type: int = 6,
    history_actions: Sequence[str] | None = None,
    hits: int = 0,
) -> BucketStrategyProfile:
    """按节点权重聚合单桶画像。

    Args:
        param_index: 目标分桶索引。
        node_profiles: 节点画像输入序列。
            每项都必须显式提供 `total_combos` 语义权重。
        table_type: 桌型编码。默认 `6`。
        history_actions: 可选行动线集合元信息。
        hits: 可选命中量元信息。

    Returns:
        聚合后的桶画像对象。
    """

    merged = np.zeros((169, 3), dtype=np.float64)
    total_node_weight = 0.0
    node_count = 0

    for node_profile in node_profiles:
        validated = _validate_profile_matrix(node_profile.probs_fcr)
        weight = max(float(node_profile.total_combos), 0.0)
        if weight <= 0.0:
            continue
        merged += validated * weight
        total_node_weight += weight
        node_count += 1

    if total_node_weight > 0.0:
        probs_fcr = merged / total_node_weight
    else:
        probs_fcr = merged

    return BucketStrategyProfile(
        table_type=table_type,
        param_index=param_index,
        probs_fcr=probs_fcr.astype(np.float32),
        node_count=node_count,
        total_node_weight=total_node_weight,
        history_actions=tuple(history_actions or ()),
        hits=max(int(hits), 0),
    )


def compute_distance(
    profile_a: np.ndarray,
    profile_b: np.ndarray,
    *,
    weight_mode: str = "combo",
) -> float:
    """计算两个桶画像之间的加权距离。

    Args:
        profile_a: 第一个 `169 x 3` 画像矩阵。
        profile_b: 第二个 `169 x 3` 画像矩阵。
        weight_mode: 权重模式。`combo` 使用 `6/4/12`, `uniform` 等权。

    Returns:
        两个画像的距离值。

    Raises:
        ValueError: 当 `weight_mode` 非法时抛出。
    """

    validated_a = _validate_profile_matrix(profile_a)
    validated_b = _validate_profile_matrix(profile_b)
    row_squared_l2 = np.sum(np.square(validated_a - validated_b), axis=1)

    if weight_mode == "combo":
        weights = _COMBO_WEIGHTS_169
        denominator = float(np.sum(weights))
    elif weight_mode == "uniform":
        weights = np.ones(169, dtype=np.float64)
        denominator = 169.0
    else:
        msg = f"未知距离权重模式: {weight_mode}"
        raise ValueError(msg)

    if denominator <= 0.0:
        return 0.0
    return float(np.sqrt(np.sum(weights * row_squared_l2) / denominator))


def compute_distance_matrix(
    bucket_profiles: Mapping[int, BucketStrategyProfile | np.ndarray],
    *,
    weight_mode: str = "combo",
) -> tuple[tuple[int, ...], np.ndarray]:
    """计算分桶两两距离矩阵。

    Args:
        bucket_profiles: `param_index -> BucketStrategyProfile` 映射。
            为兼容场景也支持直接传 `169x3` 画像矩阵。
        weight_mode: 距离权重模式。`combo` 或 `uniform`。

    Returns:
        `(ordered_param_indices, distance_matrix)`。
        矩阵对称, 对角线为 `0.0`。
    """

    ordered_indices = tuple(sorted(int(index) for index in bucket_profiles))
    matrix_size = len(ordered_indices)
    distance_matrix = np.zeros((matrix_size, matrix_size), dtype=np.float64)
    for left in range(matrix_size):
        profile_left = _extract_bucket_profile_matrix(
            bucket_profiles[ordered_indices[left]]
        )
        for right in range(left + 1, matrix_size):
            profile_right = _extract_bucket_profile_matrix(
                bucket_profiles[ordered_indices[right]]
            )
            distance = compute_distance(
                profile_left,
                profile_right,
                weight_mode=weight_mode,
            )
            distance_matrix[left, right] = distance
            distance_matrix[right, left] = distance
    return ordered_indices, distance_matrix


def cluster_buckets(
    distance_matrix: np.ndarray,
    *,
    threshold: float,
) -> tuple[tuple[int, ...], ...]:
    """基于 complete-link 规则执行阈值聚类。

    Args:
        distance_matrix: 桶两两距离矩阵，要求为 `N x N`。
        threshold: 聚类距离阈值。仅当两簇最大两两距离不超过该值时允许合并。

    Returns:
        稳定排序后的簇元组。每个簇成员升序，簇按首元素升序。
    """

    matrix = np.asarray(distance_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        msg = f"距离矩阵必须为方阵，实际形状为 {matrix.shape}。"
        raise ValueError(msg)

    cluster_sets: list[set[int]] = [{index} for index in range(matrix.shape[0])]
    while True:
        best_pair: tuple[int, int] | None = None
        best_score: tuple[float, int, int] | None = None
        for left_index in range(len(cluster_sets)):
            left_cluster = cluster_sets[left_index]
            for right_index in range(left_index + 1, len(cluster_sets)):
                right_cluster = cluster_sets[right_index]
                pair_distance = _compute_complete_link_distance(
                    left_cluster=left_cluster,
                    right_cluster=right_cluster,
                    distance_matrix=matrix,
                )
                if pair_distance > threshold:
                    continue
                pair_key = (
                    min(left_cluster),
                    min(right_cluster),
                )
                # complete-link 距离优先；并列时优先后序分桶，避免链式场景总是吞并前序桶。
                score = (
                    pair_distance,
                    -pair_key[0],
                    -pair_key[1],
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_pair = (left_index, right_index)
        if best_pair is None:
            break
        left_index, right_index = best_pair
        merged_cluster = cluster_sets[left_index] | cluster_sets[right_index]
        cluster_sets[left_index] = merged_cluster
        cluster_sets.pop(right_index)

    ordered_clusters = [tuple(sorted(cluster)) for cluster in cluster_sets]
    ordered_clusters.sort(key=lambda cluster: cluster[0] if cluster else -1)
    return tuple(ordered_clusters)


def select_representative_bucket(
    cluster: Sequence[int],
    hits_by_bucket: Mapping[int, int],
) -> int:
    """为簇选择代表桶。

    Args:
        cluster: 簇内分桶序列。
        hits_by_bucket: `param_index -> hits` 映射。

    Returns:
        代表桶索引。优先 `hits` 最大，`hits` 并列时选 `param_index` 最小。

    Raises:
        ValueError: 当簇为空时抛出。
    """

    members = [int(member) for member in cluster]
    if not members:
        raise ValueError("cluster 不能为空。")
    return min(
        members,
        key=lambda member: (-max(int(hits_by_bucket.get(member, 0)), 0), member),
    )


def compute_threshold_sweep(
    distance_matrix: np.ndarray,
    hits_by_bucket: Mapping[int, int],
    thresholds: Sequence[float] | None = None,
    *,
    ordered_bucket_indices: Sequence[int] | None = None,
    max_cluster_size: int = 8,
    max_cluster_hit_ratio: float = 0.35,
) -> tuple[ThresholdSweepRow, ...]:
    """计算阈值扫描统计并给出推荐阈值。

    Args:
        distance_matrix: 桶两两距离矩阵，要求为 `N x N`。
        hits_by_bucket: `param_index -> hits` 映射。
        thresholds: 待扫描阈值序列。为空时使用默认分位点网格。
        ordered_bucket_indices: 距离矩阵行列对应的 bucket id 顺序。
            为空时默认使用 `0..N-1`。
        max_cluster_size: 推荐阈值护栏，最大簇大小上限。
        max_cluster_hit_ratio: 推荐阈值护栏，最大簇 hits 占比上限。

    Returns:
        阈值扫描结果元组。恰有一行 `recommended=True`。
    """

    matrix = np.asarray(distance_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        msg = f"距离矩阵必须为方阵，实际形状为 {matrix.shape}。"
        raise ValueError(msg)
    matrix_size = matrix.shape[0]
    if ordered_bucket_indices is None:
        bucket_indices = tuple(range(matrix_size))
    else:
        bucket_indices = tuple(int(index) for index in ordered_bucket_indices)
        if len(bucket_indices) != matrix_size:
            msg = (
                "ordered_bucket_indices 长度必须与距离矩阵维度一致, "
                f"实际为 {len(bucket_indices)} vs {matrix_size}。"
            )
            raise ValueError(msg)
    normalized_hits = {
        bucket_index: max(int(hits_by_bucket.get(bucket_index, 0)), 0)
        for bucket_index in bucket_indices
    }
    total_hits = sum(normalized_hits.values())

    threshold_values = _resolve_threshold_grid(matrix=matrix, thresholds=thresholds)
    rows_with_guardrail: list[tuple[ThresholdSweepRow, bool]] = []
    for threshold in threshold_values:
        clusters = cluster_buckets(matrix, threshold=threshold)
        merged_clusters = [cluster for cluster in clusters if len(cluster) > 1]
        merged_bucket_count = sum(len(cluster) for cluster in merged_clusters)
        merged_hits = sum(
            sum(normalized_hits.get(bucket_indices[member], 0) for member in cluster)
            for cluster in merged_clusters
        )
        merged_hit_ratio = (
            float(merged_hits / total_hits) if total_hits > 0 else 0.0
        )
        max_seen_cluster_size = max((len(cluster) for cluster in clusters), default=0)
        max_seen_cluster_hits = max(
            (
                sum(normalized_hits.get(bucket_indices[member], 0) for member in cluster)
                for cluster in clusters
            ),
            default=0,
        )
        max_seen_cluster_hit_ratio = (
            float(max_seen_cluster_hits / total_hits) if total_hits > 0 else 0.0
        )
        guardrail_ok = (
            max_seen_cluster_size <= max_cluster_size
            and max_seen_cluster_hit_ratio <= max_cluster_hit_ratio
        )
        row = ThresholdSweepRow(
            threshold=float(threshold),
            cluster_count=len(clusters),
            merged_bucket_count=merged_bucket_count,
            merged_hit_ratio=merged_hit_ratio,
            guardrail_ok=guardrail_ok,
            recommended=False,
        )
        rows_with_guardrail.append((row, guardrail_ok))

    recommended_index = 0
    for index, (_, guardrail_ok) in enumerate(rows_with_guardrail):
        if guardrail_ok:
            recommended_index = index
            break

    result: list[ThresholdSweepRow] = []
    for index, (row, _) in enumerate(rows_with_guardrail):
        result.append(
            ThresholdSweepRow(
                threshold=row.threshold,
                cluster_count=row.cluster_count,
                merged_bucket_count=row.merged_bucket_count,
                merged_hit_ratio=row.merged_hit_ratio,
                guardrail_ok=row.guardrail_ok,
                recommended=index == recommended_index,
            )
        )
    return tuple(result)


def build_solver_node_bucket_mapping(
    node: Mapping[str, object],
    *,
    table_type: int = 6,
) -> SolverNodeBucketMapping:
    """根据 solver 节点信息构建 preflop 分桶映射结果。

    Args:
        node: solver 节点字典，至少包含 `history_full` 与 `acting_position`。
        table_type: 桌型编码，默认 `6`。

    Returns:
        含中间推导字段的映射结果；无法映射时 `param_index` 为 `None`。
    """

    history_full = _as_text(node.get("history_full"))
    history_actions = _as_text(node.get("history_actions"))
    acting_position = _as_text(node.get("acting_position"))

    previous_action = MetricsActionType.FOLD
    actor_position = resolve_position(acting_position)
    canonical_actor_position = _canonical_position(actor_position)
    metrics_position = (
        _DOMAIN_TO_METRICS_POSITION.get(actor_position)
        if actor_position is not None
        else None
    )
    tokens = tuple(split_history_tokens(history_full))

    if actor_position is None or canonical_actor_position is None or metrics_position is None:
        return SolverNodeBucketMapping(
            history_full=history_full,
            history_actions=history_actions,
            acting_position=acting_position,
            actor_position=actor_position,
            metrics_position=metrics_position,
            previous_action=previous_action,
            num_callers=0,
            num_raises=0,
            in_position_on_flop=False,
            aggressor_first_in=True,
            hero_invest_raises=0,
            param_index=None,
        )

    action_positions = resolve_action_positions(
        actor_position=actor_position,
        tokens=tokens,
    )
    if action_positions is None:
        return SolverNodeBucketMapping(
            history_full=history_full,
            history_actions=history_actions,
            acting_position=acting_position,
            actor_position=actor_position,
            metrics_position=metrics_position,
            previous_action=previous_action,
            num_callers=0,
            num_raises=0,
            in_position_on_flop=False,
            aggressor_first_in=True,
            hero_invest_raises=0,
            param_index=None,
        )

    normalized_tokens = _normalize_history_tokens(tokens)
    if normalized_tokens is None:
        return SolverNodeBucketMapping(
            history_full=history_full,
            history_actions=history_actions,
            acting_position=acting_position,
            actor_position=actor_position,
            metrics_position=metrics_position,
            previous_action=previous_action,
            num_callers=0,
            num_raises=0,
            in_position_on_flop=False,
            aggressor_first_in=True,
            hero_invest_raises=0,
            param_index=None,
        )
    raise_indices = [index for index, token in enumerate(normalized_tokens) if token == "R"]
    num_raises = len(raise_indices)
    last_raise_index = raise_indices[-1] if raise_indices else None

    if last_raise_index is None:
        num_callers = sum(1 for token in normalized_tokens if token == "C")
        aggressor_position: DomainPosition | None = None
    else:
        num_callers = sum(
            1 for token in normalized_tokens[last_raise_index + 1 :] if token == "C"
        )
        aggressor_position = action_positions[last_raise_index]

    hero_invest_raises = 0
    actor_action_indexes: list[int] = []
    for index, (position, token) in enumerate(
        zip(action_positions, normalized_tokens, strict=True)
    ):
        if _canonical_position(position) != canonical_actor_position:
            continue
        actor_action_indexes.append(index)
        if token == "R":
            hero_invest_raises += 1

    if actor_action_indexes:
        try:
            previous_action = _map_token_to_metrics_action(
                normalized_tokens[actor_action_indexes[-1]]
            )
        except ValueError:
            return SolverNodeBucketMapping(
                history_full=history_full,
                history_actions=history_actions,
                acting_position=acting_position,
                actor_position=actor_position,
                metrics_position=metrics_position,
                previous_action=MetricsActionType.FOLD,
                num_callers=0,
                num_raises=0,
                in_position_on_flop=False,
                aggressor_first_in=True,
                hero_invest_raises=0,
                param_index=None,
            )

    aggressor_first_in = True
    if aggressor_position is not None and last_raise_index is not None:
        for index in range(last_raise_index):
            if action_positions[index] != aggressor_position:
                continue
            aggressor_first_in = normalized_tokens[index] == "F"
            break

    in_position_on_flop = (
        is_in_position(
            actor_position=actor_position,
            aggressor_position=aggressor_position,
        )
        if aggressor_position is not None
        else False
    )

    try:
        metrics_table_type = TableType(table_type)
    except ValueError:
        metrics_table_type = None

    param_index: int | None = None
    if metrics_table_type is not None:
        params = PreFlopParams(
            table_type=metrics_table_type,
            position=metrics_position,
            num_callers=min(max(num_callers, 0), 1),
            num_raises=max(num_raises, 0),
            num_active_players=max(2, int(metrics_table_type)),
            previous_action=previous_action,
            in_position_on_flop=in_position_on_flop,
            aggressor_first_in=aggressor_first_in,
            hero_invest_raises=max(hero_invest_raises, 0),
        )
        index_value = params.to_index()
        if index_value >= 0:
            param_index = index_value

    return SolverNodeBucketMapping(
        history_full=history_full,
        history_actions=history_actions,
        acting_position=acting_position,
        actor_position=actor_position,
        metrics_position=metrics_position,
        previous_action=previous_action,
        num_callers=num_callers,
        num_raises=num_raises,
        in_position_on_flop=in_position_on_flop,
        aggressor_first_in=aggressor_first_in,
        hero_invest_raises=hero_invest_raises,
        param_index=param_index,
    )


def map_solver_node_to_preflop_param_index(
    node: Mapping[str, object],
    *,
    table_type: int = 6,
) -> int | None:
    """把 solver 节点映射到 preflop 参数桶索引。

    Args:
        node: solver 节点字典，至少包含 `history_full` 与 `acting_position`。
        table_type: 桌型编码，默认 `6`。

    Returns:
        对应的 `preflop_param_index`；无法映射时返回 `None`。
    """

    mapping = build_solver_node_bucket_mapping(node=node, table_type=table_type)
    return mapping.param_index


def _as_text(value: object) -> str:
    """把任意输入归一化为字符串。

    Args:
        value: 任意输入值。

    Returns:
        清理后的字符串；空值返回空字符串。
    """

    if value is None:
        return ""
    return str(value).strip()


def _map_token_to_metrics_action(token: str) -> MetricsActionType:
    """把标准化 token 映射为统计动作枚举。

    Args:
        token: 标准化历史 token，仅支持 `F/C/R`。

    Returns:
        对应的统计动作类型。
    """

    if token == "R":
        return MetricsActionType.RAISE
    if token == "C":
        return MetricsActionType.CALL
    if token == "F":
        return MetricsActionType.FOLD
    msg = f"未知历史 token: {token}"
    raise ValueError(msg)


def _normalize_history_tokens(tokens: tuple[str, ...]) -> tuple[str, ...] | None:
    """把历史 token 归一化为 `F/C/R` 并校验合法性。

    Args:
        tokens: 原始历史 token 序列。

    Returns:
        归一化后的 `F/C/R` token 序列；存在未知 token 时返回 `None`。
    """

    normalized_tokens: list[str] = []
    for token in tokens:
        normalized_token = normalize_token(token).upper()
        if normalized_token not in {"F", "C", "R"}:
            return None
        normalized_tokens.append(normalized_token)
    return tuple(normalized_tokens)


def _canonical_position(position: DomainPosition | None) -> DomainPosition | None:
    """归一化 6-max 历史中的位置别名。

    Args:
        position: 原始业务位置。

    Returns:
        归一化后的位置；`None` 直接返回 `None`。
    """

    if position is None:
        return None
    return _CANONICAL_6MAX_POSITION.get(position, position)


def _extract_preflop_range(action_record: object) -> PreflopRange:
    """从动作记录提取 `PreflopRange`。

    Args:
        action_record: 动作记录对象。

    Returns:
        动作对应的 `PreflopRange`。

    Raises:
        TypeError: 当记录不包含有效 `PreflopRange` 时抛出。
    """

    range_value = getattr(action_record, "preflop_range", None)
    if isinstance(range_value, PreflopRange):
        return range_value

    strategy_value = getattr(action_record, "strategy", None)
    if isinstance(strategy_value, PreflopRange):
        return strategy_value

    msg = "动作记录未包含可用的 PreflopRange(strategy/preflop_range)。"
    raise TypeError(msg)


def _resolve_action_family_index(action_record: object) -> int | None:
    """把动作记录解析为 `F/C/R` 列索引。

    Args:
        action_record: 动作记录对象。

    Returns:
        `F/C/R` 列索引。无法解析时返回 `None`。
    """

    family = _normalize_action_family(getattr(action_record, "action_family", None))
    if family is None:
        family = _normalize_action_family(getattr(action_record, "action_code", None))
    if family is None:
        return None
    return _ACTION_FAMILY_TO_INDEX[family]


def _normalize_action_family(value: object) -> str | None:
    """把动作描述归一化为 `F/C/R`。

    Args:
        value: 原始动作描述。

    Returns:
        归一化动作族。无法识别时返回 `None`。
    """

    if value is None:
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None

    if raw in {"F", "FOLD"}:
        return "F"
    if raw in {"C", "CALL", "CHECK", "LIMP", "OVERLIMP"}:
        return "C"
    if raw in {"R", "BET", "RAISE", "ALLIN", "ALL_IN"}:
        return "R"
    normalized = normalize_token(raw).upper()
    if normalized in _ACTION_FAMILY_TO_INDEX:
        return normalized
    return None


def _normalize_fcr_rows(probs_fcr: np.ndarray) -> np.ndarray:
    """按行归一化 `F/C/R` 矩阵。

    Args:
        probs_fcr: 待归一化矩阵, 形状 `169 x 3`。

    Returns:
        行归一化后的矩阵。零行保持零值。
    """

    normalized = _validate_profile_matrix(probs_fcr)
    row_sum = np.sum(normalized, axis=1, keepdims=True)
    non_zero_rows = row_sum[:, 0] > 0.0
    normalized[non_zero_rows] = normalized[non_zero_rows] / row_sum[non_zero_rows]
    return normalized


def _validate_profile_matrix(profile: np.ndarray) -> np.ndarray:
    """校验并转换画像矩阵形状。

    Args:
        profile: 任意数组输入。

    Returns:
        `float64` 的 `169 x 3` 矩阵副本。

    Raises:
        ValueError: 当矩阵形状非法时抛出。
    """

    array = np.asarray(profile, dtype=np.float64)
    if array.shape != (169, 3):
        msg = f"画像矩阵形状必须为 (169, 3)，实际为 {array.shape}。"
        raise ValueError(msg)
    return np.array(array, copy=True)


def _extract_bucket_profile_matrix(
    bucket_profile: BucketStrategyProfile | np.ndarray,
) -> np.ndarray:
    """从分桶对象或原始矩阵提取 `169 x 3` 画像矩阵。

    Args:
        bucket_profile: 分桶画像对象或原始矩阵。

    Returns:
        `169 x 3` 画像矩阵副本。
    """

    if isinstance(bucket_profile, BucketStrategyProfile):
        return _validate_profile_matrix(bucket_profile.probs_fcr)
    return _validate_profile_matrix(bucket_profile)


def _compute_complete_link_distance(
    *,
    left_cluster: set[int],
    right_cluster: set[int],
    distance_matrix: np.ndarray,
) -> float:
    """计算两簇的 complete-link 距离。

    Args:
        left_cluster: 左簇成员集合。
        right_cluster: 右簇成员集合。
        distance_matrix: 两两距离矩阵。

    Returns:
        两簇跨簇样本距离中的最大值。
    """

    max_distance = 0.0
    for left_member in left_cluster:
        for right_member in right_cluster:
            current_distance = float(distance_matrix[left_member, right_member])
            if current_distance > max_distance:
                max_distance = current_distance
    return max_distance


def _resolve_threshold_grid(
    *,
    matrix: np.ndarray,
    thresholds: Sequence[float] | None,
) -> tuple[float, ...]:
    """解析阈值网格。

    Args:
        matrix: 两两距离矩阵。
        thresholds: 外部传入阈值序列。

    Returns:
        归一化阈值元组（升序、去重、非负）。
    """

    if thresholds is not None:
        normalized = sorted({max(float(value), 0.0) for value in thresholds})
        if normalized:
            return tuple(normalized)
    upper_triangle = matrix[np.triu_indices(matrix.shape[0], k=1)]
    positive_values = upper_triangle[upper_triangle > 0.0]
    if positive_values.size == 0:
        return (0.0,)
    quantiles = np.quantile(positive_values, np.linspace(0.05, 0.50, 10))
    return tuple(sorted({float(max(value, 0.0)) for value in quantiles}))


__all__ = [
    "BucketNodeProfile",
    "BucketStrategyProfile",
    "SolverNodeBucketMapping",
    "ThresholdSweepRow",
    "aggregate_bucket_profile",
    "build_solver_node_bucket_mapping",
    "compute_distance",
    "compute_distance_matrix",
    "compute_threshold_sweep",
    "fold_action_families",
    "cluster_buckets",
    "map_solver_node_to_preflop_param_index",
    "select_representative_bucket",
]
