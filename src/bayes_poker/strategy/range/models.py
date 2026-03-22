"""Range 数据模型（numpy 矩阵版本）。

PreflopRange: 13x13 矩阵
- 对角线: 手对 (AA=0,0 到 22=12,12)
- 右上三角: 同花组合
- 左下三角: 非同花组合

PostflopRange: 13x13x12 三维矩阵
- 前两维同 PreflopRange
- 第三维: 每个手牌的具体组合（按字典序 cdhs）
  - 对子: 6 种组合
  - 同花: 4 种组合
  - 非同花: 12 种组合
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from bayes_poker.strategy.range.mappings import (
    _INDEX_TO_RANK,
    _INDEX_TO_SUIT,
    RANGE_169_ORDER,
    combos_per_hand,
    get_range_169_to_1326,
    index1326_to_combo,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# 手牌键到矩阵坐标的映射
def _build_hand_key_to_matrix_coord() -> dict[str, tuple[int, int]]:
    """构建手牌键到 13x13 矩阵坐标的映射。

    Returns:
        字典: hand_key -> (row, col)
        - 对子在对角线: AA=(0,0), KK=(1,1), ..., 22=(12,12)
        - 同花在右上三角: AKs=(0,1), AQs=(0,2), ...
        - 非同花在左下三角: AKo=(1,0), AQo=(2,0), ...
    """
    mapping = {}
    rank_order = "AKQJT98765432"  # A=0, K=1, ..., 2=12

    for hand_key in RANGE_169_ORDER:
        if len(hand_key) == 2:  # 对子
            rank = hand_key[0]
            idx = rank_order.index(rank)
            mapping[hand_key] = (idx, idx)
        elif hand_key.endswith("s"):  # 同花
            r1, r2 = hand_key[0], hand_key[1]
            i1, i2 = rank_order.index(r1), rank_order.index(r2)
            # 大牌在前，所以 i1 < i2，放在右上三角
            mapping[hand_key] = (i1, i2)
        else:  # 非同花
            r1, r2 = hand_key[0], hand_key[1]
            i1, i2 = rank_order.index(r1), rank_order.index(r2)
            # 大牌在前，所以 i1 < i2，放在左下三角（转置）
            mapping[hand_key] = (i2, i1)

    return mapping


_HAND_KEY_TO_COORD = _build_hand_key_to_matrix_coord()


# 预计算组合数权重（用于向量化计算）
def _build_combo_weights() -> np.ndarray:
    """构建 13x13 组合数权重矩阵。"""
    weights = np.zeros((13, 13), dtype=np.float32)
    for hand_key in RANGE_169_ORDER:
        row, col = _HAND_KEY_TO_COORD[hand_key]
        weights[row, col] = combos_per_hand(hand_key)
    return weights


_COMBO_WEIGHTS = _build_combo_weights()


def _build_combo_order() -> dict[str, list[tuple[int, int]]]:
    """构建每个手牌键的组合顺序（按字典序 cdhs）。

    Returns:
        字典: hand_key -> [(card1_52idx, card2_52idx), ...]
    """
    from itertools import combinations

    rank_order = "AKQJT98765432"
    suit_order = "cdhs"

    combo_order = {}

    for hand_key in RANGE_169_ORDER:
        combos = []

        if len(hand_key) == 2:  # 对子
            rank = hand_key[0]
            rank_idx = rank_order.index(rank)
            # 6 种组合: cd, ch, cs, dh, ds, hs
            for i, s1 in enumerate(suit_order):
                for s2 in suit_order[i+1:]:
                    c1 = rank_idx * 4 + suit_order.index(s1)
                    c2 = rank_idx * 4 + suit_order.index(s2)
                    combos.append((c1, c2))
        else:
            r1, r2 = hand_key[0], hand_key[1]
            r1_idx = rank_order.index(r1)
            r2_idx = rank_order.index(r2)

            if hand_key.endswith("s"):  # 同花
                # 4 种组合: cc, dd, hh, ss
                for suit in suit_order:
                    suit_idx = suit_order.index(suit)
                    c1 = r1_idx * 4 + suit_idx
                    c2 = r2_idx * 4 + suit_idx
                    combos.append((c1, c2))
            else:  # 非同花
                # 12 种组合
                for s1 in suit_order:
                    for s2 in suit_order:
                        if s1 != s2:
                            c1 = r1_idx * 4 + suit_order.index(s1)
                            c2 = r2_idx * 4 + suit_order.index(s2)
                            combos.append((c1, c2))

        combo_order[hand_key] = combos

    return combo_order


_COMBO_ORDER = _build_combo_order()


@dataclass
class PreflopRange:
    """13x13 矩阵翻前策略范围。

    矩阵布局:
    - 对角线: 手对 (AA=0,0 到 22=12,12)
    - 右上三角: 同花组合
    - 左下三角: 非同花组合

    Attributes:
        strategy: 13x13 策略频率矩阵
        evs: 13x13 EV 矩阵
    """

    strategy: np.ndarray  # shape (13, 13)
    evs: np.ndarray  # shape (13, 13)

    def __post_init__(self) -> None:
        """验证数据形状。"""
        if self.strategy.shape != (13, 13):
            msg = f"strategy 形状必须为 (13, 13)，实际为 {self.strategy.shape}"
            raise ValueError(msg)
        if self.evs.shape != (13, 13):
            msg = f"evs 形状必须为 (13, 13)，实际为 {self.evs.shape}"
            raise ValueError(msg)

    def to_postflop(self) -> PostflopRange:
        """展开为 13x13x12 三维表示。

        每个手牌的 strategy 和 evs 复制到其对应的所有组合。

        Returns:
            展开后的 PostflopRange
        """
        strategy_3d = np.zeros((13, 13, 12), dtype=np.float32)
        evs_3d = np.zeros((13, 13, 12), dtype=np.float32)

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            n_combos = combos_per_hand(hand_key)

            strat_val = self.strategy[row, col]
            ev_val = self.evs[row, col]

            strategy_3d[row, col, :n_combos] = strat_val
            evs_3d[row, col, :n_combos] = ev_val

        return PostflopRange(strategy=strategy_3d, evs=evs_3d)

    def total_frequency(self) -> float:
        """计算加权总频率。

        考虑每种手牌的组合数权重：对子=6，同花=4，非同花=12。

        Returns:
            总频率（0.0 ~ 1.0）
        """
        return float(np.sum(self.strategy * _COMBO_WEIGHTS) / 1326.0)

    def total_ev(self) -> float:
        """计算加权总 EV。

        Returns:
            加权平均 EV
        """
        weighted = self.strategy * self.evs * _COMBO_WEIGHTS
        total = np.sum(weighted)
        total_combos = np.sum(self.strategy * _COMBO_WEIGHTS)
        return float(total / total_combos) if total_combos > 0 else 0.0

    def adjust_by_ev(self, threshold: float) -> None:
        """根据 EV 阈值调整策略（原地修改）。

        EV 低于阈值的手牌策略设为 0。

        Args:
            threshold: EV 阈值
        """
        mask = self.evs < threshold
        self.strategy[mask] = 0.0

    def normalize(self) -> None:
        """正则化策略矩阵（原地修改）。

        将策略频率归一化，使加权总和为 1.0。
        """
        total = np.sum(self.strategy * _COMBO_WEIGHTS)
        if total > 0:
            self.strategy *= 1326.0 / total

    def __getitem__(self, index: int) -> float:
        """获取指定 169 索引的策略值（兼容旧接口）。"""
        hand_key = RANGE_169_ORDER[index]
        row, col = _HAND_KEY_TO_COORD[hand_key]
        return float(self.strategy[row, col])

    def __setitem__(self, index: int, value: float) -> None:
        """设置指定 169 索引的策略值（兼容旧接口）。"""
        hand_key = RANGE_169_ORDER[index]
        row, col = _HAND_KEY_TO_COORD[hand_key]
        self.strategy[row, col] = value

    def __len__(self) -> int:
        """返回数据长度（169）。"""
        return 169

    def debug(self, min_strategy: float = 0.0) -> str:
        """生成调试字符串。

        Args:
            min_strategy: 只显示 strategy >= 此值的手牌

        Returns:
            格式化的调试字符串
        """
        lines = [f"PreflopRange (total_freq={self.total_frequency():.2%})"]
        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            strat = self.strategy[row, col]
            if strat >= min_strategy:
                ev = self.evs[row, col]
                lines.append(f"  {hand_key}: strategy={strat:.3f}, ev={ev:.3f}")
        return "\n".join(lines)

    def to_gtoplus(self, min_strategy: float = 0.001) -> str:
        """生成 GTO+ 格式的范围字符串。

        Args:
            min_strategy: 忽略 strategy < 此值的手牌

        Returns:
            GTO+ 格式字符串
        """
        return self.to_postflop().to_gtoplus(min_strategy=min_strategy)

    @classmethod
    def zeros(cls) -> PreflopRange:
        """创建全零矩阵。"""
        return cls(
            strategy=np.zeros((13, 13), dtype=np.float32),
            evs=np.zeros((13, 13), dtype=np.float32),
        )

    @classmethod
    def ones(cls) -> PreflopRange:
        """创建策略全一、EV 全零的矩阵。"""
        return cls(
            strategy=np.ones((13, 13), dtype=np.float32),
            evs=np.zeros((13, 13), dtype=np.float32),
        )

    @classmethod
    def from_list(cls, strategy: list[float], evs: list[float]) -> PreflopRange:
        """从 169 维列表创建（兼容旧接口）。

        Args:
            strategy: 169 维策略列表（按 RANGE_169_ORDER 顺序）
            evs: 169 维 EV 列表

        Returns:
            PreflopRange 实例
        """
        if len(strategy) != 169 or len(evs) != 169:
            msg = f"列表长度必须为 169，实际为 {len(strategy)}, {len(evs)}"
            raise ValueError(msg)

        strat_matrix = np.zeros((13, 13), dtype=np.float32)
        ev_matrix = np.zeros((13, 13), dtype=np.float32)

        for idx, hand_key in enumerate(RANGE_169_ORDER):
            row, col = _HAND_KEY_TO_COORD[hand_key]
            strat_matrix[row, col] = strategy[idx]
            ev_matrix[row, col] = evs[idx]

        return cls(strategy=strat_matrix, evs=ev_matrix)

    @classmethod
    def from_tuples(
        cls, strategy: tuple[float, ...], evs: tuple[float, ...]
    ) -> PreflopRange:
        """从 tuple 创建（兼容旧接口）。"""
        return cls.from_list(list(strategy), list(evs))

    def to_list(self) -> tuple[list[float], list[float]]:
        """转换为 169 维列表（按 RANGE_169_ORDER 顺序）。

        Returns:
            (strategy_list, evs_list)
        """
        strategy_list = []
        evs_list = []

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            strategy_list.append(float(self.strategy[row, col]))
            evs_list.append(float(self.evs[row, col]))

        return strategy_list, evs_list


@dataclass
class PostflopRange:
    """13x13x12 三维翻后策略范围。

    矩阵布局:
    - 前两维同 PreflopRange (13x13)
    - 第三维: 每个手牌的具体组合（按字典序 cdhs）
      - 对子: 6 种组合
      - 同花: 4 种组合
      - 非同花: 12 种组合

    Attributes:
        strategy: 13x13x12 策略频率张量
        evs: 13x13x12 EV 张量
    """

    strategy: np.ndarray  # shape (13, 13, 12)
    evs: np.ndarray  # shape (13, 13, 12)

    def __post_init__(self) -> None:
        """验证数据形状。"""
        if self.strategy.shape != (13, 13, 12):
            msg = f"strategy 形状必须为 (13, 13, 12)，实际为 {self.strategy.shape}"
            raise ValueError(msg)
        if self.evs.shape != (13, 13, 12):
            msg = f"evs 形状必须为 (13, 13, 12)，实际为 {self.evs.shape}"
            raise ValueError(msg)

    def to_preflop(self) -> PreflopRange:
        """聚合为 13x13 表示。

        每个手牌的值为其对应组合的平均值。

        Returns:
            聚合后的 PreflopRange
        """
        strategy_2d = np.zeros((13, 13), dtype=np.float32)
        evs_2d = np.zeros((13, 13), dtype=np.float32)

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            n_combos = combos_per_hand(hand_key)

            strategy_2d[row, col] = np.mean(self.strategy[row, col, :n_combos])
            evs_2d[row, col] = np.mean(self.evs[row, col, :n_combos])

        return PreflopRange(strategy=strategy_2d, evs=evs_2d)

    def total_frequency(self) -> float:
        """计算总频率。

        Returns:
            所有有效组合频率的平均值（0.0 ~ 1.0）
        """
        total = 0.0
        count = 0
        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            n_combos = combos_per_hand(hand_key)
            total += np.sum(self.strategy[row, col, :n_combos])
            count += n_combos
        return total / count

    def ban_cards(self, card_indices: Sequence[int]) -> None:
        """移除指定牌阻挡的组合（原地修改）。

        Args:
            card_indices: 要移除的牌的 52 索引列表
        """
        blocked = set(card_indices)

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            combos = _COMBO_ORDER[hand_key]

            for combo_idx, (c1, c2) in enumerate(combos):
                if c1 in blocked or c2 in blocked:
                    self.strategy[row, col, combo_idx] = 0.0
                    self.evs[row, col, combo_idx] = 0.0

    def normalize(self) -> None:
        """正则化策略张量（原地修改）。

        将策略频率归一化，使总和为 1.0。
        """
        total = 0.0
        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            n_combos = combos_per_hand(hand_key)
            total += np.sum(self.strategy[row, col, :n_combos])

        if total > 0:
            self.strategy /= total

    def __getitem__(self, index: int) -> float:
        """获取指定 1326 索引的策略值（兼容旧接口）。"""
        mapping = get_range_169_to_1326()
        for hand_key_idx, combo_indices in enumerate(mapping):
            if index in combo_indices:
                hand_key = RANGE_169_ORDER[hand_key_idx]
                row, col = _HAND_KEY_TO_COORD[hand_key]
                combo_idx = combo_indices.index(index)
                return float(self.strategy[row, col, combo_idx])
        raise IndexError(f"Invalid index: {index}")

    def __setitem__(self, index: int, value: float) -> None:
        """设置指定 1326 索引的策略值（兼容旧接口）。"""
        mapping = get_range_169_to_1326()
        for hand_key_idx, combo_indices in enumerate(mapping):
            if index in combo_indices:
                hand_key = RANGE_169_ORDER[hand_key_idx]
                row, col = _HAND_KEY_TO_COORD[hand_key]
                combo_idx = combo_indices.index(index)
                self.strategy[row, col, combo_idx] = value
                return
        raise IndexError(f"Invalid index: {index}")

    def __len__(self) -> int:
        """返回数据长度（1326）。"""
        return 1326

    def debug(self, min_strategy: float = 0.0, max_lines: int = 50) -> str:
        """生成调试字符串。

        Args:
            min_strategy: 只显示 strategy >= 此值的组合
            max_lines: 最多显示的行数

        Returns:
            格式化的调试字符串
        """
        lines = [f"PostflopRange (total_freq={self.total_frequency():.2%})"]
        count = 0

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            combos = _COMBO_ORDER[hand_key]

            for combo_idx, (c1, c2) in enumerate(combos):
                strat = self.strategy[row, col, combo_idx]
                if strat >= min_strategy:
                    if count >= max_lines:
                        lines.append(f"  ... (truncated)")
                        return "\n".join(lines)

                    ev = self.evs[row, col, combo_idx]
                    r1, s1 = _INDEX_TO_RANK[c1 // 4], _INDEX_TO_SUIT[c1 % 4]
                    r2, s2 = _INDEX_TO_RANK[c2 // 4], _INDEX_TO_SUIT[c2 % 4]
                    combo_str = f"{r1}{s1}{r2}{s2}"
                    lines.append(f"  {combo_str}: strategy={strat:.3f}, ev={ev:.3f}")
                    count += 1

        return "\n".join(lines)

    def to_gtoplus(self, min_strategy: float = 0.001) -> str:
        """生成 GTO+ 格式的范围字符串。

        Args:
            min_strategy: 忽略 strategy < 此值的组合

        Returns:
            GTO+ 格式字符串
        """
        parts: list[str] = []

        for hand_key in RANGE_169_ORDER:
            row, col = _HAND_KEY_TO_COORD[hand_key]
            combos = _COMBO_ORDER[hand_key]

            for combo_idx, (c1, c2) in enumerate(combos):
                strat = self.strategy[row, col, combo_idx]
                if strat < min_strategy:
                    continue

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
        """创建全零张量。"""
        return cls(
            strategy=np.zeros((13, 13, 12), dtype=np.float32),
            evs=np.zeros((13, 13, 12), dtype=np.float32),
        )

    @classmethod
    def ones(cls) -> PostflopRange:
        """创建策略全一的张量。"""
        return cls(
            strategy=np.ones((13, 13, 12), dtype=np.float32),
            evs=np.zeros((13, 13, 12), dtype=np.float32),
        )

    @classmethod
    def from_list(cls, strategy: list[float], evs: list[float]) -> PostflopRange:
        """从 1326 维列表创建（兼容旧接口）。

        Args:
            strategy: 1326 维策略列表
            evs: 1326 维 EV 列表

        Returns:
            PostflopRange 实例
        """
        if len(strategy) != 1326 or len(evs) != 1326:
            msg = f"列表长度必须为 1326，实际为 {len(strategy)}, {len(evs)}"
            raise ValueError(msg)

        strat_tensor = np.zeros((13, 13, 12), dtype=np.float32)
        ev_tensor = np.zeros((13, 13, 12), dtype=np.float32)

        mapping = get_range_169_to_1326()
        for hand_key_idx, combo_indices in enumerate(mapping):
            hand_key = RANGE_169_ORDER[hand_key_idx]
            row, col = _HAND_KEY_TO_COORD[hand_key]

            for combo_idx, idx_1326 in enumerate(combo_indices):
                strat_tensor[row, col, combo_idx] = strategy[idx_1326]
                ev_tensor[row, col, combo_idx] = evs[idx_1326]

        return cls(strategy=strat_tensor, evs=ev_tensor)

    @classmethod
    def from_tuples(
        cls, strategy: tuple[float, ...], evs: tuple[float, ...]
    ) -> PostflopRange:
        """从 tuple 创建（兼容旧接口）。"""
        return cls.from_list(list(strategy), list(evs))

    def to_list(self) -> tuple[list[float], list[float]]:
        """转换为 1326 维列表。

        Returns:
            (strategy_list, evs_list)
        """
        strategy_list = [0.0] * 1326
        evs_list = [0.0] * 1326

        mapping = get_range_169_to_1326()
        for hand_key_idx, combo_indices in enumerate(mapping):
            hand_key = RANGE_169_ORDER[hand_key_idx]
            row, col = _HAND_KEY_TO_COORD[hand_key]

            for combo_idx, idx_1326 in enumerate(combo_indices):
                strategy_list[idx_1326] = float(self.strategy[row, col, combo_idx])
                evs_list[idx_1326] = float(self.evs[row, col, combo_idx])

        return strategy_list, evs_list


# ============================================================================
# 辅助函数：169 顺序提取/散布（用于向量化操作）
# ============================================================================


def _get_169_order_indices() -> np.ndarray:
    """返回 (169, 2) 数组，每行为 (row, col)。"""
    indices = np.zeros((169, 2), dtype=np.int32)
    for idx, hand_key in enumerate(RANGE_169_ORDER):
        row, col = _HAND_KEY_TO_COORD[hand_key]
        indices[idx] = [row, col]
    return indices


_INDICES_169 = _get_169_order_indices()


def extract_by_169_order(matrix: np.ndarray) -> np.ndarray:
    """按 RANGE_169_ORDER 提取为 169 维数组。"""
    return matrix[_INDICES_169[:, 0], _INDICES_169[:, 1]]


def scatter_by_169_order(values: np.ndarray, dtype=np.float32) -> np.ndarray:
    """将 169 维数组按 RANGE_169_ORDER 散布到矩阵。"""
    result = np.zeros((13, 13), dtype=dtype)
    result[_INDICES_169[:, 0], _INDICES_169[:, 1]] = values
    return result

