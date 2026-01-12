#!/usr/bin/env python3
"""批量解析 GGPoker 手牌历史文件。"""

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bayes_poker.hand_history.parse_gg_poker import (
    FAILED_HANDS_DIR,
    FAILED_HANDS_LOG_PATH,
    configure_logging,
    parse_hand_histories,
    save_hand_histories,
)
from bayes_poker.storage.converter import HandHistoryConverter
from bayes_poker.storage.repository import HandRepository

if TYPE_CHECKING:
    from pokerkit.notation import HandHistory

LOGGER = logging.getLogger(__name__)


@dataclass
class ParseResult:
    file_path: Path
    success_count: int
    total_count: int
    output_path: Path | None
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


@dataclass
class ConvertResult:
    file_path: Path
    records: list
    total_count: int
    error: str | None = None


def get_input_files(input_path: Path, recursive: bool = False) -> list[Path]:
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
    if input_base and input_base.is_dir():
        relative = input_file.relative_to(input_base)
        output_path = output_dir / relative.with_suffix(".phhs")
    else:
        output_path = output_dir / input_file.with_suffix(".phhs").name

    return output_path


def is_already_parsed(output_path: Path) -> tuple[bool, str | None]:
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
    try:
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


def parse_and_convert_file(input_file: Path) -> ConvertResult:
    try:
        configure_logging(FAILED_HANDS_LOG_PATH)
        hand_histories, total = parse_hand_histories(input_file)

        if not hand_histories:
            return ConvertResult(
                file_path=input_file,
                records=[],
                total_count=total,
            )

        converter = HandHistoryConverter(None)  # type: ignore
        records = []
        for hh in hand_histories:
            record = converter.convert(hh, source=str(input_file))
            if record:
                records.append(record)

        return ConvertResult(
            file_path=input_file,
            records=records,
            total_count=total,
        )

    except Exception as e:
        return ConvertResult(
            file_path=input_file,
            records=[],
            total_count=0,
            error=str(e),
        )


def parse_single_file_to_sqlite(
    input_file: Path,
    db_path: Path,
) -> ParseResult:
    try:
        configure_logging(FAILED_HANDS_LOG_PATH)

        hand_histories, total = parse_hand_histories(input_file)

        if not hand_histories:
            return ParseResult(
                file_path=input_file,
                success_count=0,
                total_count=total,
                output_path=None,
            )

        with HandRepository(db_path) as repo:
            converter = HandHistoryConverter(repo)
            success, failed = converter.batch_convert_and_save(
                hand_histories,
                source=str(input_file),
            )

        return ParseResult(
            file_path=input_file,
            success_count=success,
            total_count=total,
            output_path=db_path,
        )

    except Exception as e:
        LOGGER.exception("解析文件到 SQLite 失败: %s", input_file)
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
    if max_workers is None:
        max_workers = cpu_count()

    results: list[ParseResult] = []

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


def parse_files_to_sqlite_parallel(
    files: list[Path],
    db_path: Path,
    max_workers: int | None = None,
    batch_size: int = 5000,
) -> list[ParseResult]:
    if max_workers is None:
        max_workers = min(cpu_count(), 8)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("启动 %d 个解析进程...", max_workers)

    results: list[ParseResult] = []
    all_records: list = []
    total_parsed = 0
    total_files = len(files)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(parse_and_convert_file, f): f for f in files}

        for i, future in enumerate(as_completed(future_to_file), 1):
            input_file = future_to_file[future]
            try:
                conv_result = future.result()
                all_records.extend(conv_result.records)
                total_parsed += conv_result.total_count

                results.append(
                    ParseResult(
                        file_path=input_file,
                        success_count=len(conv_result.records),
                        total_count=conv_result.total_count,
                        output_path=db_path,
                        error=conv_result.error,
                    )
                )

                if i % 50 == 0 or i == total_files:
                    LOGGER.info(
                        "解析进度 [%d/%d]: 累计 %d 条记录",
                        i,
                        total_files,
                        len(all_records),
                    )

            except Exception as e:
                LOGGER.exception("解析进程失败: %s", input_file)
                results.append(
                    ParseResult(
                        file_path=input_file,
                        success_count=0,
                        total_count=0,
                        output_path=None,
                        error=str(e),
                    )
                )

    LOGGER.info("解析完成，共 %d 条记录，开始批量写入...", len(all_records))

    if all_records:

        def progress_cb(current: int, total: int, success: int, dups: int) -> None:
            LOGGER.info(
                "写入进度 [%d/%d]: 成功 %d, 重复 %d",
                current,
                total,
                success,
                dups,
            )

        with HandRepository(db_path, wal_mode=True) as repo:
            success, duplicates = repo.insert_hands_batch(
                all_records,
                batch_size=batch_size,
                progress_callback=progress_cb,
            )
            LOGGER.info("写入完成: 成功 %d, 重复 %d", success, duplicates)

    return results


