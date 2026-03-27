"""预留检验 bucket 相似度映射逻辑的白盒测试。"""

from __future__ import annotations

from bayes_poker.strategy.preflop_parse import normalize_history

from bayes_poker.strategy.strategy_engine.population_vb.bucket_similarity import (
    map_solver_node_to_preflop_param_index,
)


def _make_solver_node(*, history_full: str, acting_position: str) -> dict[str, str]:
    """构造只带历史与位置的 solver_node 记录。

    Args:
        history_full: 完整历史字符串。
        acting_position: 当前待行动位置。

    Returns:
        仅包含历史与位置的节点字典。
    """

    return {
        "history_full": history_full,
        "history_actions": normalize_history(history_full),
        "acting_position": acting_position,
    }


def test_map_param_index_first_in_root() -> None:
    """根节点 UTG 对应 bucket 0。"""

    node = _make_solver_node(history_full="", acting_position="UTG")
    assert map_solver_node_to_preflop_param_index(node) == 0


def test_map_param_index_first_in_bb_limp_defense() -> None:
    """BB limp defense 应落在 bucket 19。"""

    node = _make_solver_node(history_full="F-F-F-F-C", acting_position="BB")
    assert map_solver_node_to_preflop_param_index(node) == 19


def test_map_param_index_passive_reentry() -> None:
    """Passive re-entry 场景应落在 bucket 25。"""

    node = _make_solver_node(
        history_full="R2-C-F-F-R6-F-F",
        acting_position="HJ",
    )
    assert map_solver_node_to_preflop_param_index(node) == 25


def test_map_param_index_active_reentry() -> None:
    """Active re-entry 场景应落在 bucket 45。"""

    node = _make_solver_node(
        history_full="F-F-R3-F-R8-F",
        acting_position="CO",
    )
    assert map_solver_node_to_preflop_param_index(node) == 45


def test_map_param_index_aggressor_first_in_flag() -> None:
    """Aggressor_first_in True/False 两种历史应映射到不同桶。"""

    true_aggressor = _make_solver_node(
        history_full="F-F-R3-F-R8-F",
        acting_position="CO",
    )
    false_aggressor = _make_solver_node(
        history_full="C-F-R3-F-F-F-R8",
        acting_position="CO",
    )

    result_true = map_solver_node_to_preflop_param_index(true_aggressor)
    result_false = map_solver_node_to_preflop_param_index(false_aggressor)
    assert result_true == 45
    assert result_false == 47


def test_map_param_index_returns_none_for_unknown_token() -> None:
    """历史包含未知 token 时应返回 None。"""

    node = _make_solver_node(
        history_full="F-F-R3-X-R8-F",
        acting_position="CO",
    )
    assert map_solver_node_to_preflop_param_index(node) is None
