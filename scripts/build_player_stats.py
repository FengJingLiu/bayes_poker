#!/usr/bin/env python3
"""从 PHHS 文件构建 PlayerStats 并保存到 SQLite 数据库。

用法：
    # 处理单个文件
    uv run python scripts/build_player_stats.py data/outputs/file.phhs -o data/player_stats.db

    # 批量处理目录
    uv run python scripts/build_player_stats.py data/outputs/ -o data/player_stats.db

    # 使用多进程加速
    uv run python scripts/build_player_stats.py data/outputs/ -o data/player_stats.db -w 4

    # 查看统计信息
    uv run python scripts/build_player_stats.py --stats data/player_stats.db
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# 确保 src 目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pokerkit import HandHistory

from bayes_poker.hand_history.parse_gg_poker import parse_value_in_cents
from bayes_poker.player_metrics.builder import build_player_stats_from_hands
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.serialization import compute_hand_hash
from bayes_poker.storage import PlayerStatsRepository

LOGGER = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """配置日志。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def detect_table_type(num_players: int) -> TableType:
    """根据玩家数量检测桌型。

    Args:
        num_players: 手牌中的玩家数量。

    Returns:
        TableType.HEADS_UP (2人) 或 TableType.SIX_MAX (其他)。
    """
    return TableType.HEADS_UP if num_players == 2 else TableType.SIX_MAX


def load_phhs_file(path: Path) -> list[HandHistory]:
    """加载 PHHS 文件。

    Args:
        path: PHHS 文件路径。

    Returns:
        HandHistory 列表。
    """
    with path.open("rb") as f:
        return list(HandHistory.load_all(f, parse_value=parse_value_in_cents))


def find_phhs_files(input_path: Path) -> list[Path]:
    """查找所有 PHHS 文件。

    Args:
        input_path: 文件或目录路径。

    Returns:
        PHHS 文件路径列表。
    """
    if input_path.is_file():
        return [input_path]
    elif input_path.is_dir():
        return sorted(input_path.glob("*.phhs"))
    else:
        return []


@dataclass
class ProcessResult:
    """单个文件处理结果。"""

    file_path: Path
    total_hands: int
    new_hands: int
    skipped_hands: int
    players_updated: int
    error: str | None = None


def process_single_file(
    phhs_path: Path,
    db_path: Path,
) -> ProcessResult:
    """处理单个 PHHS 文件（用于多进程）。

    Args:
        phhs_path: PHHS 文件路径。
        db_path: 数据库路径。

    Returns:
        ProcessResult 处理结果。
    """
    try:
        hands = load_phhs_file(phhs_path)
        total_hands = len(hands)

        if total_hands == 0:
            return ProcessResult(
                file_path=phhs_path,
                total_hands=0,
                new_hands=0,
                skipped_hands=0,
                players_updated=0,
            )

        with PlayerStatsRepository(db_path) as repo:
            hands_with_hash: list[tuple[HandHistory, str]] = [
                (hh, compute_hand_hash(hh)) for hh in hands
            ]
            processed_hashes = repo.get_processed_hand_hashes([h for _, h in hands_with_hash])

            new_hands_with_hash = [
                (hh, h) for hh, h in hands_with_hash if h not in processed_hashes
            ]
            new_hands_list = [hh for hh, _ in new_hands_with_hash]
            skipped = total_hands - len(new_hands_list)

            if not new_hands_list:
                return ProcessResult(
                    file_path=phhs_path,
                    total_hands=total_hands,
                    new_hands=0,
                    skipped_hands=skipped,
                    players_updated=0,
                )

            # 按桌型分组处理
            hu_hands: list[HandHistory] = []
            six_max_hands: list[HandHistory] = []

            for hh in new_hands_list:
                num_players = len(hh.players) if hh.players else 0
                if num_players == 2:
                    hu_hands.append(hh)
                elif num_players > 0:
                    six_max_hands.append(hh)

            players_updated = 0

            # 处理 Heads-Up 手牌
            if hu_hands:
                hu_stats = build_player_stats_from_hands(hu_hands, TableType.HEADS_UP)
                repo.upsert_batch_with_merge(hu_stats)
                players_updated += len(hu_stats)

            # 处理 6-max 手牌
            if six_max_hands:
                six_max_stats = build_player_stats_from_hands(six_max_hands, TableType.SIX_MAX)
                repo.upsert_batch_with_merge(six_max_stats)
                players_updated += len(six_max_stats)

            repo.mark_hands_processed([h for _, h in new_hands_with_hash])

            return ProcessResult(
                file_path=phhs_path,
                total_hands=total_hands,
                new_hands=len(new_hands_list),
                skipped_hands=skipped,
                players_updated=players_updated,
            )

    except Exception as e:
        return ProcessResult(
            file_path=phhs_path,
            total_hands=0,
            new_hands=0,
            skipped_hands=0,
            players_updated=0,
            error=str(e),
        )


