#!/usr/bin/env python3
"""Profile OpponentEstimator initialization bottleneck."""

import time
from pathlib import Path

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.opponent_estimator import OpponentEstimator
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository


def main():
    db_path = Path("data/database/player_stats.db")
    table_type = TableType.SIX_MAX

    with PlayerStatsRepository(db_path) as repo:
        t0 = time.perf_counter()
        summaries = repo.load_summary_for_estimator(table_type)
        t1 = time.perf_counter()
        print(f"Load summaries: {(t1-t0)*1000:.1f} ms")

        # Manually step through initialization
        estimator = OpponentEstimator.__new__(OpponentEstimator)

        t0 = time.perf_counter()
        estimator._initialize_common_state(
            table_type=table_type,
            options=None,
            random_seed=42,
        )
        t1 = time.perf_counter()
        print(f"Common state: {(t1-t0)*1000:.1f} ms")

        estimator._stats_list = []
        estimator._summaries = summaries
        estimator._stats_cache = {}
        estimator._stats_loader = lambda name: repo.get(name, table_type)

        t0 = time.perf_counter()
        estimator._initialize_priors_and_base_models()
        t1 = time.perf_counter()
        print(f"Priors + base models: {(t1-t0)*1000:.1f} ms")

        # Break down _initialize_priors_and_base_models
        t0 = time.perf_counter()
        estimator._vpip_prior = estimator._create_vpip_prior()
        t1 = time.perf_counter()
        print(f"  - VPIP prior: {(t1-t0)*1000:.1f} ms")

        t0 = time.perf_counter()
        estimator._pfr_prior = estimator._create_pfr_prior()
        t1 = time.perf_counter()
        print(f"  - PFR prior: {(t1-t0)*1000:.1f} ms")

        t0 = time.perf_counter()
        estimator._aggression_prior = estimator._create_aggression_prior()
        t1 = time.perf_counter()
        print(f"  - AGG prior: {(t1-t0)*1000:.1f} ms")

        t0 = time.perf_counter()
        estimator._wtp_prior = estimator._create_wtp_prior()
        t1 = time.perf_counter()
        print(f"  - WTP prior: {(t1-t0)*1000:.1f} ms")

        t0 = time.perf_counter()
        estimator._base_models = [
            estimator._estimate_base_model_from_summary(summary)
            for summary in summaries
        ]
        t1 = time.perf_counter()
        print(f"  - Base models: {(t1-t0)*1000:.1f} ms")

        t0 = time.perf_counter()
        estimator._build_numpy_cache()
        t1 = time.perf_counter()
        print(f"  - NumPy cache: {(t1-t0)*1000:.1f} ms")


if __name__ == "__main__":
    main()
