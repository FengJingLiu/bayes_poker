#!/usr/bin/env python3
"""
批量解析 GGPoker 手牌历史文件。

本脚本支持：
- 单文件或文件夹批量解析
- 可选多进程并行处理
- 自定义输出目录

使用示例:
    # 解析单个文件
    python batch_parse_handhistory.py input.txt -o output/

    # 解析整个文件夹
    python batch_parse_handhistory.py data/handhistory/ -o output/

    # 使用 4 个进程并行解析
    python batch_parse_handhistory.py data/handhistory/ -o output/ -w 4
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import cpu_count
from pathlib import Path
from typing import TYPE_CHECKING

# 将 src 目录添加到模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bayes_poker.hand_history.parse_gg_poker import (
    FAILED_HANDS_DIR,
    FAILED_HANDS_LOG_PATH,
    configure_logging,
    parse_hand_histories,
    save_hand_histories,
)

if TYPE_CHECKING:
    from pokerkit.notation import HandHistory

# 日志配置
LOGGER = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """
    单个文件的解析结果。

    Attributes:
        file_path: 源文件路径。
        success_count: 成功解析的手牌数量。
        total_count: 总手牌数量。
        output_path: 输出文件路径。
        error: 解析过程中的错误信息（如有）。
    """

    file_path: Path
    success_count: int
    total_count: int
    output_path: Path | None
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


def get_input_files(input_path: Path, recursive: bool = False) -> list[Path]:
    """
    获取待处理的输入文件列表。

    Args:
        input_path: 输入路径，可以是文件或目录。
        recursive: 是否递归搜索子目录。

    Returns:
        文件路径列表。

    Raises:
        FileNotFoundError: 如果输入路径不存在。
        ValueError: 如果输入路径既非文件也非目录。
    """
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在: {input_path}")

    if input_path.is_file():
        return [input_path]

    if input_path.is_dir():
        pattern = "**/*.txt" if recursive else "*.txt"
        return sorted(input_path.glob(pattern))

    raise ValueError(f"无效的输入路径: {input_path}")


def generate_output_path(
    input_file: Path,
    output_dir: Path,
    input_base: Path | None = None,
) -> Path:
    """
    生成输出文件路径。

    Args:
        input_file: 输入文件路径。
        output_dir: 输出目录。
        input_base: 输入基础目录（用于保持相对路径结构）。

    Returns:
        输出文件路径（.phhs 格式）。
    """
    if input_base and input_base.is_dir():
        relative = input_file.relative_to(input_base)
        output_path = output_dir / relative.with_suffix(".phhs")
    else:
        output_path = output_dir / input_file.with_suffix(".phhs").name

    return output_path


def is_already_parsed(output_path: Path) -> tuple[bool, str | None]:
    """
    判断输出是否已存在（用于跳过已解析文件）。

    规则：
    - 输出文件存在且非空：视为已解析
    - 输出文件不存在或为空：视为未解析

    Returns:
        (是否已解析, 跳过原因)
    """
    try:
        if output_path.exists():
            size = output_path.stat().st_size
            if size > 0:
                return True, f"输出已存在({size} bytes)"
            return False, "输出文件为空，重新解析"
    except OSError as e:
        return False, f"检查输出失败({e})，重新解析"

    return False, None


def parse_single_file(
    input_file: Path,
    output_path: Path,
) -> ParseResult:
    """
    解析单个手牌历史文件。

    Args:
        input_file: 输入文件路径。
        output_path: 输出文件路径。

    Returns:
        解析结果对象。
    """
    try:
        # 配置当前进程的日志
        configure_logging(FAILED_HANDS_LOG_PATH)

        hand_histories, total = parse_hand_histories(input_file)

        if hand_histories:
            save_hand_histories(output_path, hand_histories)

        return ParseResult(
            file_path=input_file,
            success_count=len(hand_histories),
            total_count=total,
            output_path=output_path if hand_histories else None,
        )

    except Exception as e:
        LOGGER.exception("解析文件失败: %s", input_file)
        return ParseResult(
            file_path=input_file,
            success_count=0,
            total_count=0,
            output_path=None,
            error=str(e),
        )


def parse_files_sequential(
    files: list[Path],
    output_dir: Path,
    input_base: Path | None = None,
) -> list[ParseResult]:
    """
    顺序解析多个文件。

    Args:
        files: 待解析的文件列表。
        output_dir: 输出目录。
        input_base: 输入基础目录。

    Returns:
        解析结果列表。
    """
    results: list[ParseResult] = []

    for i, input_file in enumerate(files, 1):
        output_path = generate_output_path(input_file, output_dir, input_base)
        already_parsed, reason = is_already_parsed(output_path)
        if already_parsed:
            LOGGER.info(
                "跳过 [%d/%d]: %s (%s)",
                i,
                len(files),
                input_file.name,
                reason or "已解析",
            )
            results.append(
                ParseResult(
                    file_path=input_file,
                    success_count=0,
                    total_count=0,
                    output_path=output_path,
                    skipped=True,
                    skip_reason=reason,
                )
            )
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)

        LOGGER.info("解析 [%d/%d]: %s", i, len(files), input_file.name)
        result = parse_single_file(input_file, output_path)
        results.append(result)

        LOGGER.info(
            "完成 [%d/%d]: %d/%d 手成功",
            i,
            len(files),
            result.success_count,
            result.total_count,
        )

    return results


def parse_files_parallel(
    files: list[Path],
    output_dir: Path,
    input_base: Path | None = None,
    max_workers: int | None = None,
) -> list[ParseResult]:
    """
    并行解析多个文件。

    Args:
        files: 待解析的文件列表。
        output_dir: 输出目录。
        input_base: 输入基础目录。
        max_workers: 最大工作进程数，默认为 CPU 核心数。

    Returns:
        解析结果列表。
    """
    if max_workers is None:
        max_workers = cpu_count()

    results: list[ParseResult] = []

    # 预先创建输出目录并准备任务
    tasks: list[tuple[Path, Path]] = []
    skipped_count = 0
    for input_file in files:
        output_path = generate_output_path(input_file, output_dir, input_base)
        already_parsed, reason = is_already_parsed(output_path)
        if already_parsed:
            skipped_count += 1
            LOGGER.info("跳过: %s (%s)", input_file.name, reason or "已解析")
            results.append(
                ParseResult(
                    file_path=input_file,
                    success_count=0,
                    total_count=0,
                    output_path=output_path,
                    skipped=True,
                    skip_reason=reason,
                )
            )
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tasks.append((input_file, output_path))

    if not tasks:
        LOGGER.info("所有文件均已解析（跳过 %d 个）", skipped_count)
        return results

    LOGGER.info("启动 %d 个工作进程...", max_workers)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(parse_single_file, input_file, output_path): input_file
            for input_file, output_path in tasks
        }

        for i, future in enumerate(as_completed(future_to_file), 1):
            input_file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
                LOGGER.info(
                    "完成 [%d/%d]: %s - %d/%d 手成功",
                    i,
                    len(tasks),
                    input_file.name,
                    result.success_count,
                    result.total_count,
                )
            except Exception as e:
                LOGGER.exception("进程执行失败: %s", input_file)
                results.append(
                    ParseResult(
                        file_path=input_file,
                        success_count=0,
                        total_count=0,
                        output_path=None,
                        error=str(e),
                    )
                )

    return results


def print_summary(results: list[ParseResult], elapsed: float) -> None:
    """
    打印解析摘要。

    Args:
        results: 解析结果列表。
        elapsed: 总耗时（秒）。
    """
    total_files = len(results)
    skipped_files = sum(1 for r in results if r.skipped)
    success_files = sum(
        1 for r in results if (not r.skipped) and r.error is None and r.success_count > 0
    )
    failed_files = sum(1 for r in results if (not r.skipped) and r.error is not None)
    total_hands = sum(r.total_count for r in results)
    success_hands = sum(r.success_count for r in results)

    print("\n" + "=" * 60)
    print("                    解析摘要")
    print("=" * 60)
    print(f"  文件总数:     {total_files}")
    print(f"  跳过文件:     {skipped_files}")
    print(f"  成功文件:     {success_files}")
    print(f"  失败文件:     {failed_files}")
    print("-" * 60)
    print(f"  手牌总数:     {total_hands}")
    print(f"  成功解析:     {success_hands}")
    print(f"  解析失败:     {total_hands - success_hands}")
    print(f"  成功率:       {success_hands / total_hands * 100:.2f}%" if total_hands else "  成功率:       N/A")
    print("-" * 60)
    print(f"  总耗时:       {elapsed:.2f} 秒")
    print(f"  平均速度:     {total_hands / elapsed:.0f} 手/秒" if elapsed > 0 else "")
    print("=" * 60)

    # 显示失败文件
    failed = [r for r in results if (not r.skipped) and r.error is not None]
    if failed:
        print("\n失败文件列表:")
        for r in failed:
            print(f"  - {r.file_path}: {r.error}")


def setup_logging(verbose: bool = False) -> None:
    """
    配置根日志。

    Args:
        verbose: 是否启用详细日志输出。
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。

    Returns:
        解析后的命令行参数。
    """
    parser = argparse.ArgumentParser(
        description="批量解析 GGPoker 手牌历史文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 解析单个文件
  python batch_parse_handhistory.py input.txt -o output/

  # 解析整个文件夹
  python batch_parse_handhistory.py data/handhistory/ -o output/

  # 使用 4 个进程并行解析
  python batch_parse_handhistory.py data/handhistory/ -o output/ -w 4

  # 递归搜索子目录
  python batch_parse_handhistory.py data/handhistory/ -o output/ -r
        """,
    )

    parser.add_argument(
        "input",
        type=Path,
        help="输入文件或目录路径",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/outputs"),
        help="输出目录路径 (默认: data/outputs)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=1,
        help="工作进程数，大于 1 时启用多进程 (默认: 1)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="递归搜索子目录中的文件",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="启用详细日志输出",
    )

    return parser.parse_args()


def main() -> int:
    """
    主入口函数。

    Returns:
        退出状态码，0 表示成功，1 表示有错误。
    """
    args = parse_args()
    setup_logging(args.verbose)

    try:
        files = get_input_files(args.input, args.recursive)
    except (FileNotFoundError, ValueError) as e:
        LOGGER.error(str(e))
        return 1

    if not files:
        LOGGER.warning("未找到任何 .txt 文件")
        return 0

    LOGGER.info("找到 %d 个文件待处理", len(files))

    # 确定输入基础目录
    input_base = args.input if args.input.is_dir() else None

    # 确保输出目录存在
    args.output.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # 根据 workers 参数选择顺序或并行模式
    if args.workers > 1:
        LOGGER.info("使用多进程模式 (workers=%d)", args.workers)
        results = parse_files_parallel(
            files, args.output, input_base, args.workers
        )
    else:
        LOGGER.info("使用顺序模式")
        results = parse_files_sequential(files, args.output, input_base)

    elapsed = time.time() - start_time
    print_summary(results, elapsed)

    # 如果有任何错误，返回非零状态码
    has_errors = any(r.error is not None for r in results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
