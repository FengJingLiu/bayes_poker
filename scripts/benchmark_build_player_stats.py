#!/usr/bin/env python3
"""Benchmark: 测试 build_player_stats.py 的解析速度。

测试场景：
1. 单线程处理 10 万手牌
2. 多进程 (24 workers) 处理 10 万手牌
3. 重复手牌去重性能（先解析 10 万手，再次运行同样的 10 万手）

用法：
    uv run python scripts/benchmark_build_player_stats.py
"""

from __future__ import annotations

import multiprocessing
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

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

TARGET_HANDS = 100_000


@dataclass
class BenchmarkResult:
    name: str
    hands_count: int
    duration_seconds: float
    new_hands: int
    skipped_hands: int

    @property
    def hands_per_second(self) -> float:
        return self.hands_count / self.duration_seconds if self.duration_seconds > 0 else 0

    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  手牌数: {self.hands_count:,}\n"
            f"  耗时: {self.duration_seconds:.2f}s\n"
            f"  速度: {self.hands_per_second:,.0f} hands/s\n"
            f"  新增: {self.new_hands:,} | 跳过: {self.skipped_hands:,}"
        )


def load_hands_from_directory(directory: Path, limit: int) -> list[HandHistory]:
    hands: list[HandHistory] = []
    phhs_files = sorted(directory.glob("*.phhs"))

    for phhs_path in phhs_files:
        if len(hands) >= limit:
            break

        with phhs_path.open("rb") as f:
            file_hands = list(HandHistory.load_all(f, parse_value=parse_value_in_cents))
            remaining = limit - len(hands)
            hands.extend(file_hands[:remaining])

    return hands


def process_hands_single_thread(
    hands: list[HandHistory],
    db_path: Path,
) -> tuple[int, int]:
    with PlayerStatsRepository(db_path) as repo:
        hands_with_hash = [(hh, compute_hand_hash(hh)) for hh in hands]
        processed_hashes = repo.get_processed_hand_hashes([h for _, h in hands_with_hash])

        new_hands_with_hash = [(hh, h) for hh, h in hands_with_hash if h not in processed_hashes]
        new_hands_list = [hh for hh, _ in new_hands_with_hash]
        skipped = len(hands) - len(new_hands_list)

        if new_hands_list:
            hu_hands = [hh for hh in new_hands_list if hh.players and len(hh.players) == 2]
            six_max_hands = [hh for hh in new_hands_list if hh.players and len(hh.players) > 2]

            if hu_hands:
                hu_stats = build_player_stats_from_hands(hu_hands, TableType.HEADS_UP)
                repo.upsert_batch_with_merge(hu_stats)

            if six_max_hands:
                six_max_stats = build_player_stats_from_hands(six_max_hands, TableType.SIX_MAX)
                repo.upsert_batch_with_merge(six_max_stats)

            repo.mark_hands_processed([h for _, h in new_hands_with_hash])

        return len(new_hands_list), skipped


def process_files_to_worker_db(args: tuple[list[str], str]) -> tuple[int, str]:
    """Worker: 逐文件加载处理，写入独立数据库。返回 (手牌数, db_path)。"""
    file_paths, worker_db_path = args

    total_hands = 0

    with PlayerStatsRepository(worker_db_path) as repo:
        for file_path_str in file_paths:
            path = Path(file_path_str)
            with path.open("rb") as f:
                hands = list(HandHistory.load_all(f, parse_value=parse_value_in_cents))

            if not hands:
                continue

            hu_hands = [hh for hh in hands if hh.players and len(hh.players) == 2]
            six_max_hands = [hh for hh in hands if hh.players and len(hh.players) > 2]

            if hu_hands:
                hu_stats = build_player_stats_from_hands(hu_hands, TableType.HEADS_UP)
                repo.upsert_batch_with_merge(hu_stats)

            if six_max_hands:
                six_max_stats = build_player_stats_from_hands(six_max_hands, TableType.SIX_MAX)
                repo.upsert_batch_with_merge(six_max_stats)

            total_hands += len(hands)

    return total_hands, worker_db_path


def merge_worker_databases_sql(worker_db_paths: list[Path], final_db_path: Path) -> None:
    """使用 SQL ATTACH 批量合并 worker 数据库，避免 Python 对象传输。"""
    with PlayerStatsRepository(final_db_path) as _:
        pass

    conn = sqlite3.connect(str(final_db_path))
    conn.row_factory = sqlite3.Row

    for i, worker_db in enumerate(worker_db_paths):
        if not worker_db.exists():
            continue

        alias = f"worker_{i}"
        conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(worker_db),))

        conn.execute(f"""
            INSERT INTO player_stats (
                player_name, table_type, vpip_positive, vpip_total,
                preflop_stats_json, postflop_stats_json, created_at, updated_at
            )
            SELECT
                player_name, table_type, vpip_positive, vpip_total,
                preflop_stats_json, postflop_stats_json, created_at, updated_at
            FROM {alias}.player_stats
            WHERE NOT EXISTS (
                SELECT 1 FROM player_stats
                WHERE player_stats.player_name = {alias}.player_stats.player_name
                AND player_stats.table_type = {alias}.player_stats.table_type
            )
        """)

        conn.execute(f"DETACH DATABASE {alias}")
        conn.commit()

    conn.close()


