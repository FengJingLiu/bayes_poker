"""OpponentEstimator 性能基准测试.

测量 OpponentEstimator 从 summary 快速路径初始化的耗时,
以及从真实数据库随机挑选 1000 名玩家并计算后验的端到端性能.

历史基线 (2026-03-18, 128K 玩家池, SIX_MAX):
  - 全量 PlayerStats 反序列化 (load_all_for_estimator): ~360s (128174 rows x 38KB blob)
  - 全量 OpponentEstimator.__init__: ~19min (含反序列化 + 相似度索引构建)
  - Summary 快速路径 from_summaries(): ~4.7s (load=1.6s + init=3.1s)
  - Python player_stats_from_binary 单条: ~2.8ms (repo.get 端到端 ~3.1ms)
  - build_metrics_summary 一次性构建: ~20min (含全量反序列化 + 全局先验计算)
  - estimate_player_model 单次: ~622ms (128K 池; numpy 相似度 ~30ms,
    collect_prior ~660ms, estimate_ad ~280ms; 共 30 preflop + 1296 postflop 节点)
  - 延迟分布 (n=200): P50=422ms, P90=560ms, P99=726ms, max=948ms
  NOTE: 全量路径极慢, 不再作为 benchmark 测试运行, 仅记录基线数据.

门控条件: BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 + 数据库文件存在.
"""

from __future__ import annotations

import csv
import os
import random
import time

import pytest

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.player_metrics.opponent_estimator import OpponentEstimator
from bayes_poker.storage import PlayerStatsRepository

from .helpers import (
    PLAYER_CORE_STATS_CSV_PATH,
    PLAYER_STATS_DB_PATH,
    RUN_REAL_SCENARIO_ENV,
)

# ---------------------------------------------------------------------------
# 门控跳过
# ---------------------------------------------------------------------------

_SKIP_REASON_ENV = f"未启用真实场景测试 (设置 {RUN_REAL_SCENARIO_ENV}=1 才运行)"
_SKIP_REASON_DB = f"玩家统计数据库不存在: {PLAYER_STATS_DB_PATH}"
_SKIP_REASON_CSV = f"玩家核心统计 CSV 不存在: {PLAYER_CORE_STATS_CSV_PATH}"

