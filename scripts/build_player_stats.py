#!/usr/bin/env python3
"""从 PHHS 文件构建 PlayerStats 并保存到 SQLite 数据库（Rust 加速版）。

本脚本使用 Rust 实现的批处理函数，相比 Python 版本有显著性能提升。

用法：
    # 批量处理目录
    uv run python scripts/build_player_stats.py data/outputs/ -o data/database/player_stats.db

    # 指定每批次加载的文件数量（控制内存占用）
    uv run python scripts/build_player_stats.py data/outputs/ -o data/database/player_stats.db -b 100

    # 查看统计信息
    uv run python scripts/build_player_stats.py --stats data/database/player_stats.db

    # 清空数据库后重新构建
    uv run python scripts/build_player_stats.py data/outputs/ -o data/database/player_stats.db --clear -b 100

环境变量：
    BAYES_POKER_MAX_FILES_IN_MEMORY: 默认的每批次加载文件数量
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# 确保 src 目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bayes_poker.player_metrics.rust_api import batch_process_phhs
from bayes_poker.storage import PlayerStatsRepository

LOGGER = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    """配置日志。

    Args:
        verbose: 是否启用详细日志输出。
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_default_batch_size() -> int | None:
    """获取默认的批处理大小。

    Returns:
        从环境变量读取的批处理大小，如果未设置则返回 None。
    """
    env_value = os.environ.get("BAYES_POKER_MAX_FILES_IN_MEMORY")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            LOGGER.warning(
                "无效的 BAYES_POKER_MAX_FILES_IN_MEMORY 值: %s，忽略",
                env_value,
            )
    return None


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="从 PHHS 文件构建 PlayerStats 并保存到 SQLite（Rust 加速版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data/outputs/ -o data/player_stats.db
  %(prog)s data/outputs/ -o data/player_stats.db -b 100
  %(prog)s --stats data/player_stats.db
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="PHHS 文件目录",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="SQLite 数据库路径",
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=None,
        help="每批次加载的文件数量（默认从环境变量读取或一次性加载全部）",
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
            if stats.get("processed_hands_legacy_count", 0) > 0:
                print(f"legacy 手牌数: {stats['processed_hands_legacy_count']}")
        return

    # 验证参数
    if not args.input:
        parser.error("需要指定输入目录")
    if not args.output:
        parser.error("需要指定输出数据库路径 (-o)")

    input_path = args.input
    if not input_path.is_dir():
        LOGGER.error("输入路径必须是目录: %s", input_path)
        sys.exit(1)

    # 清空数据库（如果请求）
    if args.clear:
        with PlayerStatsRepository(args.output) as repo:
            repo.clear()
        LOGGER.info("已清空数据库")

    # 确定批处理大小
    batch_size = args.batch_size or get_default_batch_size()

    LOGGER.info("开始处理 PHHS 文件...")
    LOGGER.info("  输入目录: %s", input_path)
    LOGGER.info("  数据库: %s", args.output)
    if batch_size:
        LOGGER.info("  批处理大小: %d 文件/批", batch_size)
    else:
        LOGGER.info("  批处理大小: 一次性加载全部")

    # 调用 Rust 批处理函数
    try:
        new_hands, players_count, skipped_hands = batch_process_phhs(
            phhs_dir=input_path,
            db_path=args.output,
            max_files_in_memory=batch_size,
        )
    except Exception as e:
        LOGGER.error("批处理失败: %s", e)
        sys.exit(1)

    # 获取最终统计
    with PlayerStatsRepository(args.output) as repo:
        stats = repo.get_stats()

    # 打印结果
    print()
    print("=" * 50)
    print("处理完成")
    print(f"  新增手牌: {new_hands}")
    print(f"  跳过重复: {skipped_hands}")
    print(f"  数据库玩家数: {players_count}")
    print(f"  数据库总手牌数: {stats['processed_hands_count']}")
    if stats.get("processed_hands_legacy_count", 0) > 0:
        print(f"  legacy 手牌数: {stats['processed_hands_legacy_count']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
