#!/usr/bin/env python3
"""Benchmark OpponentEstimator summary loading and similarity calculation."""

import time
from pathlib import Path

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.opponent_estimator import OpponentEstimator
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository


def main():
    db_path = Path("data/database/player_stats.db")
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    table_type = TableType.SIX_MAX

    with PlayerStatsRepository(db_path) as repo:
        # Benchmark 1: Load summaries
        t0 = time.perf_counter()
        summaries = repo.load_summary_for_estimator(table_type)
        t1 = time.perf_counter()
        load_time_ms = (t1 - t0) * 1000
        print(f"✅ Loaded {len(summaries)} summaries in {load_time_ms:.1f} ms")

        # Benchmark 2: Initialize estimator (includes NumPy cache build)
        t0 = time.perf_counter()
        estimator = OpponentEstimator.from_summaries(
            summaries,
            table_type=table_type,
            stats_loader=lambda name: repo.get(name, table_type),
            random_seed=42,
        )
        t1 = time.perf_counter()
        init_time_ms = (t1 - t0) * 1000
        print(f"✅ Initialized estimator in {init_time_ms:.1f} ms")

        # Benchmark 3: Similarity calculation (preflop + postflop)
        target_name = summaries[100].player_name if len(summaries) > 100 else summaries[0].player_name
        target_stats = repo.get(target_name, table_type)
        if not target_stats:
            print(f"❌ Target player not found: {target_name}")
            return

        t0 = time.perf_counter()
        preflop_ads, postflop_ads = estimator.estimate_player_model(target_stats)
        t1 = time.perf_counter()
        calc_time_ms = (t1 - t0) * 1000
        print(f"✅ Similarity calculation in {calc_time_ms:.1f} ms")
        print(f"   - Preflop ADs: {len(preflop_ads)}")
        print(f"   - Postflop ADs: {len(postflop_ads)}")

        # Summary
        total_time_ms = load_time_ms + init_time_ms + calc_time_ms
        print(f"\n📊 Total time: {total_time_ms:.1f} ms")
        print(f"   - Load summaries: {load_time_ms:.1f} ms ({load_time_ms/total_time_ms*100:.1f}%)")
        print(f"   - Init estimator: {init_time_ms:.1f} ms ({init_time_ms/total_time_ms*100:.1f}%)")
        print(f"   - Similarity calc: {calc_time_ms:.1f} ms ({calc_time_ms/total_time_ms*100:.1f}%)")


if __name__ == "__main__":
    main()
