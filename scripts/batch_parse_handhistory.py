#!/usr/bin/env python3
"""批量解析 GGPoker 手牌历史文件。

该模块提供了一个命令行工具，用于批量处理 GGPoker 的手牌历史文本文件。
支持将解析结果保存为 .phhs 文件或导入到 SQLite 数据库中。

使用示例:
    1. 解析目录下的所有文件并保存为 .phhs:
        python scripts/batch_parse_handhistory.py data/input_dir -o data/output_dir

    2. 使用多进程解析文件到 SQLite 数据库:
        python scripts/batch_parse_handhistory.py data/input_dir --sqlite data/poker.db -w 4

    3. 递归解析目录并指定批量写入大小:
        python scripts/batch_parse_handhistory.py data/input_dir --sqlite data/poker.db -r --batch-size 1000
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import Lock, cpu_count
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bayes_poker.hand_history.parse_gg_poker import (
    FAILED_HANDS_DIR,
    FAILED_HANDS_LOG_PATH,
    configure_logging,
    parse_hand_histories,
    save_hand_histories,
)
from bayes_poker.player_metrics.serialization import compute_hand_hash

if TYPE_CHECKING:
    from pokerkit.notation import HandHistory

LOGGER = logging.getLogger(__name__)


_GLOBAL_BLOOM: Any | None = None
_GLOBAL_BLOOM_LOCK: Any | None = None


def _require_bloomfilter() -> Any:
    try:
        from pybloomfilter import BloomFilter
    except Exception as exc:
        raise RuntimeError("未安装 pybloomfiltermmap3（import pybloomfilter 失败）") from exc

    return BloomFilter


def _init_worker_bloom_dedupe(bloom_path: str, lock: Any) -> None:
    global _GLOBAL_BLOOM, _GLOBAL_BLOOM_LOCK

    BloomFilter = _require_bloomfilter()
    _GLOBAL_BLOOM = BloomFilter.open(bloom_path)
    _GLOBAL_BLOOM_LOCK = lock


def _require_sqlite_storage() -> tuple[type[Any], type[Any]]:
    try:
        converter_module = importlib.import_module("bayes_poker.storage.converter")
        repository_module = importlib.import_module("bayes_poker.storage.repository")
        HandHistoryConverter = getattr(converter_module, "HandHistoryConverter")
        HandRepository = getattr(repository_module, "HandRepository")
    except Exception as exc:
        raise RuntimeError(
            "SQLite 输出模式当前不可用：缺少 bayes_poker.storage.converter/bayes_poker.storage.repository"
        ) from exc

    return HandHistoryConverter, HandRepository


@dataclass
class ParseResult:
    """解析结果数据类。

    Attributes:
        file_path: 输入文件的路径。
        success_count: 成功解析的手牌数量。
        total_count: 文件中的总手牌数量。
        output_path: 解析结果的输出路径（如果成功）。
        skipped: 是否跳过了解析。
        skip_reason: 跳过解析的原因。
        error: 如果解析失败，存储错误消息。
    """
    file_path: Path
    success_count: int
    total_count: int
    output_path: Path | None
    duplicate_count: int = 0
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None


@dataclass
class ConvertResult:
    """转换结果数据类。

    Attributes:
        file_path: 输入文件的路径。
        records: 转换后的手牌记录列表。
        total_count: 文件中的总手牌数量。
        error: 如果转换失败，存储错误消息。
    """
    file_path: Path
    records: list[dict[str, Any]]
    total_count: int
    error: str | None = None


def get_input_files(input_path: Path, recursive: bool = False) -> list[Path]:
    """获取输入路径下的所有手牌历史文件。

    Args:
        input_path: 输入的文件或目录路径。
        recursive: 是否递归搜索子目录。

    Returns:
        包含所有符合条件的文件路径列表。

    Raises:
        FileNotFoundError: 如果输入路径不存在。
        ValueError: 如果输入路径无效。
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
    """生成解析结果的输出路径。

    Args:
        input_file: 输入文件路径。
        output_dir: 输出目录路径。
        input_base: 输入的基础目录，用于保持目录结构。

    Returns:
        生成的输出文件路径。
    """
    if input_base and input_base.is_dir():
        relative = input_file.relative_to(input_base)
        output_path = output_dir / relative.with_suffix(".phhs")
    else:
        output_path = output_dir / input_file.with_suffix(".phhs").name

    return output_path


