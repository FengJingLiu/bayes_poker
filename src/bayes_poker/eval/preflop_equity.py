"""Preflop equity 矩阵解析与缓存模块。

从 PreFlopEquities.txt 解析 1326 combo 对战 equity,
聚合为 169x169 手牌组 equity 矩阵并保存为 .npy 文件。

文件格式: 每行 `Card1Card2:Card3Card4=equity`
    例: AcAd:AhKc=93.47

169x169 矩阵:
    matrix[i][j] = 手牌组 i 对战手牌组 j 的平均 equity (0.0 ~ 1.0)
    索引顺序遵循 RANGE_169_ORDER (从 "22" 到 "TT")

用法:
    # 一次性生成并保存
    python -m bayes_poker.eval.preflop_equity \\
        --input /path/to/PreFlopEquities.txt \\
        --output data/eval/preflop_equity_169x169.npy

    # 代码中加载使用
    from bayes_poker.eval.preflop_equity import load_equity_matrix
    matrix = load_equity_matrix("data/eval/preflop_equity_169x169.npy")
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from bayes_poker.strategy.range.mappings import (
    RANGE_169_ORDER,
    _INDEX_TO_RANK,
    _INDEX_TO_SUIT,
    get_hand_key_to_169_index,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path("data/eval/preflop_equity_169x169.npy")

# ============================================================================
# 预计算查询表
# ============================================================================

# card string ("Ac", "Kd", ...) -> 52 index
_CARD_STR_TO_52: dict[str, int] = {}
for _r_idx, _r_char in enumerate(_INDEX_TO_RANK):
    for _s_idx, _s_char in enumerate(_INDEX_TO_SUIT):
        _CARD_STR_TO_52[f"{_r_char}{_s_char}"] = _r_idx * 4 + _s_idx


def _build_combo52_to_169() -> np.ndarray:
    """构建 (52, 52) -> 169 索引查询表。

    Returns:
        shape (52, 52) int16 数组, table[c1][c2] = 169 索引。
        同一张牌 (c1==c2) 位置为 -1。
    """
    hand_key_to_169 = get_hand_key_to_169_index()
    table = np.full((52, 52), -1, dtype=np.int16)

    for c1 in range(52):
        r1 = c1 // 4
        s1 = c1 % 4
        for c2 in range(52):
            if c1 == c2:
                continue
            r2 = c2 // 4
            s2 = c2 % 4

            # 确保大牌在前
            rr1, rr2, ss1, ss2 = r1, r2, s1, s2
            if rr1 < rr2:
                rr1, rr2 = rr2, rr1
                ss1, ss2 = ss2, ss1

            r1_char = _INDEX_TO_RANK[rr1]
            r2_char = _INDEX_TO_RANK[rr2]

            if rr1 == rr2:
                hand_key = f"{r1_char}{r2_char}"
            elif ss1 == ss2:
                hand_key = f"{r1_char}{r2_char}s"
            else:
                hand_key = f"{r1_char}{r2_char}o"

            table[c1, c2] = hand_key_to_169[hand_key]

    return table


# 延迟初始化
_combo52_to_169: np.ndarray | None = None


def _get_combo52_to_169() -> np.ndarray:
    """获取 (52,52)->169 查询表 (延迟初始化)。"""
    global _combo52_to_169
    if _combo52_to_169 is None:
        _combo52_to_169 = _build_combo52_to_169()
    return _combo52_to_169


# ============================================================================
# 核心功能
# ============================================================================


def build_equity_matrix_169(filepath: str | Path) -> np.ndarray:
    """解析 PreFlopEquities.txt 并生成 169x169 equity 矩阵。

    对于每一对 169 手牌组 (i, j), 矩阵值为所有不共享牌的
    具体 combo 对战 equity 的加权平均值。

    Args:
        filepath: PreFlopEquities.txt 文件路径。

    Returns:
        169x169 float64 矩阵, matrix[i][j] 表示手牌组 i 对战
        手牌组 j 的平均 equity, 范围 0.0 ~ 1.0。
        matrix[i][j] + matrix[j][i] ≈ 1.0。
    """
    filepath = Path(filepath)
    if not filepath.exists():
        msg = f"文件不存在: {filepath}"
        raise FileNotFoundError(msg)

    lookup = _get_combo52_to_169()
    card_lut = _CARD_STR_TO_52

    # 累加器
    eq_sum = np.zeros((169, 169), dtype=np.float64)
    eq_count = np.zeros((169, 169), dtype=np.int32)

    line_count = 0
    error_count = 0

    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            # 格式: XxXx:XxXx=DD.DD (固定位置解析)
            # line[0:2] = card1 of hand1
            # line[2:4] = card2 of hand1
            # line[4]   = ':'
            # line[5:7] = card1 of hand2
            # line[7:9] = card2 of hand2
            # line[9]   = '='
            # line[10:]  = equity
            try:
                c1_h1 = card_lut[line[0:2]]
                c2_h1 = card_lut[line[2:4]]
                c1_h2 = card_lut[line[5:7]]
                c2_h2 = card_lut[line[7:9]]
                equity = float(line[10:].rstrip()) / 100.0

                idx_i = lookup[c1_h1, c2_h1]
                idx_j = lookup[c1_h2, c2_h2]

                eq_sum[idx_i, idx_j] += equity
                eq_count[idx_i, idx_j] += 1

            except (KeyError, ValueError, IndexError):
                error_count += 1
                if error_count <= 5:
                    LOGGER.warning("解析失败 (行 %d): %s", line_count + 1, line.rstrip())

            line_count += 1
            if line_count % 500_000 == 0:
                LOGGER.info("已处理 %d 行...", line_count)

    LOGGER.info(
        "解析完成: %d 行, %d 错误, %d 非零矩阵元素",
        line_count,
        error_count,
        int(np.count_nonzero(eq_count)),
    )

    if error_count > 0:
        LOGGER.warning("共 %d 行解析失败", error_count)

    # 计算平均值, 避免除零
    with np.errstate(divide="ignore", invalid="ignore"):
        matrix = np.where(eq_count > 0, eq_sum / eq_count, 0.0)

    return matrix.astype(np.float32)


def save_equity_matrix(
    matrix: np.ndarray,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """保存 equity 矩阵到 .npy 文件。

    Args:
        matrix: 169x169 equity 矩阵。
        output_path: 输出文件路径。

    Returns:
        实际保存的文件路径。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, matrix)
    LOGGER.info("矩阵已保存: %s (shape=%s, dtype=%s)", output_path, matrix.shape, matrix.dtype)
    return output_path


