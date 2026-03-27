"""Preflop 分桶相似度基础能力。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from bayes_poker.domain.table import Position as DomainPosition
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
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
        total_weight: 节点总权重（通常为 combos 加权和）。
    """

    table_type: int
    param_index: int
    probs_fcr: np.ndarray
    node_count: int
    total_weight: float


@dataclass(frozen=True, slots=True)
class ThresholdSweepRow:
    """阈值扫描结果行。

    Attributes:
        threshold: 当前距离阈值。
        cluster_count: 在该阈值下的簇数量。
        merged_bucket_count: 被合并覆盖的桶数量。
        merged_hit_ratio: 被合并覆盖的 hits 占比。
    """

    threshold: float
    cluster_count: int
    merged_bucket_count: int
    merged_hit_ratio: float


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


__all__ = [
    "BucketStrategyProfile",
    "SolverNodeBucketMapping",
    "ThresholdSweepRow",
    "build_solver_node_bucket_mapping",
    "map_solver_node_to_preflop_param_index",
]