def print_summary(results: list[ParseResult], elapsed: float) -> None:
    total_files = len(results)
    skipped_files = sum(1 for r in results if r.skipped)
    success_files = sum(
        1
        for r in results
        if (not r.skipped) and r.error is None and r.success_count > 0
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
    print(
        f"  成功率:       {success_hands / total_hands * 100:.2f}%"
        if total_hands
        else "  成功率:       N/A"
    )
    print("-" * 60)
    print(f"  总耗时:       {elapsed:.2f} 秒")
    print(f"  平均速度:     {total_hands / elapsed:.0f} 手/秒" if elapsed > 0 else "")
    print("=" * 60)

    failed = [r for r in results if (not r.skipped) and r.error is not None]
    if failed:
        print("\n失败文件列表:")
        for r in failed[:10]:
            print(f"  - {r.file_path}: {r.error}")
        if len(failed) > 10:
            print(f"  ... 还有 {len(failed) - 10} 个失败文件")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量解析 GGPoker 手牌历史文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=None,
        help="输出到 SQLite 数据库路径（与 .phhs 输出互斥）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="批量写入大小 (默认: 5000)",
    )

    return parser.parse_args()


def main() -> int:
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

    input_base = args.input if args.input.is_dir() else None

    start_time = time.time()

    if args.sqlite:
        LOGGER.info("使用 SQLite 输出模式: %s", args.sqlite)
        if args.workers > 1:
            results = parse_files_to_sqlite_parallel(
                files,
                args.sqlite,
                max_workers=args.workers,
                batch_size=args.batch_size,
            )
        else:
            results = parse_files_to_sqlite(files, args.sqlite)
    elif args.workers > 1:
        args.output.mkdir(parents=True, exist_ok=True)
        LOGGER.info("使用多进程模式 (workers=%d)", args.workers)
        results = parse_files_parallel(files, args.output, input_base, args.workers)
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        LOGGER.info("使用顺序模式")
        results = parse_files_sequential(files, args.output, input_base)

    elapsed = time.time() - start_time
    print_summary(results, elapsed)

    if args.sqlite:
        with HandRepository(args.sqlite) as repo:
            stats = repo.get_stats()
            print(f"\n数据库统计: 手牌={stats['hands']} 玩家={stats['players']}")

    has_errors = any(r.error is not None for r in results)
    return 1 if has_errors else 0


def parse_files_to_sqlite(
    files: list[Path],
    db_path: Path,
) -> list[ParseResult]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[ParseResult] = []
    for i, input_file in enumerate(files, 1):
        LOGGER.info("解析 [%d/%d]: %s", i, len(files), input_file.name)
        result = parse_single_file_to_sqlite(input_file, db_path)
        results.append(result)
        LOGGER.info(
            "完成 [%d/%d]: %d/%d 手成功",
            i,
            len(files),
            result.success_count,
            result.total_count,
        )

    with HandRepository(db_path) as repo:
        stats = repo.get_stats()
        LOGGER.info(
            "数据库统计: 手牌=%d 玩家=%d",
            stats["hands"],
            stats["players"],
        )

    return results


if __name__ == "__main__":
    sys.exit(main())