def load_equity_matrix(filepath: str | Path = DEFAULT_OUTPUT_PATH) -> np.ndarray:
    """加载已缓存的 169x169 equity 矩阵。

    Args:
        filepath: .npy 文件路径。

    Returns:
        169x169 float32 矩阵。

    Raises:
        FileNotFoundError: 文件不存在。
    """
    filepath = Path(filepath)
    if not filepath.exists():
        msg = f"Equity 矩阵文件不存在: {filepath}。请先运行 python -m bayes_poker.eval.preflop_equity 生成。"
        raise FileNotFoundError(msg)

    matrix = np.load(filepath)
    if matrix.shape != (169, 169):
        msg = f"矩阵形状不正确: 期望 (169, 169), 实际 {matrix.shape}"
        raise ValueError(msg)

    LOGGER.debug("已加载 equity 矩阵: %s", filepath)
    return matrix


def get_equity(
    matrix: np.ndarray,
    hand_key_hero: str,
    hand_key_villain: str,
) -> float:
    """查询两个手牌组之间的平均 equity。

    Args:
        matrix: 169x169 equity 矩阵。
        hand_key_hero: Hero 手牌键, 如 "AKs", "QQ"。
        hand_key_villain: Villain 手牌键, 如 "JTs", "AA"。

    Returns:
        Hero 对 Villain 的平均 equity (0.0 ~ 1.0)。
    """
    idx_map = get_hand_key_to_169_index()
    i = idx_map[hand_key_hero]
    j = idx_map[hand_key_villain]
    return float(matrix[i, j])


def get_equity_vs_range(
    matrix: np.ndarray,
    hand_key: str,
    range_weights: np.ndarray,
) -> float:
    """计算一个手牌组对抗给定范围的加权平均 equity。

    Args:
        matrix: 169x169 equity 矩阵。
        hand_key: 手牌键, 如 "AKs"。
        range_weights: 长度 169 的权重向量 (对手范围频率)。

    Returns:
        加权平均 equity (0.0 ~ 1.0)。
    """
    idx_map = get_hand_key_to_169_index()
    i = idx_map[hand_key]
    row = matrix[i]
    total_weight = np.sum(range_weights)
    if total_weight == 0.0:
        return 0.0
    return float(np.dot(row, range_weights) / total_weight)


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    """命令行入口: 解析 equity 文件并保存矩阵。"""
    parser = argparse.ArgumentParser(
        description="解析 PreFlopEquities.txt, 生成 169x169 equity 矩阵",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="PreFlopEquities.txt 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"输出 .npy 文件路径 (默认: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    LOGGER.info("开始解析: %s", args.input)
    matrix = build_equity_matrix_169(args.input)

    # 基础校验
    _validate_matrix(matrix)

    output = save_equity_matrix(matrix, args.output)
    LOGGER.info("完成! 矩阵已保存至 %s", output)


def _validate_matrix(matrix: np.ndarray) -> None:
    """对生成的矩阵进行基础正确性校验。"""
    idx_map = get_hand_key_to_169_index()

    # 1. 检查 AA vs AA 应为 0.5
    aa_idx = idx_map["AA"]
    aa_vs_aa = matrix[aa_idx, aa_idx]
    LOGGER.info("AA vs AA = %.4f (期望 ≈ 0.5000)", aa_vs_aa)

    # 2. 检查对称性: matrix[i][j] + matrix[j][i] ≈ 1.0
    symmetry_err = matrix + matrix.T
    # 排除全零位置 (不存在的对战)
    nonzero_mask = (matrix > 0) & (matrix.T > 0)
    if np.any(nonzero_mask):
        max_sym_err = np.max(np.abs(symmetry_err[nonzero_mask] - 1.0))
        mean_sym_err = np.mean(np.abs(symmetry_err[nonzero_mask] - 1.0))
        LOGGER.info(
            "对称性检查: max|eq[i][j]+eq[j][i]-1.0| = %.6f, mean = %.6f",
            max_sym_err,
            mean_sym_err,
        )

    # 3. 检查覆盖率
    filled = np.count_nonzero(matrix)
    total = 169 * 169
    LOGGER.info("矩阵覆盖率: %d / %d (%.1f%%)", filled, total, 100 * filled / total)

    # 4. 抽查几个已知 equity
    checks = [
        ("AA", "KK", 0.80, 0.84),  # AA vs KK ≈ 82%
        ("AA", "72o", 0.86, 0.90),  # AA vs 72o ≈ 88%
        ("AKs", "QQ", 0.44, 0.48),  # AKs vs QQ ≈ 46%
    ]
    for hero, villain, lo, hi in checks:
        eq = matrix[idx_map[hero], idx_map[villain]]
        status = "OK" if lo <= eq <= hi else "WARN"
        LOGGER.info("  %s vs %s = %.4f [%s] (期望 %.2f~%.2f)", hero, villain, eq, status, lo, hi)


if __name__ == "__main__":
    main()
