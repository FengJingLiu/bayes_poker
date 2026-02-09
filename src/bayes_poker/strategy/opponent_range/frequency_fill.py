"""limp 场景的 Calling Range 频率填充算法。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bayes_poker.strategy.range import RANGE_1326_LENGTH, PreflopRange, get_range_1326_to_169

if TYPE_CHECKING:
    from bayes_poker.strategy.preflop_parse.models import StrategyAction, StrategyNode


def _clamp_probability(value: float) -> float:
    """限制概率到 [0.0, 1.0] 区间。

    Args:
        value: 输入概率。

    Returns:
        归一化后的概率值。
    """
    return max(0.0, min(1.0, float(value)))


def _is_raise_action(action: "StrategyAction") -> bool:
    """判断是否为 raise 类动作。

    Args:
        action: 策略动作。

    Returns:
        是否为 raise 类动作。
    """
    action_type = str(action.action_type).upper()
    if action.is_all_in:
        return True
    return action_type in {"RAISE", "BET"} or action.action_code.upper().startswith("R")


def _raise_sort_key(action: "StrategyAction") -> tuple[float, int]:
    """返回 raise 动作排序键。

    Args:
        action: 策略动作。

    Returns:
        `(bet_size_bb, order_index)` 键值, 尺度越小越靠前。
    """
    if action.bet_size_bb is None:
        return (float("inf"), action.order_index)
    return (float(action.bet_size_bb), action.order_index)


def _pick_min_size_raise_action(node: "StrategyNode") -> "StrategyAction | None":
    """选择最小尺度 raise 动作。

    Args:
        node: 策略节点。

    Returns:
        最小尺度 raise 动作, 不存在时返回 `None`。
    """
    raise_actions = [action for action in node.actions if _is_raise_action(action)]
    if not raise_actions:
        return None
    raise_actions.sort(key=_raise_sort_key)
    return raise_actions[0]


def _build_sorted_combo_indices_by_ev(raise_action: "StrategyAction") -> list[int]:
    """按 raise EV 从高到低构建 1326 组合排序。

    Args:
        raise_action: 用于排序的 raise 动作。

    Returns:
        排序后的组合索引列表。
    """
    mapping_1326_to_169 = get_range_1326_to_169()
    return sorted(
        range(RANGE_1326_LENGTH),
        key=lambda combo_idx: (
            float(raise_action.range.evs[mapping_1326_to_169[combo_idx]]),
            -combo_idx,
        ),
        reverse=True,
    )


def _build_trapezoid_combo_probabilities(
    *,
    sorted_combo_indices: list[int],
    raise_frequency: float,
    call_frequency: float,
) -> list[float]:
    """按 A/B 目标生成 1326 维梯形信念分布。

    算法流程:
    1. 剔除顶端 A% 组合。
    2. 后续 B% 组合先设为 100% call。
    3. 用右侧尾部质量转移到 raise 尾部, 形成左升右降梯形。

    Args:
        sorted_combo_indices: 按 EV 降序的组合索引。
        raise_frequency: A, raise 频率。
        call_frequency: B, call 频率。

    Returns:
        1326 维组合 call 概率向量。
    """
    probs = [0.0] * RANGE_1326_LENGTH
    if not sorted_combo_indices:
        return probs

    raise_ratio = _clamp_probability(raise_frequency)
    call_ratio = _clamp_probability(call_frequency)
    raise_count = min(
        RANGE_1326_LENGTH,
        max(0, int(round(raise_ratio * RANGE_1326_LENGTH))),
    )
    max_callable = RANGE_1326_LENGTH - raise_count
    call_count = min(
        max_callable,
        max(0, int(round(call_ratio * RANGE_1326_LENGTH))),
    )
    if call_count <= 0:
        return probs

    call_start = raise_count
    call_end = raise_count + call_count

    for combo_idx in sorted_combo_indices[call_start:call_end]:
        probs[combo_idx] = 1.0

    if raise_count <= 0 or call_count <= 1:
        return probs

    smooth_count = min(
        max(1, call_count // 5),
        raise_count,
        call_count,
    )
    left_candidates = sorted_combo_indices[call_start - smooth_count : call_start]
    right_candidates = sorted_combo_indices[call_end - smooth_count : call_end]

    for i in range(smooth_count):
        left_prob = float(i + 1) / float(smooth_count + 1)
        right_prob = float(smooth_count - i) / float(smooth_count + 1)
        probs[left_candidates[i]] = max(probs[left_candidates[i]], left_prob)
        probs[right_candidates[i]] = min(probs[right_candidates[i]], right_prob)

    return probs


def _aggregate_combo_probs_to_preflop_range(
    combo_probs: list[float],
    *,
    evs_169: list[float],
) -> PreflopRange:
    """将 1326 组合概率聚合为 169 手牌概率。

    Args:
        combo_probs: 1326 维组合概率。
        evs_169: 169 维 EV 向量。

    Returns:
        聚合后的 169 维范围。
    """
    mapping_1326_to_169 = get_range_1326_to_169()
    strategy_sum = [0.0] * len(evs_169)
    strategy_count = [0] * len(evs_169)

    for combo_idx, combo_prob in enumerate(combo_probs):
        idx_169 = mapping_1326_to_169[combo_idx]
        strategy_sum[idx_169] += float(combo_prob)
        strategy_count[idx_169] += 1

    strategy = [0.0] * len(evs_169)
    for idx_169, total in enumerate(strategy_sum):
        count = strategy_count[idx_169]
        strategy[idx_169] = (total / float(count)) if count > 0 else 0.0

    return PreflopRange(strategy=strategy, evs=list(evs_169))


def build_limp_calling_range(
    *,
    node: "StrategyNode",
    raise_frequency: float,
    call_frequency: float,
) -> PreflopRange:
    """构建 limp 场景 Calling Range。

    Args:
        node: 当前前缀对应的翻前策略节点。
        raise_frequency: A, 统计中的 raise 频率。
        call_frequency: B, 统计中的 call 频率。

    Returns:
        169 维 calling range。
    """
    raise_action = _pick_min_size_raise_action(node)
    if raise_action is None:
        return PreflopRange.zeros()

    sorted_combo_indices = _build_sorted_combo_indices_by_ev(raise_action)
    combo_probs = _build_trapezoid_combo_probabilities(
        sorted_combo_indices=sorted_combo_indices,
        raise_frequency=raise_frequency,
        call_frequency=call_frequency,
    )
    return _aggregate_combo_probs_to_preflop_range(
        combo_probs,
        evs_169=list(raise_action.range.evs),
    )
