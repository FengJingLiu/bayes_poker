"""169↔1326 手牌映射工具。

提供 GTOWizard 风格 169 手牌顺序与 1326 组合索引之间的映射。
"""

from __future__ import annotations

from functools import reduce
from itertools import combinations

# ============================================================================
# 常量定义
# ============================================================================

# 169 维策略向量长度
RANGE_169_LENGTH = 169

# 1326 维策略向量长度（52 choose 2）
RANGE_1326_LENGTH = 1326

# GTOWizard 顺序的 169 手牌键
RANGE_169_ORDER: tuple[str, ...] = (
    "22",
    "32o",
    "32s",
    "33",
    "42o",
    "42s",
    "43o",
    "43s",
    "44",
    "52o",
    "52s",
    "53o",
    "53s",
    "54o",
    "54s",
    "55",
    "62o",
    "62s",
    "63o",
    "63s",
    "64o",
    "64s",
    "65o",
    "65s",
    "66",
    "72o",
    "72s",
    "73o",
    "73s",
    "74o",
    "74s",
    "75o",
    "75s",
    "76o",
    "76s",
    "77",
    "82o",
    "82s",
    "83o",
    "83s",
    "84o",
    "84s",
    "85o",
    "85s",
    "86o",
    "86s",
    "87o",
    "87s",
    "88",
    "92o",
    "92s",
    "93o",
    "93s",
    "94o",
    "94s",
    "95o",
    "95s",
    "96o",
    "96s",
    "97o",
    "97s",
    "98o",
    "98s",
    "99",
    "A2o",
    "A2s",
    "A3o",
    "A3s",
    "A4o",
    "A4s",
    "A5o",
    "A5s",
    "A6o",
    "A6s",
    "A7o",
    "A7s",
    "A8o",
    "A8s",
    "A9o",
    "A9s",
    "AA",
    "AJo",
    "AJs",
    "AKo",
    "AKs",
    "AQo",
    "AQs",
    "ATo",
    "ATs",
    "J2o",
    "J2s",
    "J3o",
    "J3s",
    "J4o",
    "J4s",
    "J5o",
    "J5s",
    "J6o",
    "J6s",
    "J7o",
    "J7s",
    "J8o",
    "J8s",
    "J9o",
    "J9s",
    "JJ",
    "JTo",
    "JTs",
    "K2o",
    "K2s",
    "K3o",
    "K3s",
    "K4o",
    "K4s",
    "K5o",
    "K5s",
    "K6o",
    "K6s",
    "K7o",
    "K7s",
    "K8o",
    "K8s",
    "K9o",
    "K9s",
    "KJo",
    "KJs",
    "KK",
    "KQo",
    "KQs",
    "KTo",
    "KTs",
    "Q2o",
    "Q2s",
    "Q3o",
    "Q3s",
    "Q4o",
    "Q4s",
    "Q5o",
    "Q5s",
    "Q6o",
    "Q6s",
    "Q7o",
    "Q7s",
    "Q8o",
    "Q8s",
    "Q9o",
    "Q9s",
    "QJo",
    "QJs",
    "QQ",
    "QTo",
    "QTs",
    "T2o",
    "T2s",
    "T3o",
    "T3s",
    "T4o",
    "T4s",
    "T5o",
    "T5s",
    "T6o",
    "T6s",
    "T7o",
    "T7s",
    "T8o",
    "T8s",
    "T9o",
    "T9s",
    "TT",
)

# Rank 字符到索引的映射（2=0, 3=1, ..., A=12）
_RANK_TO_INDEX: dict[str, int] = {
    "2": 0,
    "3": 1,
    "4": 2,
    "5": 3,
    "6": 4,
    "7": 5,
    "8": 6,
    "9": 7,
    "T": 8,
    "J": 9,
    "Q": 10,
    "K": 11,
    "A": 12,
}

# Suit 字符到索引的映射
_SUIT_TO_INDEX: dict[str, int] = {"c": 0, "d": 1, "h": 2, "s": 3}

# 索引到 Rank 字符
_INDEX_TO_RANK: str = "23456789TJQKA"

# 索引到 Suit 字符
_INDEX_TO_SUIT: str = "cdhs"

# 1326 组合的 52 索引对列表（预计算）
_COMBINATIONS_1326: tuple[tuple[int, int], ...] = tuple(combinations(range(52), 2))

# 用于快速计算 1326 索引的辅助数组
_HELPER_1326: tuple[int, ...] = tuple(
    reduce(lambda x, y: x + [x[-1] + y], list(range(51, 0, -1)), [0])
)


# ============================================================================
# 延迟初始化的映射表
# ============================================================================

_range_169_to_1326: tuple[tuple[int, ...], ...] | None = None
_range_1326_to_169: tuple[int, ...] | None = None
_hand_key_to_169_index: dict[str, int] | None = None


