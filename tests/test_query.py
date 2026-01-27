"""策略查询回退匹配测试。"""

from pathlib import Path

import pytest

from bayes_poker.strategy.preflop_parse import (
    QueryResult,
    generate_call_to_fold_variants,
    normalize_history,
    query_node,
    parse_strategy_directory,
    PreflopStrategy,
)

# 测试数据路径
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CASH6M_STRATEGY_DIR = FIXTURES_DIR / "Cash6m50zGeneral"


@pytest.fixture(scope="module")
def cash6m_strategy() -> PreflopStrategy:
    """加载 Cash6m50zGeneral 测试策略。"""
    if not CASH6M_STRATEGY_DIR.exists():
        pytest.skip(f"测试策略目录不存在: {CASH6M_STRATEGY_DIR}")
    return parse_strategy_directory(CASH6M_STRATEGY_DIR)


class TestNormalizeHistory:
    """normalize_history 函数测试。"""

    def test_empty(self) -> None:
        assert normalize_history("") == ""

    def test_simple(self) -> None:
        assert normalize_history("F-C") == "F-C"

    def test_remove_amounts(self) -> None:
        assert normalize_history("R2-C") == "R-C"
        assert normalize_history("R2.5-R8") == "R-R"
        assert normalize_history("R17.5-C-R35") == "R-C-R"

    def test_rai(self) -> None:
        assert normalize_history("R2-RAI") == "R-R"

    def test_mixed(self) -> None:
        assert normalize_history("F-R2-C-R6.5-F") == "F-R-C-R-F"


class TestGenerateCallToFoldVariants:
    """generate_call_to_fold_variants 函数测试。"""

    def test_no_calls(self) -> None:
        assert generate_call_to_fold_variants("R2-F") == []
        assert generate_call_to_fold_variants("F-F-F") == []

    def test_single_call(self) -> None:
        variants = generate_call_to_fold_variants("R2-C")
        assert variants == ["R2-F"]

    def test_multiple_calls(self) -> None:
        variants = generate_call_to_fold_variants("R2-C-R6-C")
        assert len(variants) == 2
        assert variants[0] == "R2-C-R6-F"
        assert variants[1] == "R2-F-R6-F"

    def test_three_calls(self) -> None:
        variants = generate_call_to_fold_variants("C-C-C")
        assert len(variants) == 3
        assert variants[0] == "C-C-F"
        assert variants[1] == "C-F-F"
        assert variants[2] == "F-F-F"


class TestRealStrategyQuery:
    """使用真实 Cash6m50zGeneral 策略的查询测试。

    注意：测试用例基于实际策略数据结构。
    """

    def test_root_node(self, cash6m_strategy: PreflopStrategy) -> None:
        """空历史应该匹配根节点。"""
        result = cash6m_strategy.query(100, "")
        assert result is not None
        assert result.fallback_level == 0
        assert result.matched_history == ""

    def test_exact_match_r2(self, cash6m_strategy: PreflopStrategy) -> None:
        """R2 应该精确匹配。"""
        result = cash6m_strategy.query(100, "R2")
        assert result is not None
        assert result.fallback_level == 0
        assert result.matched_history == "R2"

    def test_fallback_r2_5_to_r2(self, cash6m_strategy: PreflopStrategy) -> None:
        """R2.5 策略中不存在，应通过 history_actions 回退到 R2。"""
        result = cash6m_strategy.query(100, "R2.5")
        assert result is not None
        # 策略中没有 R2.5，回退匹配到 R2
        assert result.fallback_level >= 1
        assert result.matched_history == "R2"

    def test_fallback_r4_r8(self, cash6m_strategy: PreflopStrategy) -> None:
        """R4-R8 应回退到 R-R 匹配（如 R2-R6.5）。"""
        result = cash6m_strategy.query(100, "R4-R8")
        assert result is not None
        assert result.fallback_level >= 1
        # 应匹配到类似 R2-R6.5 的节点
        assert "R" in result.matched_history

    def test_fallback_r2_c(self, cash6m_strategy: PreflopStrategy) -> None:
        """R2-C 应能通过 history_actions 匹配到 R-C 模式节点。"""
        result = cash6m_strategy.query(100, "R2-C")
        assert result is not None
        # 会通过 history_actions 匹配

    def test_fallback_r2_c_f(self, cash6m_strategy: PreflopStrategy) -> None:
        """R2-C-F 应能匹配到 R-C-F 模式节点。"""
        result = cash6m_strategy.query(100, "R2-C-F")
        assert result is not None

    def test_fallback_r3_c_f(self, cash6m_strategy: PreflopStrategy) -> None:
        """R3-C-F 应能通过去量回退匹配到 R-C-F 模式节点。"""
        result = cash6m_strategy.query(100, "R3-C-F")
        assert result is not None
        assert result.fallback_level >= 1

    def test_exact_match_rai(self, cash6m_strategy: PreflopStrategy) -> None:
        """RAI 应该精确匹配（策略中存在 RAI 节点）。"""
        result = cash6m_strategy.query(100, "RAI")
        assert result is not None
        assert result.matched_history == "RAI"

    def test_query_deep_history(self, cash6m_strategy: PreflopStrategy) -> None:
        """测试较深的行动历史查询。"""
        # 使用策略中实际存在的路径
        result = cash6m_strategy.query(100, "F-F-F-F-C-R3")
        assert result is not None
        # 可能精确匹配或需要回退

    def test_no_match_nonsense(self, cash6m_strategy: PreflopStrategy) -> None:
        """完全无效的历史应该返回 None。"""
        result = cash6m_strategy.query(100, "X-Y-Z-W-Q")
        assert result is None

    def test_already_normalized_r(self, cash6m_strategy: PreflopStrategy) -> None:
        """已标准化输入 R 应通过 history_actions 匹配到 R2 等节点。"""
        result = cash6m_strategy.query(100, "R")
        assert result is not None
        assert result.fallback_level >= 1
        # 应匹配到 history_actions == "R" 的节点

    def test_already_normalized_r_c(self, cash6m_strategy: PreflopStrategy) -> None:
        """已标准化输入 R-C 应通过 history_actions 匹配。"""
        result = cash6m_strategy.query(100, "R-C")
        assert result is not None
        assert result.fallback_level >= 1

    def test_fallback_r4_c_r9(self, cash6m_strategy: PreflopStrategy) -> None:
        """R4-C-R9 应通过 CALL→FOLD + 去量回退匹配。"""
        result = cash6m_strategy.query(100, "R4-C-R9")
        assert result is not None
        assert result.fallback_level >= 1