def is_already_parsed(output_path: Path) -> tuple[bool, str | None]:
    """检查文件是否已经被解析过。

    Args:
        output_path: 输出文件路径。

    Returns:
        一个元组 (是否已解析, 理由)。
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
    bloom: Any | None = None,
) -> ParseResult:
    """解析单个手牌历史文件并保存。

    Args:
        input_file: 输入文件路径。
        output_path: 输出文件路径。

    Returns:
        解析结果对象。
    """
    try:
        configure_logging(FAILED_HANDS_LOG_PATH)

        hand_histories, total = parse_hand_histories(input_file)

        bloom_filter = bloom or _GLOBAL_BLOOM
        duplicate_count = 0
        if bloom_filter is not None and hand_histories:
            hands_with_hash: list[tuple[HandHistory, str]] = [
                (hh, compute_hand_hash(hh)) for hh in hand_histories
            ]

            if _GLOBAL_BLOOM_LOCK is not None:
                with _GLOBAL_BLOOM_LOCK:
                    keep = [not bloom_filter.add(h) for _, h in hands_with_hash]
            else:
                keep = [not bloom_filter.add(h) for _, h in hands_with_hash]

            filtered: list[HandHistory] = []
            for (hh, _h), keep_flag in zip(hands_with_hash, keep, strict=True):
                if keep_flag:
                    filtered.append(hh)
                else:
                    duplicate_count += 1

            hand_histories = filtered

        if hand_histories:
            save_hand_histories(output_path, hand_histories)

        return ParseResult(
            file_path=input_file,
            success_count=len(hand_histories),
            total_count=total,
            output_path=output_path if hand_histories else None,
            duplicate_count=duplicate_count,
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
    """解析单个文件并转换为数据库记录。

    Args:
        input_file: 输入文件路径。

    Returns:
        转换结果对象。
    """
    try:
        configure_logging(FAILED_HANDS_LOG_PATH)
        hand_histories, total = parse_hand_histories(input_file)

        if not hand_histories:
            return ConvertResult(
                file_path=input_file,
                records=[],
                total_count=total,
            )

        HandHistoryConverter, _HandRepository = _require_sqlite_storage()
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
    """解析单个文件并将结果保存到 SQLite 数据库。

    Args:
        input_file: 输入文件路径。
        db_path: SQLite 数据库路径。

    Returns:
        解析结果对象。
    """
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

        HandHistoryConverter, HandRepository = _require_sqlite_storage()
        with HandRepository(db_path) as repo:
            converter = HandHistoryConverter(repo)
            success, _failed = converter.batch_convert_and_save(
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
    bloom: Any | None = None,
) -> list[ParseResult]:
    """顺序解析文件列表。

    Args:
        files: 待处理的文件路径列表。
        output_dir: 输出目录路径。
        input_base: 输入的基础目录。

    Returns:
        所有文件的解析结果列表。
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
        result = parse_single_file(input_file, output_path, bloom=bloom)
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
    dedupe_bloom_path: Path | None = None,
    dedupe_lock: Any | None = None,
) -> list[ParseResult]:
    """并发解析文件列表。

    Args:
        files: 待处理的文件路径列表。
        output_dir: 输出目录路径。
        input_base: 输入的基础目录。
        max_workers: 并发工作进程数。

    Returns:
        所有文件的解析结果列表。
    """
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

    if dedupe_bloom_path is None:
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

    if dedupe_lock is None:
        raise ValueError("启用去重时必须提供 dedupe_lock")

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker_bloom_dedupe,
        initargs=(str(dedupe_bloom_path), dedupe_lock),
    ) as executor:
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
    """并发解析文件并将结果批量写入 SQLite 数据库。

    Args:
        files: 待处理的文件路径列表。
        db_path: SQLite 数据库路径。
        max_workers: 并发解析进程数。
        batch_size: 数据库批量写入大小。

    Returns:
        所有文件的解析结果列表。
    """
    if max_workers is None:
        max_workers = min(cpu_count(), 8)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info("启动 %d 个解析进程...", max_workers)

    results: list[ParseResult] = []
    all_records: list[dict[str, Any]] = []
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

        _HandHistoryConverter, HandRepository = _require_sqlite_storage()
        with HandRepository(db_path, wal_mode=True) as repo:
            success, duplicates = repo.insert_hands_batch(
                all_records,
                batch_size=batch_size,
                progress_callback=progress_cb,
            )
            LOGGER.info("写入完成: 成功 %d, 重复 %d", success, duplicates)

    return results