def _init_mappings() -> None:
    """初始化 169↔1326 映射表。"""
    global _range_169_to_1326, _range_1326_to_169, _hand_key_to_169_index

    if _range_169_to_1326 is not None:
        return

    # 构建手牌键到 169 索引的映射
    _hand_key_to_169_index = {key: i for i, key in enumerate(RANGE_169_ORDER)}

    # 构建 169 → 1326 映射
    range_169_to_1326_list: list[list[int]] = [[] for _ in range(RANGE_169_LENGTH)]
    range_1326_to_169_list: list[int] = [0] * RANGE_1326_LENGTH

    for combo_idx in range(RANGE_1326_LENGTH):
        card1_idx, card2_idx = _COMBINATIONS_1326[combo_idx]
        hand_key = _combo_index_to_hand_key(card1_idx, card2_idx)
        idx_169 = _hand_key_to_169_index[hand_key]
        range_169_to_1326_list[idx_169].append(combo_idx)
        range_1326_to_169_list[combo_idx] = idx_169

    _range_169_to_1326 = tuple(tuple(lst) for lst in range_169_to_1326_list)
    _range_1326_to_169 = tuple(range_1326_to_169_list)


def _combo_index_to_hand_key(card1_idx: int, card2_idx: int) -> str:
    """将两张牌的 52 索引转换为手牌键。

    Args:
        card1_idx: 第一张牌的 52 索引
        card2_idx: 第二张牌的 52 索引

    Returns:
        手牌键，如 "AKs", "AKo", "AA"（大牌在前）
    """
    rank1 = card1_idx // 4
    suit1 = card1_idx % 4
    rank2 = card2_idx // 4
    suit2 = card2_idx % 4

    # 确保 rank1 >= rank2（大牌在前，符合 GTOWizard 格式如 "32s"）
    if rank1 < rank2:
        rank1, rank2 = rank2, rank1
        suit1, suit2 = suit2, suit1

    r1_char = _INDEX_TO_RANK[rank1]
    r2_char = _INDEX_TO_RANK[rank2]

    if rank1 == rank2:
        return f"{r1_char}{r2_char}"
    elif suit1 == suit2:
        return f"{r1_char}{r2_char}s"
    else:
        return f"{r1_char}{r2_char}o"


# ============================================================================
# 公开 API
# ============================================================================


def get_range_169_to_1326() -> tuple[tuple[int, ...], ...]:
    """获取 169 索引到 1326 索引列表的映射。

    Returns:
        169 元素的 tuple，每个元素是该手牌对应的 1326 索引列表
    """
    _init_mappings()
    assert _range_169_to_1326 is not None
    return _range_169_to_1326


def get_range_1326_to_169() -> tuple[int, ...]:
    """获取 1326 索引到 169 索引的映射。

    Returns:
        1326 元素的 tuple，每个元素是对应的 169 索引
    """
    _init_mappings()
    assert _range_1326_to_169 is not None
    return _range_1326_to_169


def get_hand_key_to_169_index() -> dict[str, int]:
    """获取手牌键到 169 索引的映射。

    Returns:
        手牌键（如 "AKs"）到 169 索引的字典
    """
    _init_mappings()
    assert _hand_key_to_169_index is not None
    return _hand_key_to_169_index


def card_to_index52(rank: str, suit: str) -> int:
    """将牌面转换为 52 索引。

    索引布局：
        2c=0, 2d=1, 2h=2, 2s=3, 3c=4, ..., Ac=48, Ad=49, Ah=50, As=51

    Args:
        rank: 牌面大小，如 "A", "K", "2"
        suit: 花色，如 "c", "d", "h", "s"

    Returns:
        0-51 的索引
    """
    return _RANK_TO_INDEX[rank] * 4 + _SUIT_TO_INDEX[suit]


def index52_to_card(idx: int) -> tuple[str, str]:
    """将 52 索引转换为牌面。

    Args:
        idx: 0-51 的索引

    Returns:
        (rank, suit) 元组，如 ("A", "s")
    """
    return _INDEX_TO_RANK[idx // 4], _INDEX_TO_SUIT[idx % 4]


def combo_to_index1326(card1_idx: int, card2_idx: int) -> int:
    """将两张牌的 52 索引转换为 1326 组合索引。

    Args:
        card1_idx: 第一张牌的 52 索引
        card2_idx: 第二张牌的 52 索引

    Returns:
        0-1325 的组合索引
    """
    if card1_idx > card2_idx:
        card1_idx, card2_idx = card2_idx, card1_idx
    return _HELPER_1326[card1_idx] + card2_idx - card1_idx - 1


def index1326_to_combo(idx: int) -> tuple[int, int]:
    """将 1326 组合索引转换为两张牌的 52 索引。

    Args:
        idx: 0-1325 的组合索引

    Returns:
        (card1_idx, card2_idx) 元组，card1_idx < card2_idx
    """
    return _COMBINATIONS_1326[idx]


def combos_per_hand(hand_key: str) -> int:
    """获取手牌键对应的组合数。

    Args:
        hand_key: 手牌键，如 "AA", "AKs", "AKo"

    Returns:
        组合数：对子=6，同花=4，非同花=12
    """
    if len(hand_key) == 2:
        return 6  # 对子
    return 4 if hand_key.endswith("s") else 12