def process_files_sequential(
    phhs_files: list[Path],
    db_path: Path,
) -> Iterator[ProcessResult]:
    """顺序处理多个文件。"""
    for phhs_path in phhs_files:
        yield process_single_file(phhs_path, db_path)


def process_files_parallel(
    phhs_files: list[Path],
    db_path: Path,
    workers: int,
) -> Iterator[ProcessResult]:
    """并行处理多个文件。"""
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_file, path, db_path): path
            for path in phhs_files
        }
        for future in as_completed(futures):
            yield future.result()


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="从 PHHS 文件构建 PlayerStats 并保存到 SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data/outputs/ -o data/player_stats.db
  %(prog)s data/outputs/ -o data/player_stats.db -w 4
  %(prog)s --stats data/player_stats.db
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="PHHS 文件或目录",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="SQLite 数据库路径",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=1,
        help="并行进程数 (默认: 1)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细日志输出",
    )
    parser.add_argument(
        "--stats",
        type=Path,
        metavar="DB_PATH",
        help="查看数据库统计信息",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清空数据库后重新构建",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)

    # 统计信息模式
    if args.stats:
        with PlayerStatsRepository(args.stats) as repo:
            stats = repo.get_stats()
            print(f"数据库: {args.stats}")
            print(f"玩家数: {stats['player_count']}")
            print(f"已处理手牌数: {stats['processed_hands_count']}")
            if stats.get('processed_hands_legacy_count', 0) > 0:
                print(f"legacy 手牌数: {stats['processed_hands_legacy_count']}")
        return

    # 验证参数
    if not args.input:
        parser.error("需要指定输入文件或目录")
    if not args.output:
        parser.error("需要指定输出数据库路径 (-o)")

    # 查找文件
    phhs_files = find_phhs_files(args.input)
    if not phhs_files:
        LOGGER.error("未找到 PHHS 文件: %s", args.input)
        sys.exit(1)

    LOGGER.info("找到 %d 个 PHHS 文件", len(phhs_files))

    # 清空数据库（如果请求）
    if args.clear:
        with PlayerStatsRepository(args.output) as repo:
            repo.clear()
        LOGGER.info("已清空数据库")

    # 处理文件
    total_new = 0
    total_skipped = 0
    total_errors = 0

    if args.workers > 1:
        results = process_files_parallel(phhs_files, args.output, args.workers)
    else:
        results = process_files_sequential(phhs_files, args.output)

    for result in results:
        if result.error:
            LOGGER.error("处理失败: %s - %s", result.file_path.name, result.error)
            total_errors += 1
        else:
            LOGGER.info(
                "处理完成: %s | 总计: %d | 新增: %d | 跳过: %d",
                result.file_path.name,
                result.total_hands,
                result.new_hands,
                result.skipped_hands,
            )
            total_new += result.new_hands
            total_skipped += result.skipped_hands

    # 最终统计
    with PlayerStatsRepository(args.output) as repo:
        stats = repo.get_stats()

    print()
    print("=" * 50)
    print(f"处理完成")
    print(f"  文件数: {len(phhs_files)}")
    print(f"  新增手牌: {total_new}")
    print(f"  跳过重复: {total_skipped}")
    print(f"  错误数: {total_errors}")
    print(f"  数据库玩家数: {stats['player_count']}")
    print(f"  数据库手牌数: {stats['processed_hands_count']}")
    if stats.get('processed_hands_legacy_count', 0) > 0:
        print(f"  legacy 手牌数: {stats['processed_hands_legacy_count']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