pytestmark = [
    pytest.mark.large_sample,
    pytest.mark.skipif(
        os.environ.get(RUN_REAL_SCENARIO_ENV) != "1",
        reason=_SKIP_REASON_ENV,
    ),
    pytest.mark.skipif(
        not PLAYER_STATS_DB_PATH.exists(),
        reason=_SKIP_REASON_DB,
    ),
    pytest.mark.skipif(
        not PLAYER_CORE_STATS_CSV_PATH.exists(),
        reason=_SKIP_REASON_CSV,
    ),
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_SAMPLE_COUNT = 1000
"""随机抽样玩家数."""

_MIN_HANDS = 100
"""筛选玩家的最小总手数 (严格大于)."""

_RANDOM_SEED = 42
"""随机种子, 保证可复现."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_player_names_from_csv(
    *,
    csv_path: "os.PathLike[str]",
    min_hands: int,
    sample_count: int,
    seed: int,
) -> list[str]:
    """从 player_core_stats.csv 随机抽样玩家名.

    筛选条件: SIX_MAX, 非 aggregated, total_hands > min_hands.

    Args:
        csv_path: CSV 文件路径.
        min_hands: 最小总手数 (严格大于).
        sample_count: 期望抽样数量.
        seed: 随机种子.

    Returns:
        随机抽样后的玩家名列表.

    Raises:
        ValueError: 当满足条件的玩家数量不足时.
    """
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        candidates: list[str] = []
        for row in reader:
            table_type = (row.get("table_type") or "").strip().upper()
            if table_type != "SIX_MAX":
                continue
            name = (row.get("player_name") or "").strip()
            if not name or name.lower().startswith("aggregated_"):
                continue
            try:
                total_hands = int(float(row.get("total_hands", "0") or "0"))
            except ValueError:
                continue
            if total_hands <= min_hands:
                continue
            candidates.append(name)

    if len(candidates) < sample_count:
        raise ValueError(
            f"满足条件的玩家不足: required={sample_count}, "
            f"available={len(candidates)}"
        )

    rng = random.Random(seed)
    return rng.sample(candidates, sample_count)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def player_stats_repo() -> PlayerStatsRepository:
    """打开真实玩家统计仓库 (module 级复用).

    Returns:
        已连接的 PlayerStatsRepository 实例.
    """
    repo = PlayerStatsRepository(PLAYER_STATS_DB_PATH)
    repo.connect()
    return repo


@pytest.fixture(scope="module")
def estimator_from_summaries(
    player_stats_repo: PlayerStatsRepository,
) -> OpponentEstimator:
    """从 summary 快速路径构建 OpponentEstimator (module 级复用).

    Args:
        player_stats_repo: 已连接的仓库.

    Returns:
        已初始化的 OpponentEstimator 实例.
    """
    summaries = player_stats_repo.load_summary_for_estimator(TableType.SIX_MAX)
    if not summaries:
        pytest.skip("Summary 表为空或不存在")

    def _stats_loader(name: str) -> PlayerStats | None:
        """按需加载单个玩家的完整统计."""
        try:
            return player_stats_repo.get(name, TableType.SIX_MAX)
        except Exception:
            return None

    return OpponentEstimator.from_summaries(
        summaries,
        table_type=TableType.SIX_MAX,
        stats_loader=_stats_loader,
        random_seed=_RANDOM_SEED,
    )


@pytest.fixture(scope="module")
def sampled_player_names() -> list[str]:
    """从 CSV 随机抽取 1000 名玩家 (module 级复用).

    Returns:
        玩家名列表.
    """
    return _load_player_names_from_csv(
        csv_path=PLAYER_CORE_STATS_CSV_PATH,
        min_hands=_MIN_HANDS,
        sample_count=_SAMPLE_COUNT,
        seed=_RANDOM_SEED,
    )


# ---------------------------------------------------------------------------
# Test 1: Summary 快速路径初始化耗时
# ---------------------------------------------------------------------------


class TestEstimatorInitFromSummaries:
    """测量 from_summaries() 快速路径的初始化耗时."""

    def test_summary_init_timing(
        self,
        player_stats_repo: PlayerStatsRepository,
    ) -> None:
        """Summary 快速路径初始化应在 10s 内完成.

        Args:
            player_stats_repo: 已连接的仓库.
        """
        # 加载 summaries
        start_load = time.perf_counter()
        summaries = player_stats_repo.load_summary_for_estimator(TableType.SIX_MAX)
        elapsed_load = time.perf_counter() - start_load

        if not summaries:
            pytest.skip("Summary 表为空或不存在")

        def _stats_loader(name: str) -> PlayerStats | None:
            try:
                return player_stats_repo.get(name, TableType.SIX_MAX)
            except Exception:
                return None

        # 初始化 estimator
        start_init = time.perf_counter()
        estimator = OpponentEstimator.from_summaries(
            summaries,
            table_type=TableType.SIX_MAX,
            stats_loader=_stats_loader,
            random_seed=_RANDOM_SEED,
        )
        elapsed_init = time.perf_counter() - start_init
        elapsed_total = elapsed_load + elapsed_init

        print(
            f"\n[Benchmark] Summary 快速路径初始化:\n"
            f"  summary_count={len(summaries)}\n"
            f"  load_summaries={elapsed_load:.3f}s\n"
            f"  from_summaries={elapsed_init:.3f}s\n"
            f"  total={elapsed_total:.3f}s"
        )

        assert estimator is not None
        assert elapsed_total < 10.0, (
            f"Summary 路径总耗时 {elapsed_total:.1f}s 超过 10s 上限"
        )


# ---------------------------------------------------------------------------
# Test 2: 随机 1000 名真实玩家后验计算
# ---------------------------------------------------------------------------


class TestQuery1000RealPlayers:
    """从真实数据库随机挑选 1000 名玩家, 测量后验计算耗时."""

    def test_query_1000_real_players_posterior(
        self,
        player_stats_repo: PlayerStatsRepository,
        estimator_from_summaries: OpponentEstimator,
        sampled_player_names: list[str],
    ) -> None:
        """加载 1000 名真实玩家的 PlayerStats 并计算后验, 测量端到端耗时.

        流程: CSV 筛选 → repo.get() 加载完整统计 → estimate_player_model().

        Args:
            player_stats_repo: 已连接的仓库.
            estimator_from_summaries: 从 summary 构建的估计器.
            sampled_player_names: 随机抽样的玩家名列表.
        """
        query_count = len(sampled_player_names)

        # 阶段 1: 逐个加载完整 PlayerStats
        start_load = time.perf_counter()
        loaded_stats: list[PlayerStats] = []
        skipped = 0
        for name in sampled_player_names:
            stats = player_stats_repo.get(name, TableType.SIX_MAX)
            if stats is not None:
                loaded_stats.append(stats)
            else:
                skipped += 1
        elapsed_load = time.perf_counter() - start_load

        assert len(loaded_stats) > 0, "未能加载任何玩家统计"

        # 阶段 2: 批量计算后验
        start_estimate = time.perf_counter()
        for stats in loaded_stats:
            preflop_ads, postflop_ads = (
                estimator_from_summaries.estimate_player_model(stats)
            )
            assert len(preflop_ads) > 0
            assert len(postflop_ads) > 0
        elapsed_estimate = time.perf_counter() - start_estimate

        elapsed_total = elapsed_load + elapsed_estimate
        actual_count = len(loaded_stats)
        avg_load_ms = (elapsed_load / actual_count) * 1000
        avg_estimate_ms = (elapsed_estimate / actual_count) * 1000
        avg_total_ms = (elapsed_total / actual_count) * 1000

        print(
            f"\n[Benchmark] 1000 名真实玩家后验计算:\n"
            f"  requested={query_count}, loaded={actual_count}, "
            f"skipped={skipped}\n"
            f"  load_stats: total={elapsed_load:.3f}s, "
            f"avg={avg_load_ms:.2f}ms/player\n"
            f"  estimate:   total={elapsed_estimate:.3f}s, "
            f"avg={avg_estimate_ms:.2f}ms/player\n"
            f"  end-to-end: total={elapsed_total:.3f}s, "
            f"avg={avg_total_ms:.2f}ms/player"
        )

        assert avg_estimate_ms < 1000.0, (
            f"平均后验计算 {avg_estimate_ms:.1f}ms/player 超过 1000ms 上限"
        )


# ---------------------------------------------------------------------------
# Test 3: 单次加载 + 后验的详细耗时分布
# ---------------------------------------------------------------------------


class TestPosteriorTimingDistribution:
    """测量后验计算的耗时分布 (P50/P90/P99)."""

    def test_posterior_latency_distribution(
        self,
        player_stats_repo: PlayerStatsRepository,
        estimator_from_summaries: OpponentEstimator,
        sampled_player_names: list[str],
    ) -> None:
        """统计后验计算各百分位延迟.

        Args:
            player_stats_repo: 已连接的仓库.
            estimator_from_summaries: 从 summary 构建的估计器.
            sampled_player_names: 随机抽样的玩家名列表.
        """
        # 取前 200 名做详细计时 (减少总耗时)
        sample = sampled_player_names[:200]
        latencies_ms: list[float] = []

        for name in sample:
            stats = player_stats_repo.get(name, TableType.SIX_MAX)
            if stats is None:
                continue

            t0 = time.perf_counter()
            estimator_from_summaries.estimate_player_model(stats)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000)

        assert len(latencies_ms) > 0, "无有效延迟数据"

        latencies_ms.sort()
        n = len(latencies_ms)
        p50 = latencies_ms[n // 2]
        p90 = latencies_ms[int(n * 0.9)]
        p99 = latencies_ms[int(n * 0.99)]
        p_min = latencies_ms[0]
        p_max = latencies_ms[-1]
        avg = sum(latencies_ms) / n

        print(
            f"\n[Benchmark] 后验计算延迟分布 (n={n}):\n"
            f"  min={p_min:.2f}ms, P50={p50:.2f}ms, "
            f"P90={p90:.2f}ms, P99={p99:.2f}ms, max={p_max:.2f}ms\n"
            f"  avg={avg:.2f}ms"
        )

        assert p99 < 2000.0, (
            f"P99 延迟 {p99:.1f}ms 超过 2000ms 上限"
        )