def process_hands_multi_process(
    directory: Path,
    db_path: Path,
    workers: int,
    limit: int,
    tmp_dir: Path,
) -> tuple[int, int, int]:
    """多进程处理：文件分成小 chunks，workers 处理后合并到单一数据库。"""
    phhs_files = sorted(directory.glob("*.phhs"))

    chunk_size = 10
    file_chunks: list[list[Path]] = []
    for i in range(0, len(phhs_files), chunk_size):
        chunk = phhs_files[i : i + chunk_size]
        if chunk:
            file_chunks.append(chunk)

    worker_db_paths = [tmp_dir / f"chunk_{i}.db" for i in range(len(file_chunks))]

    args_list = [
        ([str(f) for f in chunk], str(worker_db_paths[i]))
        for i, chunk in enumerate(file_chunks)
    ]

    print(f"  启动 {workers} workers 处理 {len(file_chunks)} chunks...")

    with multiprocessing.Pool(workers) as pool:
        results = pool.map(process_files_to_worker_db, args_list)
        total_hands = sum(r[0] for r in results)

    print(f"  处理完成: {total_hands} hands")

    existing_worker_dbs = [p for p in worker_db_paths if p.exists()]
    if existing_worker_dbs:
        print(f"  合并 {len(existing_worker_dbs)} 个数据库...")
        merge_worker_databases_sql(existing_worker_dbs, db_path)

    for p in worker_db_paths:
        p.unlink(missing_ok=True)
        for suffix in ["-wal", "-shm"]:
            wal = p.with_suffix(p.suffix + suffix)
            wal.unlink(missing_ok=True)

    return total_hands, 0, total_hands


def run_benchmark(
    name: str,
    hands: list[HandHistory] | None,
    db_path: Path,
    workers: int = 1,
    directory: Path | None = None,
    limit: int = TARGET_HANDS,
    tmp_dir: Path | None = None,
) -> BenchmarkResult:
    start = time.perf_counter()

    if workers == 1:
        assert hands is not None
        new_hands, skipped = process_hands_single_thread(hands, db_path)
        total = len(hands)
    else:
        assert directory is not None and tmp_dir is not None
        new_hands, skipped, total = process_hands_multi_process(
            directory, db_path, workers, limit, tmp_dir
        )

    duration = time.perf_counter() - start

    return BenchmarkResult(
        name=name,
        hands_count=total,
        duration_seconds=duration,
        new_hands=new_hands,
        skipped_hands=skipped,
    )


def cleanup_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    wal_path = db_path.with_suffix(".db-wal")
    shm_path = db_path.with_suffix(".db-shm")
    if wal_path.exists():
        wal_path.unlink()
    if shm_path.exists():
        shm_path.unlink()


def main() -> None:
    data_dir = PROJECT_ROOT / "data" / "outputs"
    if not data_dir.exists():
        print(f"错误: 数据目录不存在: {data_dir}")
        sys.exit(1)

    print(f"加载 {TARGET_HANDS:,} 手牌...")
    start_load = time.perf_counter()
    hands = load_hands_from_directory(data_dir, TARGET_HANDS)
    load_duration = time.perf_counter() - start_load
    print(f"加载完成: {len(hands):,} 手牌，耗时 {load_duration:.2f}s\n")

    if len(hands) < TARGET_HANDS:
        print(f"警告: 仅找到 {len(hands):,} 手牌，少于目标 {TARGET_HANDS:,}\n")

    results: list[BenchmarkResult] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        print("=" * 60)
        print("Benchmark 1: 单线程处理")
        print("=" * 60)
        db_path = tmp_path / "bench_single.db"
        result1 = run_benchmark("单线程", hands, db_path, workers=1)
        print(result1)
        results.append(result1)
        cleanup_db(db_path)
        print()

        print("=" * 60)
        print("Benchmark 2: 多进程 (4 workers) 处理")
        print("=" * 60)

        del hands
        import gc
        gc.collect()

        db_path = tmp_path / "bench_multi.db"
        result2 = run_benchmark(
            "多进程 (4)",
            None,
            db_path,
            workers=4,
            directory=data_dir,
            limit=TARGET_HANDS,
            tmp_dir=tmp_path,
        )
        print(result2)
        results.append(result2)
        cleanup_db(db_path)
        print()

        print("=" * 60)
        print("Benchmark 3: 重复手牌去重")
        print("=" * 60)
        db_path = tmp_path / "bench_dedup.db"

        hands = load_hands_from_directory(data_dir, TARGET_HANDS)

        print("  第一轮: 首次处理...")
        result3a = run_benchmark("去重-首次", hands, db_path, workers=1)
        print(f"  {result3a}")
        results.append(result3a)

        print("\n  第二轮: 重复处理（应全部跳过）...")
        result3b = run_benchmark("去重-重复", hands, db_path, workers=1)
        print(f"  {result3b}")
        results.append(result3b)
        cleanup_db(db_path)
        print()

    print("=" * 60)
    print("汇总结果")
    print("=" * 60)
    print(f"{'场景':<20} {'手牌数':>12} {'耗时(s)':>10} {'速度(h/s)':>12}")
    print("-" * 60)
    for r in results:
        print(f"{r.name:<20} {r.hands_count:>12,} {r.duration_seconds:>10.2f} {r.hands_per_second:>12,.0f}")

    if len(results) >= 2:
        speedup = results[0].duration_seconds / results[1].duration_seconds if results[1].duration_seconds > 0 else 0
        print(f"\n多进程加速比: {speedup:.2f}x")

    if len(results) >= 4:
        dedup_speedup = results[2].duration_seconds / results[3].duration_seconds if results[3].duration_seconds > 0 else 0
        print(f"去重加速比: {dedup_speedup:.2f}x (跳过重复比首次处理快)")


if __name__ == "__main__":
    main()