def print_summary(results: list[ParseResult], elapsed: float) -> None:
    """打印解析统计摘要。

    Args:
        results: 所有文件的解析结果列表。
        elapsed: 总耗时（秒）。
    """
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
    total_duplicates = sum(r.duplicate_count for r in results)
    failed_hands = total_hands - success_hands - total_duplicates

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
    if total_duplicates:
        print(f"  去重跳过:     {total_duplicates}")
    print(f"  解析失败:     {failed_hands}")
    effective_total = total_hands - total_duplicates
    print(
        f"  成功率:       {success_hands / effective_total * 100:.2f}%"
        if effective_total > 0
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
    """配置日志系统。

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
    """解析命令行参数。

    Returns:
        解析后的参数命名空间。
    """
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

    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="生成 .phhs 时启用近似全局去重（Bloom Filter）",
    )
    parser.add_argument(
        "--dedupe-capacity",
        type=int,
        default=100_000_000,
        help="布隆过滤器期望手牌数 (默认: 100000000)",
    )
    parser.add_argument(
        "--dedupe-error-rate",
        type=float,
        default=0.01,
        help="布隆过滤器误判率 (默认: 0.01)",
    )
    parser.add_argument(
        "--dedupe-bloom-path",
        type=Path,
        default=None,
        help="布隆过滤器 mmap 文件路径（默认在输出目录内创建）",
    )

    return parser.parse_args()


def main() -> int:
    """主入口函数。

    Returns:
        退出码（0 表示成功，1 表示有错误）。
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

    input_base = args.input if args.input.is_dir() else None

    start_time = time.time()

    bloom_local: Any | None = None
    dedupe_bloom_path: Path | None = None
    dedupe_lock: Any | None = None

    if args.dedupe:
        if args.sqlite:
            LOGGER.warning("当前启用 --sqlite 时忽略 --dedupe")
        else:
            BloomFilter = _require_bloomfilter()
            args.output.mkdir(parents=True, exist_ok=True)

            if args.dedupe_bloom_path is None:
                dedupe_path = args.output / "hand_hashes.bloom"
            else:
                dedupe_path = args.dedupe_bloom_path

            dedupe_path.parent.mkdir(parents=True, exist_ok=True)

            bloom_path_str = str(dedupe_path)
            if dedupe_path.exists():
                bf = BloomFilter.open(bloom_path_str)
            else:
                bf = BloomFilter(args.dedupe_capacity, args.dedupe_error_rate, bloom_path_str)

            dedupe_bloom_path = dedupe_path

            if args.workers > 1:
                bf.close()
                dedupe_lock = Lock()
            else:
                bloom_local = bf

            LOGGER.info(
                "启用去重(Bloom mmap): path=%s expected=%d error_rate=%s",
                dedupe_bloom_path,
                args.dedupe_capacity,
                args.dedupe_error_rate,
            )

    if args.sqlite:
        try:
            _require_sqlite_storage()
        except RuntimeError as exc:
            LOGGER.error(str(exc))
            return 1

    try:
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
            results = parse_files_parallel(
                files,
                args.output,
                input_base,
                args.workers,
                dedupe_bloom_path=dedupe_bloom_path,
                dedupe_lock=dedupe_lock,
            )
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            LOGGER.info("使用顺序模式")
            results = parse_files_sequential(
                files,
                args.output,
                input_base,
                bloom=bloom_local,
            )
    finally:
        if bloom_local is not None and args.workers <= 1 and args.dedupe and (not args.sqlite):
            bloom_local.close()

    elapsed = time.time() - start_time
    print_summary(results, elapsed)

    if args.sqlite:
        _HandHistoryConverter, HandRepository = _require_sqlite_storage()
        with HandRepository(args.sqlite) as repo:
            stats = repo.get_stats()
            print(f"\n数据库统计: 手牌={stats['hands']} 玩家={stats['players']}")

    has_errors = any(r.error is not None for r in results)
    return 1 if has_errors else 0


def parse_files_to_sqlite(
    files: list[Path],
    db_path: Path,
) -> list[ParseResult]:
    """顺序解析文件并将结果保存到 SQLite 数据库。

    Args:
        files: 待处理的文件路径列表。
        db_path: SQLite 数据库路径。

    Returns:
        所有文件的解析结果列表。
    """
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

    _HandHistoryConverter, HandRepository = _require_sqlite_storage()
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
