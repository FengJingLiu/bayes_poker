"""翻前策略解析数据模型。

定义用于表示 GTOWizard 风格翻前策略的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH

if TYPE_CHECKING:
    from collections.abc import Sequence

# 策略向量长度（对应 13x13 = 169 种起手牌组合）
STRATEGY_VECTOR_LENGTH = RANGE_169_LENGTH


@dataclass(frozen=True, slots=True)
class StrategyAction:
    """单个策略行动记录。

    Attributes:
        order_index: 行动在 solutions 数组中的索引（从 0 开始）
        action_code: 行动代码，如 "F", "R2", "R2.5", "RAI", "C" 等
        action_type: 行动类型，如 "FOLD", "RAISE", "CALL"
        bet_size_bb: 下注大小（以 BB 为单位）；对于 FOLD/CALL 或 ALLIN 为 None
        is_all_in: 是否为全下
        total_frequency: 该行动的总体频率（0.0 ~ 1.0）
        next_position: 下一个行动位置，如 "HJ", "BB" 等
        range: 每种起手牌（169 种）的策略频率和 EV 向量
        total_ev: 该行动的总 EV
        total_combos: 该行动的总组合数
    """

    order_index: int
    action_code: str
    action_type: str
    bet_size_bb: float | None
    is_all_in: bool
    total_frequency: float
    next_position: str
    range: PreflopRange
    total_ev: float = 0.0
    total_combos: float = 0.0


@dataclass(frozen=True, slots=True)
class StrategyNode:
    """策略节点，表示某个行动历史下的决策点。

    Attributes:
        history_full: 完整的行动历史字符串，如 "F-R2-R6.5-F-R17.5-R35-RAI-C"
        history_actions: 标准化后的行动序列，如 "F-R-R-F-R-R-R-C"
        history_token_count: 行动历史中的 token 数量
        acting_position: 当前行动位置，如 "UTG", "BB" 等
        source_file: 来源文件名
        actions: 该节点可选的行动列表
    """

    history_full: str
    history_actions: str
    history_token_count: int
    acting_position: str
    source_file: str
    actions: tuple[StrategyAction, ...]


@dataclass(slots=True)
class PreflopStrategy:
    """翻前策略集合，按 stack_bb 分组。

    Attributes:
        name: 策略名称，如 "Cash6m50zGeneral"
        source_dir: 策略文件来源目录
        nodes_by_stack: 按 stack_bb 分组的策略节点字典
            - 外层 key: stack_bb（如 100）
            - 内层 key: history_full（如 "" 表示根节点、"F-R2" 表示某行动线）
    """

    name: str
    source_dir: str
    nodes_by_stack: dict[int, dict[str, StrategyNode]] = field(default_factory=dict)

    def get_node(self, stack_bb: int, history_full: str = "") -> StrategyNode | None:
        """获取指定 stack 和行动历史下的策略节点。

        Args:
            stack_bb: 筹码深度（BB 数）
            history_full: 完整行动历史（空字符串表示根节点/开局）

        Returns:
            对应的策略节点，或 None（如果不存在）
        """
        stack_nodes = self.nodes_by_stack.get(stack_bb)
        if stack_nodes is None:
            return None
        return stack_nodes.get(history_full)

    def add_node(self, stack_bb: int, node: StrategyNode) -> None:
        """添加策略节点。

        Args:
            stack_bb: 筹码深度（BB 数）
            node: 策略节点
        """
        if stack_bb not in self.nodes_by_stack:
            self.nodes_by_stack[stack_bb] = {}
        self.nodes_by_stack[stack_bb][node.history_full] = node

    def stack_sizes(self) -> list[int]:
        """获取所有可用的 stack 大小。

        Returns:
            排序后的 stack_bb 列表
        """
        return sorted(self.nodes_by_stack.keys())

    def node_count(self, stack_bb: int | None = None) -> int:
        """获取节点数量。

        Args:
            stack_bb: 指定 stack 大小；如果为 None 则统计所有

        Returns:
            节点数量
        """
        if stack_bb is not None:
            return len(self.nodes_by_stack.get(stack_bb, {}))
        return sum(len(nodes) for nodes in self.nodes_by_stack.values())

    def query(
        self,
        stack_bb: int,
        history: str,
    ) -> "QueryResult | None":
        """查询指定行动历史下的策略节点。

        支持多级回退匹配：精确匹配 → 去量匹配 → CALL→FOLD 替换。

        Args:
            stack_bb: 筹码深度（BB 数）
            history: 行动历史，如 "R2-C-R6"

        Returns:
            QueryResult 如果找到匹配，否则 None
        """
        from bayes_poker.strategy.preflop.query import query_node

        return query_node(self, stack_bb, history)
