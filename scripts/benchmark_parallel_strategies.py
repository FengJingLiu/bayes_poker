#!/usr/bin/env python3
"""对比两种并行策略的性能：单线程 vs 多进程分片。

说明：
- 单线程：直接调用 build_player_stats_from_hands。
- 多进程：将手牌列表切分成多个 chunk，每个 worker 独立构建 stats，主进程再做 merge。

用法：
    uv run python scripts/benchmark_parallel_strategies.py
"""

from __future__ import annotations

import multiprocessing
import sys
import time
from pathlib import Path

from pokerkit import HandHistory

from bayes_poker.player_metrics.builder import build_player_stats_from_hands
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.player_metrics.serialization import merge_player_stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "outputs"

TARGET_HANDS = 20_000
WORKERS = 4


def load_hands(directory: Path, limit: int) -> list[HandHistory]:
    hands: list[HandHistory] = []
    for phhs_file in sorted(directory.glob("*.phhs")):
        with phhs_file.open("rb") as fp:
            for hh in HandHistory.load_all(fp):
                hands.append(hh)
                if len(hands) >= limit:
                    return hands
    return hands


def _split_chunks(items: list[HandHistory], chunks: int) -> list[list[HandHistory]]:
    if chunks <= 1:
        return [items]
    chunk_size = max(1, len(items) // chunks)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _key(stats: PlayerStats) -> tuple[str, int]:
    return (stats.player_name, int(stats.table_type))


def _merge_maps(
    target: dict[tuple[str, int], PlayerStats],
    source: dict[str, PlayerStats],
) -> None:
    for stats in source.values():
        k = _key(stats)
        existing = target.get(k)
        if existing is None:
            target[k] = stats
        else:
            merge_player_stats(existing, stats)


def _build_stats_for_hands(
    hands: list[HandHistory],
) -> dict[tuple[str, int], PlayerStats]:
    hu_hands = [hh for hh in hands if hh.players and len(hh.players) == 2]
    six_max_hands = [hh for hh in hands if hh.players and len(hh.players) > 2]

    merged: dict[tuple[str, int], PlayerStats] = {}

    if hu_hands:
        hu_map = build_player_stats_from_hands(hu_hands, TableType.HEADS_UP)
        _merge_maps(merged, hu_map)

    if six_max_hands:
        six_map = build_player_stats_from_hands(six_max_hands, TableType.SIX_MAX)
        _merge_maps(merged, six_map)

    return merged


def _worker_build_stats(hands: list[HandHistory]) -> dict[tuple[str, int], PlayerStats]:
    return _build_stats_for_hands(hands)


def benchmark_single_thread(
    hands: list[HandHistory],
) -> tuple[float, dict[tuple[str, int], PlayerStats]]:
    start = time.perf_counter()
    stats = _build_stats_for_hands(hands)
    return time.perf_counter() - start, stats


def benchmark_multi_process(
    hands: list[HandHistory], workers: int
) -> tuple[float, dict[tuple[str, int], PlayerStats]]:
    chunks = _split_chunks(hands, workers)

    start = time.perf_counter()
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        partial_results = pool.map(_worker_build_stats, chunks)

    merged: dict[tuple[str, int], PlayerStats] = {}
    for part in partial_results:
        for k, stats in part.items():
            existing = merged.get(k)
            if existing is None:
                merged[k] = stats
            else:
                merge_player_stats(existing, stats)

    return time.perf_counter() - start, merged


def main() -> None:
    if not DATA_DIR.exists():
        print(f"错误: 数据目录不存在: {DATA_DIR}")
        raise SystemExit(1)

    print(f"加载 {TARGET_HANDS:,} 手牌...")
    load_start = time.perf_counter()
    hands = load_hands(DATA_DIR, TARGET_HANDS)
    load_elapsed = time.perf_counter() - load_start
    print(f"加载完成: {len(hands):,} 手牌，耗时 {load_elapsed:.2f}s\n")

    print("=" * 60)
    print("策略 1: 单线程")
    print("=" * 60)
    t1, s1 = benchmark_single_thread(hands)
    print(f"  耗时: {t1:.2f}s")
    print(f"  速度: {len(hands) / t1:,.0f} hands/s")
    print(f"  玩家数: {len(s1)}")
    print()

    print("=" * 60)
    print(f"策略 2: 多进程分片 ({WORKERS} workers)")
    print("=" * 60)
    t2, s2 = benchmark_multi_process(hands, WORKERS)
    print(f"  耗时: {t2:.2f}s")
    print(f"  速度: {len(hands) / t2:,.0f} hands/s")
    print(f"  玩家数: {len(s2)}")
    print()

    print("=" * 60)
    print("对比结果")
    print("=" * 60)
    if t2 > 0:
        print(f"加速比: {t1 / t2:.2f}x")


if __name__ == "__main__":
    main()
