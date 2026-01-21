"""翻前策略查询模块。

提供根据行动历史查询策略节点的功能，支持多级回退匹配。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bayes_poker.strategy.preflop.models import PreflopStrategy, StrategyNode


@dataclass
class QueryResult:
    """策略查询结果。

    Attributes:
        node: 匹配到的策略节点
        matched_history: 实际匹配的历史字符串（节点的 history_full）
        original_history: 原始查询的历史字符串
        fallback_level: 使用的回退级别 (0=精确匹配)
        fallback_description: 回退策略的描述
    """

    node: StrategyNode
    matched_history: str
    original_history: str
    fallback_level: int
    fallback_description: str


def _split_tokens(history: str) -> list[str]:
    """分割并清理行动历史 token。

    Args:
        history: 行动历史字符串

    Returns:
        清理后的 token 列表
    """
    if not history:
        return []
    return [t.strip() for t in history.split("-") if t.strip()]


def normalize_history(history: str) -> str:
    """将行动历史标准化，去除加注量。

    Args:
        history: 行动历史，如 "R2.5-C-R8-F"

    Returns:
        标准化后的历史，如 "R-C-R-F"
    """
    if not history:
        return ""
    tokens = _split_tokens(history)
    normalized = []
    for token in tokens:
        upper = token.upper()
        if upper == "RAI" or (upper.startswith("R") and len(upper) > 1):
            normalized.append("R")
        elif upper in ("F", "C", "R"):
            normalized.append(upper)
        else:
            normalized.append(token)
    return "-".join(normalized)


def generate_call_to_fold_variants(history: str) -> list[str]:
    """生成将 CALL 替换为 FOLD 的变体列表。

    从后向前逐个替换 C 为 F，生成所有可能的变体。

    Args:
        history: 行动历史，如 "R2-C-R6-C"

    Returns:
        变体列表，如 ["R2-C-R6-F", "R2-F-R6-F"]
    """
    tokens = _split_tokens(history)
    call_indices = [i for i, t in enumerate(tokens) if t.upper() == "C"]

    if not call_indices:
        return []

    variants = []
    for num_replacements in range(1, len(call_indices) + 1):
        new_tokens = tokens.copy()
        indices_to_replace = call_indices[-num_replacements:]
        for idx in indices_to_replace:
            new_tokens[idx] = "F"
        variants.append("-".join(new_tokens))

    return variants


def _try_match(
    strategy: PreflopStrategy, stack_bb: int, history: str
) -> StrategyNode | None:
    """尝试按 history_full 精确匹配策略节点。"""
    return strategy.get_node(stack_bb, history)


def _extract_raise_sizes(history: str) -> list[float]:
    """从历史字符串中提取所有加注尺度。

    Args:
        history: 历史字符串，如 "R2-F-R6.5"

    Returns:
        加注尺度列表，如 [2.0, 6.5]。RAI 视为 1000.0
    """
    sizes = []
    for token in history.split("-"):
        token = token.strip().upper()
        if token.startswith("R") and len(token) > 1:
            if token == "RAI":
                sizes.append(1000.0)
            else:
                try:
                    sizes.append(float(token[1:]))
                except ValueError:
                    pass
    return sizes


def _calculate_raise_distance(
    query_sizes: list[float], candidate_sizes: list[float]
) -> float:
    """计算查询加注尺度与候选节点加注尺度的差距。

    逐位置比较加注尺度，计算差值的平方和。
    如果长度不同，缺失位置视为差距 1000。

    Args:
        query_sizes: 查询历史的加注尺度列表
        candidate_sizes: 候选节点的加注尺度列表

    Returns:
        差距值（越小越匹配）
    """
    max_len = max(len(query_sizes), len(candidate_sizes))
    total = 0.0
    for i in range(max_len):
        q = query_sizes[i] if i < len(query_sizes) else 1000.0
        c = candidate_sizes[i] if i < len(candidate_sizes) else 1000.0
        total += (q - c) ** 2
    return total


def _find_by_normalized_history(
    strategy: PreflopStrategy,
    stack_bb: int,
    normalized_history: str,
    original_history: str = "",
) -> StrategyNode | None:
    """按标准化历史（history_actions）查找最匹配的节点。

    多个匹配时优先选择与原始查询加注额差距最小的节点。

    Args:
        strategy: 翻前策略对象
        stack_bb: 筹码深度
        normalized_history: 标准化后的行动历史
        original_history: 原始查询历史（用于计算加注额差距）

    Returns:
        与原始查询加注额差距最小的匹配节点，或 None
    """
    stack_nodes = strategy.nodes_by_stack.get(stack_bb)
    if not stack_nodes:
        return None

    # 收集所有匹配的节点
    candidates = [
        (history_full, node)
        for history_full, node in stack_nodes.items()
        if node.history_actions == normalized_history
    ]

    if not candidates:
        return None

    # 提取查询历史的加注尺度
    query_sizes = _extract_raise_sizes(original_history or normalized_history)

    # 按与查询加注额的差距排序，差距小的优先
    candidates.sort(
        key=lambda x: (
            _calculate_raise_distance(query_sizes, _extract_raise_sizes(x[0])),
            len(x[0]),
            x[0],
        )
    )
    return candidates[0][1]


def query_node(
    strategy: PreflopStrategy,
    stack_bb: int,
    history: str,
) -> QueryResult | None:
    """查询指定行动历史下的策略节点。

    支持多级回退匹配：
    - Level 0: 精确匹配 history_full
    - Level 1: 去除加注量后按 history_actions 匹配
    - Level 2: CALL→FOLD 替换后精确匹配
    - Level 3: CALL→FOLD 替换后按 history_actions 匹配

    Args:
        strategy: 翻前策略对象
        stack_bb: 筹码深度（BB 数）
        history: 行动历史，如 "R2-C-R6"

    Returns:
        QueryResult 如果找到匹配，否则 None
    """
    original = history

    # Level 0: 精确匹配 history_full
    node = _try_match(strategy, stack_bb, history)
    if node is not None:
        return QueryResult(
            node=node,
            matched_history=history,
            original_history=original,
            fallback_level=0,
            fallback_description="精确匹配",
        )

    # Level 1: 去除加注量后按 history_actions 匹配
    normalized = normalize_history(history)
    # 无论 normalized 是否等于 history，都尝试按 history_actions 查找
    node = _find_by_normalized_history(strategy, stack_bb, normalized, original)
    if node is not None:
        return QueryResult(
            node=node,
            matched_history=node.history_full,
            original_history=original,
            fallback_level=1,
            fallback_description="去除加注量（按 history_actions 匹配）",
        )

    # Level 2: CALL→FOLD 替换后精确匹配
    call_variants = generate_call_to_fold_variants(history)
    for variant in call_variants:
        node = _try_match(strategy, stack_bb, variant)
        if node is not None:
            return QueryResult(
                node=node,
                matched_history=variant,
                original_history=original,
                fallback_level=2,
                fallback_description="CALL→FOLD 替换",
            )

    # Level 3: CALL→FOLD 替换后按 history_actions 匹配
    for variant in call_variants:
        normalized_variant = normalize_history(variant)
        node = _find_by_normalized_history(
            strategy, stack_bb, normalized_variant, variant
        )
        if node is not None:
            return QueryResult(
                node=node,
                matched_history=node.history_full,
                original_history=original,
                fallback_level=3,
                fallback_description="CALL→FOLD + 去量（按 history_actions 匹配）",
            )

    # Level 4: 标准化后的 CALL→FOLD 变体按 history_actions 匹配
    normalized_variants = generate_call_to_fold_variants(normalized)
    for variant in normalized_variants:
        node = _find_by_normalized_history(strategy, stack_bb, variant, original)
        if node is not None:
            return QueryResult(
                node=node,
                matched_history=node.history_full,
                original_history=original,
                fallback_level=4,
                fallback_description="去量 + CALL→FOLD（按 history_actions 匹配）",
            )

    return None
