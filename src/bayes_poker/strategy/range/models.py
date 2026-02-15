"""Range 数据模型。

定义统一的 Range 类用于表示 preflop（169维）和 postflop（1326维）策略向量。

slots 参数说明：
    slots=True 会让 dataclass 生成 __slots__ 属性，带来以下优化：
    1. 内存效率：不再使用 __dict__ 存储属性，每个实例节省约 100+ 字节
    2. 访问速度：属性访问比 __dict__ 查找更快（约 20-30%）
    3. 属性限制：只能使用声明的属性，防止意外添加新属性

    适合大量创建的轻量对象（如 Range），不适合需要动态添加属性的场景。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.strategy.range.mappings import (
    RANGE_169_LENGTH,
    RANGE_1326_LENGTH,
    combos_per_hand,
    get_range_169_to_1326,
    get_range_1326_to_169,
    index1326_to_combo,
    RANGE_169_ORDER,
    _INDEX_TO_RANK,
    _INDEX_TO_SUIT,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(slots=True)
class PreflopRange:
    """169 维翻前策略范围。

    包含策略频率和 EV 向量，支持可变操作以便根据 EV 调整策略。
    数据按 GTOWizard 顺序排列，与 RANGE_169_ORDER 对应。

    Attributes:
        strategy: 169 维策略频率向量（每手牌的行动概率）
        evs: 169 维 EV 向量（每手牌的期望值）
    """

    strategy: list[float] = field(default_factory=lambda: [0.0] * RANGE_169_LENGTH)
    evs: list[float] = field(default_factory=lambda: [0.0] * RANGE_169_LENGTH)

    def __post_init__(self) -> None:
        """验证数据长度。"""
        if len(self.strategy) != RANGE_169_LENGTH:
            msg = f"strategy 长度必须为 {RANGE_169_LENGTH}，实际为 {len(self.strategy)}"
            raise ValueError(msg)
        if len(self.evs) != RANGE_169_LENGTH:
            msg = f"evs 长度必须为 {RANGE_169_LENGTH}，实际为 {len(self.evs)}"
            raise ValueError(msg)

    def to_postflop(self) -> PostflopRange:
        """展开为 1326 维表示。

        每个 169 手牌的 strategy 和 evs 复制到其对应的所有 1326 组合。

        Returns:
            展开后的 1326 维 PostflopRange
        """
        strategy_1326 = [0.0] * RANGE_1326_LENGTH
        evs_1326 = [0.0] * RANGE_1326_LENGTH
        mapping = get_range_169_to_1326()

        for idx_169, combo_indices in enumerate(mapping):
            strat_val = self.strategy[idx_169]
            ev_val = self.evs[idx_169]
            for combo_idx in combo_indices:
                strategy_1326[combo_idx] = strat_val
                evs_1326[combo_idx] = ev_val

        return PostflopRange(strategy=strategy_1326, evs=evs_1326)

    def total_frequency(self) -> float:
        """计算加权总频率。

        考虑每种手牌的组合数权重：对子=6，同花=4，非同花=12。

        Returns:
            总频率（0.0 ~ 1.0）
        """
        total = 0.0
        for idx, value in enumerate(self.strategy):
            combos = combos_per_hand(RANGE_169_ORDER[idx])
            total += value * combos
        return total / RANGE_1326_LENGTH

    def total_ev(self) -> float:
        """计算加权总 EV。

        Returns:
            加权平均 EV
        """
        total = 0.0
        total_combos = 0.0
        for idx, (strat, ev) in enumerate(zip(self.strategy, self.evs)):
            combos = combos_per_hand(RANGE_169_ORDER[idx])
            total += strat * ev * combos
            total_combos += strat * combos
        return total / total_combos if total_combos > 0 else 0.0

    def adjust_by_ev(self, threshold: float) -> None:
        """根据 EV 阈值调整策略。

        EV 低于阈值的手牌策略设为 0。

        Args:
            threshold: EV 阈值
        """
        for i in range(RANGE_169_LENGTH):
            if self.evs[i] < threshold:
                self.strategy[i] = 0.0

    def normalize(self) -> None:
        """正则化策略向量。

        将策略频率归一化，使加权总和为 1.0。
        考虑每种手牌的组合数权重：对子=6，同花=4，非同花=12。
        """
        total = 0.0
        for idx, value in enumerate(self.strategy):
            combos = combos_per_hand(RANGE_169_ORDER[idx])
            total += value * combos

        if total > 0:
            norm = RANGE_1326_LENGTH / total
            for i in range(RANGE_169_LENGTH):
                self.strategy[i] *= norm

    def __getitem__(self, index: int) -> float:
        """获取指定索引的策略值。"""
        return self.strategy[index]

    def __setitem__(self, index: int, value: float) -> None:
        """设置指定索引的策略值。"""
        self.strategy[index] = value

    def __len__(self) -> int:
        """返回数据长度。"""
        return len(self.strategy)

    def debug(self, min_strategy: float = 0.0) -> str:
        """生成调试字符串，打印每个手牌的 strategy 和 ev。

        Args:
            min_strategy: 只显示 strategy >= 此值的手牌

        Returns:
            格式化的调试字符串
        """
        lines = [f"PreflopRange (total_freq={self.total_frequency():.2%})"]
        for idx in range(RANGE_169_LENGTH):
            strat = self.strategy[idx]
            if strat >= min_strategy:
                ev = self.evs[idx]
                hand_key = RANGE_169_ORDER[idx]
                lines.append(f"  {hand_key}: strategy={strat:.3f}, ev={ev:.3f}")
        return "\n".join(lines)

    def to_gtoplus(self, min_strategy: float = 0.001) -> str:
        """生成 GTO+ 格式的范围字符串。

        展开为 1326 维后委托给 PostflopRange.to_gtoplus()。

        Args:
            min_strategy: 忽略 strategy < 此值的手牌（默认 0.001）

        Returns:
            GTO+ 格式字符串，如 "[50.0]AhKs[/50.0],[100.0]AsAd[/100.0]"
        """
        return self.to_postflop().to_gtoplus(min_strategy=min_strategy)

    @classmethod
    def zeros(cls) -> PreflopRange:
        """创建全零向量。"""
        return cls()

    @classmethod
    def ones(cls) -> PreflopRange:
        """创建策略全一、EV 全零的向量。"""
        return cls(strategy=[1.0] * RANGE_169_LENGTH)

    @classmethod
    def from_tuples(
        cls, strategy: tuple[float, ...], evs: tuple[float, ...]
    ) -> PreflopRange:
        """从 tuple 创建（兼容旧接口）。"""
        return cls(strategy=list(strategy), evs=list(evs))


@dataclass(slots=True)
class PostflopRange:
    """1326 维翻后策略范围。

    包含策略频率和 EV 向量，支持可变操作。

    Attributes:
        strategy: 1326 维策略频率向量
        evs: 1326 维 EV 向量
    """

    strategy: list[float] = field(default_factory=lambda: [0.0] * RANGE_1326_LENGTH)
    evs: list[float] = field(default_factory=lambda: [0.0] * RANGE_1326_LENGTH)

    def __post_init__(self) -> None:
        """验证数据长度。"""
        if len(self.strategy) != RANGE_1326_LENGTH:
            msg = (
                f"strategy 长度必须为 {RANGE_1326_LENGTH}，实际为 {len(self.strategy)}"
            )
            raise ValueError(msg)
        if len(self.evs) != RANGE_1326_LENGTH:
            msg = f"evs 长度必须为 {RANGE_1326_LENGTH}，实际为 {len(self.evs)}"
            raise ValueError(msg)

    def to_preflop(self) -> PreflopRange:
        """聚合为 169 维表示。

        每个 169 手牌的值为其对应 1326 组合的平均值。

        Returns:
            聚合后的 169 维 PreflopRange
        """
        strategy_169 = [0.0] * RANGE_169_LENGTH
        evs_169 = [0.0] * RANGE_169_LENGTH
        mapping = get_range_169_to_1326()

        for idx_169, combo_indices in enumerate(mapping):
            if combo_indices:
                strat_sum = sum(self.strategy[i] for i in combo_indices)
                ev_sum = sum(self.evs[i] for i in combo_indices)
                count = len(combo_indices)
                strategy_169[idx_169] = strat_sum / count
                evs_169[idx_169] = ev_sum / count

        return PreflopRange(strategy=strategy_169, evs=evs_169)

    def total_frequency(self) -> float:
        """计算总频率。

        Returns:
            所有组合频率的平均值（0.0 ~ 1.0）
        """
        return sum(self.strategy) / RANGE_1326_LENGTH

    def ban_cards(self, card_indices: Sequence[int]) -> None:
        """移除指定牌阻挡的组合（原地修改）。

        Args:
            card_indices: 要移除的牌的 52 索引列表
        """
        blocked = set(card_indices)

        for combo_idx in range(RANGE_1326_LENGTH):
            card1, card2 = index1326_to_combo(combo_idx)
            if card1 in blocked or card2 in blocked:
                self.strategy[combo_idx] = 0.0
                self.evs[combo_idx] = 0.0

    def normalize(self) -> None:
        """正则化策略向量。

        将策略频率归一化，使总和为 1.0。
        """
        total = sum(self.strategy)

        if total > 0:
            norm = 1.0 / total
            for i in range(RANGE_1326_LENGTH):
                self.strategy[i] *= norm

    def __getitem__(self, index: int) -> float:
        """获取指定索引的策略值。"""
        return self.strategy[index]

    def __setitem__(self, index: int, value: float) -> None:
        """设置指定索引的策略值。"""
        self.strategy[index] = value

    def __len__(self) -> int:
        """返回数据长度。"""
        return len(self.strategy)

    def debug(self, min_strategy: float = 0.0, max_lines: int = 50) -> str:
        """生成调试字符串，打印每个组合的 strategy 和 ev。

        Args:
            min_strategy: 只显示 strategy >= 此值的组合
            max_lines: 最多显示的行数

        Returns:
            格式化的调试字符串
        """
        lines = [f"PostflopRange (total_freq={self.total_frequency():.2%})"]
        count = 0
        for idx in range(RANGE_1326_LENGTH):
            strat = self.strategy[idx]
            if strat >= min_strategy:
                if count >= max_lines:
                    lines.append(f"  ... (truncated, {RANGE_1326_LENGTH - count} more)")
                    break
                ev = self.evs[idx]
                c1, c2 = index1326_to_combo(idx)
                r1, s1 = _INDEX_TO_RANK[c1 // 4], _INDEX_TO_SUIT[c1 % 4]
                r2, s2 = _INDEX_TO_RANK[c2 // 4], _INDEX_TO_SUIT[c2 % 4]
                combo_str = f"{r1}{s1}{r2}{s2}"
                lines.append(f"  {combo_str}: strategy={strat:.3f}, ev={ev:.3f}")
                count += 1
        return "\n".join(lines)

    def to_gtoplus(self, min_strategy: float = 0.001) -> str:
        """生成 GTO+ 格式的范围字符串。

        格式示例: [15.8]8s7d[/15.8],[15.8]8s7c[/15.8]
        括号内是权重百分比（0-100）。
        权重为 100% 时直接输出组合名称，不加权重标签。
        权重为 0 或低于 min_strategy 的组合会被跳过。

        Args:
            min_strategy: 忽略 strategy < 此值的组合（默认 0.001）

        Returns:
            GTO+ 格式字符串，可直接粘贴到 GTO+ 软件中
        """
        parts: list[str] = []
        for idx in range(RANGE_1326_LENGTH):
            strat = self.strategy[idx]
            if strat < min_strategy:
                continue
            c1, c2 = index1326_to_combo(idx)
            r1, s1 = _INDEX_TO_RANK[c1 // 4], _INDEX_TO_SUIT[c1 % 4]
            r2, s2 = _INDEX_TO_RANK[c2 // 4], _INDEX_TO_SUIT[c2 % 4]
            combo_str = f"{r1}{s1}{r2}{s2}"
            weight = round(strat * 100, 1)
            if weight >= 100.0:
                parts.append(combo_str)
            else:
                parts.append(f"[{weight}]{combo_str}[/{weight}]")
        return ",".join(parts)

    @classmethod
    def zeros(cls) -> PostflopRange:
        """创建全零向量。"""
        return cls()

    @classmethod
    def ones(cls) -> PostflopRange:
        """创建策略全一的向量。"""
        return cls(strategy=[1.0] * RANGE_1326_LENGTH)

    @classmethod
    def from_tuples(
        cls, strategy: tuple[float, ...], evs: tuple[float, ...]
    ) -> PostflopRange:
        """从 tuple 创建（兼容旧接口）。"""
        return cls(strategy=list(strategy), evs=list(evs))
