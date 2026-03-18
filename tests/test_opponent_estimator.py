"""OpponentEstimator 单元测试。"""

from __future__ import annotations

import pytest

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import (
    ActionStats,
    PlayerMetricsSummary,
    PlayerStats,
    StatValue,
)
from bayes_poker.player_metrics.opponent_estimator import (
    OpponentEstimator,
    OpponentEstimatorOptions,
)
from bayes_poker.player_metrics.params import PostFlopParams, PreFlopParams


def _make_player_stats(
    name: str,
    vpip: float = 0.25,
    *,
    total_hands: int = 100,
    table_type: TableType = TableType.SIX_MAX,
) -> PlayerStats:
    """构造具有指定 VPIP 和手数的 mock PlayerStats。"""
    stats = PlayerStats(player_name=name, table_type=table_type)
    positive = int(vpip * total_hands)
    stats.vpip = StatValue(positive=positive, total=total_hands)

    for action_stats in stats.preflop_stats:
        action_stats.raise_samples = 10
        action_stats.check_call_samples = 20
        action_stats.fold_samples = 10

    for action_stats in stats.postflop_stats:
        action_stats.raise_samples = 8
        action_stats.check_call_samples = 15
        action_stats.bet_0_40 = 5
        action_stats.fold_samples = 12

    return stats


def _make_player_pool(
    count: int = 10,
    *,
    table_type: TableType = TableType.SIX_MAX,
) -> list[PlayerStats]:
    """构造 VPIP 从 0.1 到 0.55 均匀分布的玩家池。"""
    players = []
    for i in range(count):
        vpip = 0.10 + 0.05 * i
        stats = _make_player_stats(
            f"player_{i}",
            vpip=vpip,
            total_hands=200,
            table_type=table_type,
        )
        players.append(stats)
    return players


def _make_summary(stats: PlayerStats) -> PlayerMetricsSummary:
    """从完整 `PlayerStats` 构造轻量 summary.

    Args:
        stats: 完整玩家统计.

    Returns:
        仅包含四类标量计数的 summary.
    """

    pfr_pos, pfr_total = calculate_pfr(stats)
    agg_pos, agg_total = calculate_aggression(stats)
    wtp_pos, wtp_total = calculate_wtp(stats)
    return PlayerMetricsSummary(
        player_name=stats.player_name,
        table_type=stats.table_type,
        total_hands=stats.vpip.total,
        vpip_pos=stats.vpip.positive,
        vpip_total=stats.vpip.total,
        pfr_pos=pfr_pos,
        pfr_total=pfr_total,
        agg_pos=agg_pos,
        agg_total=agg_total,
        wtp_pos=wtp_pos,
        wtp_total=wtp_total,
    )


class TestOpponentEstimatorInit:
    def test_init_succeeds_with_player_pool(self) -> None:
        pool = _make_player_pool(10)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=42)
        assert estimator is not None

    def test_init_with_empty_pool_succeeds(self) -> None:
        estimator = OpponentEstimator([], TableType.SIX_MAX, random_seed=0)
        assert estimator is not None

    def test_prior_histograms_are_built(self) -> None:
        pool = _make_player_pool(20)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=0)
        assert len(estimator._vpip_prior) == 100
        assert len(estimator._pfr_prior) == 100
        assert len(estimator._aggression_prior) == 100
        assert len(estimator._wtp_prior) == 100


class TestOpponentEstimatorEstimatePlayerModel:
    def test_returns_correct_length_ad_lists(self) -> None:
        pool = _make_player_pool(10)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=42)

        target = _make_player_stats("hero", vpip=0.25, total_hands=150)
        preflop_ads, postflop_ads = estimator.estimate_player_model(target)

        expected_pre = len(PreFlopParams.get_all_params(TableType.SIX_MAX))
        expected_post = len(PostFlopParams.get_all_params(TableType.SIX_MAX))
        assert len(preflop_ads) == expected_pre
        assert len(postflop_ads) == expected_post

    def test_non_forced_action_fold_is_zero(self) -> None:
        pool = _make_player_pool(15)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=42)
        target = _make_player_stats("hero", vpip=0.25, total_hands=150)
        preflop_ads, _ = estimator.estimate_player_model(target)

        for i, params in enumerate(PreFlopParams.get_all_params(TableType.SIX_MAX)):
            if not params.forced_action():
                ad = preflop_ads[i]
                assert abs(ad.fold.mean) < 1e-10, (
                    f"非强制节点 {params} 的 fold 均值应为 0，实际 {ad.fold.mean}"
                )

    def test_non_forced_action_br_cc_sum_to_one(self) -> None:
        pool = _make_player_pool(15)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=42)
        target = _make_player_stats("hero", vpip=0.25, total_hands=150)
        preflop_ads, _ = estimator.estimate_player_model(target)

        for i, params in enumerate(PreFlopParams.get_all_params(TableType.SIX_MAX)):
            if not params.forced_action():
                ad = preflop_ads[i]
                total = ad.bet_raise.mean + ad.check_call.mean
                assert abs(total - 1.0) < 0.05, (
                    f"非强制节点 {params} 的 BR+CC 均值之和应约为 1，实际 {total}"
                )

    def test_forced_action_three_dims_sum_to_one(self) -> None:
        pool = _make_player_pool(15)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=42)
        target = _make_player_stats("hero", vpip=0.25, total_hands=150)
        _, postflop_ads = estimator.estimate_player_model(target)

        for i, params in enumerate(PostFlopParams.get_all_params(TableType.SIX_MAX)):
            if params.forced_action():
                ad = postflop_ads[i]
                total = ad.bet_raise.mean + ad.check_call.mean + ad.fold.mean
                assert abs(total - 1.0) < 0.05, (
                    f"强制节点 {params} 的 BR+CC+FO 均值之和应约为 1，实际 {total}"
                )


class TestOpponentEstimatorReproducibility:
    def test_same_seed_produces_same_result(self) -> None:
        pool = _make_player_pool(15)
        target = _make_player_stats("hero", vpip=0.3, total_hands=200)

        estimator_a = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=123)
        pre_a, post_a = estimator_a.estimate_player_model(target)

        estimator_b = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=123)
        pre_b, post_b = estimator_b.estimate_player_model(target)

        for ad_a, ad_b in zip(pre_a, pre_b):
            assert abs(ad_a.bet_raise.mean - ad_b.bet_raise.mean) < 1e-12, (
                "相同随机种子应产生相同结果"
            )
        for ad_a, ad_b in zip(post_a, post_b):
            assert abs(ad_a.bet_raise.mean - ad_b.bet_raise.mean) < 1e-12, (
                "相同随机种子应产生相同翻后结果"
            )

    def test_estimated_ad_has_valid_probability_ranges(self) -> None:
        pool = _make_player_pool(15)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=7)
        target = _make_player_stats("hero", vpip=0.3, total_hands=200)
        preflop_ads, postflop_ads = estimator.estimate_player_model(target)
        for ad in preflop_ads + postflop_ads:
            assert 0.0 <= ad.bet_raise.mean <= 1.0
            assert 0.0 <= ad.check_call.mean <= 1.0
            assert 0.0 <= ad.fold.mean <= 1.0
            assert ad.bet_raise.sigma >= 0.0
            assert ad.check_call.sigma >= 0.0
            assert ad.fold.sigma >= 0.0


class TestOpponentEstimatorWithOptions:
    def test_custom_options_respected(self) -> None:
        opts = OpponentEstimatorOptions(
            prior_num_bins=50,
            min_samples=10,
            max_similar_players=20,
            max_update_samples=100,
        )
        pool = _make_player_pool(10)
        estimator = OpponentEstimator(pool, TableType.SIX_MAX, options=opts, random_seed=0)

        assert len(estimator._vpip_prior) == 50

        target = _make_player_stats("hero", vpip=0.25, total_hands=80)
        preflop_ads, postflop_ads = estimator.estimate_player_model(target)
        assert len(preflop_ads) > 0
        assert len(postflop_ads) > 0


class TestOpponentEstimatorOptionsValidation:
    """无效配置应立即抛出 ValueError。"""

    def test_zero_prior_num_bins_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="prior_num_bins"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(prior_num_bins=0),
            )

    def test_zero_min_samples_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="min_samples"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(min_samples=0),
            )

    def test_zero_max_similar_players_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="max_similar_players"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(max_similar_players=0),
            )

    def test_negative_max_difference_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="max_difference"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(max_difference=-0.1),
            )

    def test_negative_max_base_stats_sigma_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="max_base_stats_sigma"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(max_base_stats_sigma=-1.0),
            )

    def test_negative_max_update_samples_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="max_update_samples"):
            OpponentEstimator(
                [],
                TableType.SIX_MAX,
                options=OpponentEstimatorOptions(max_update_samples=-1),
            )


class TestOpponentEstimatorAggregatedExclusion:
    """aggregated_* 玩家不得进入先验池。"""

    def test_aggregated_player_excluded_from_stats_list(self) -> None:
        pool = _make_player_pool(5)
        aggregated = _make_player_stats("aggregated_sixmax_100", vpip=0.3, total_hands=500)
        pool.append(aggregated)

        estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=0)

        player_names = [s.player_name for s in estimator._stats_list]
        assert "aggregated_sixmax_100" not in player_names
        assert len(estimator._stats_list) == 5


class TestOpponentEstimatorFromSummaries:
    """`from_summaries` 路径应与完整统计路径保持一致."""

    def test_from_summaries_produces_same_results_as_full_path(self) -> None:
        """summary 初始化应复现完整池初始化结果.

        Returns:
            None.
        """

        pool = _make_player_pool(12)
        stats_by_name = {stats.player_name: stats for stats in pool}
        summaries = [_make_summary(stats) for stats in pool]
        target = _make_player_stats("hero", vpip=0.32, total_hands=180)

        full_estimator = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=17)
        summary_estimator = OpponentEstimator.from_summaries(
            summaries,
            table_type=TableType.SIX_MAX,
            stats_loader=lambda name: stats_by_name.get(name),
            random_seed=17,
        )

        full_preflop, full_postflop = full_estimator.estimate_player_model(target)
        summary_preflop, summary_postflop = summary_estimator.estimate_player_model(
            target
        )

        for full_ad, summary_ad in zip(full_preflop, summary_preflop, strict=True):
            assert full_ad.bet_raise.mean == summary_ad.bet_raise.mean
            assert full_ad.bet_raise.sigma == summary_ad.bet_raise.sigma
            assert full_ad.check_call.mean == summary_ad.check_call.mean
            assert full_ad.check_call.sigma == summary_ad.check_call.sigma
            assert full_ad.fold.mean == summary_ad.fold.mean
            assert full_ad.fold.sigma == summary_ad.fold.sigma

        for full_ad, summary_ad in zip(full_postflop, summary_postflop, strict=True):
            assert full_ad.bet_raise.mean == summary_ad.bet_raise.mean
            assert full_ad.bet_raise.sigma == summary_ad.bet_raise.sigma
            assert full_ad.check_call.mean == summary_ad.check_call.mean
            assert full_ad.check_call.sigma == summary_ad.check_call.sigma
            assert full_ad.fold.mean == summary_ad.fold.mean
            assert full_ad.fold.sigma == summary_ad.fold.sigma


class TestOpponentEstimatorVectorizedSelection:
    """NumPy 向量化排序路径的语义正确性测试。"""

    def _make_estimator_with_mask(
        self,
        mask: list[bool],
        max_similar: int = 130,
    ) -> OpponentEstimator:
        """构造仅含 _np_valid_mask 和 _base_models 的最小估计器."""
        import numpy as np

        opts = OpponentEstimatorOptions(max_similar_players=max_similar)
        est = OpponentEstimator.__new__(OpponentEstimator)
        est._options = opts
        # 用 object() 占位，_select_top_difference_pairs 只关心 mask
        est._base_models = [object() for _ in mask]
        est._np_valid_mask = np.array(mask, dtype=bool)
        return est

    def test_tie_break_preserves_original_index_order(self) -> None:
        """距离相同时应按原始索引升序选取（与 Python 标量路径一致）。

        distances=[1.0, 1.0, 0.0, 0.0], max_similar_players=1
        期望选 index=2（最小距离 0.0 中索引最小的）。
        """
        import numpy as np

        est = self._make_estimator_with_mask([True, True, True, True], max_similar=1)
        pairs = est._select_top_difference_pairs(
            np.array([1.0, 1.0, 0.0, 0.0], dtype=np.float32)
        )
        assert len(pairs) == 1
        assert pairs[0].index == 2
        assert pairs[0].difference == 0.0

    def test_nan_distances_are_excluded(self) -> None:
        """NaN 距离应被过滤，不得出现在结果中。"""
        import numpy as np

        est = self._make_estimator_with_mask([True, True, True], max_similar=3)
        pairs = est._select_top_difference_pairs(
            np.array([float("nan"), 0.1, float("inf")], dtype=np.float32)
        )
        # NaN 过滤后剩 index=1(0.1) 和 index=2(inf)
        assert len(pairs) == 2
        assert pairs[0].index == 1
        assert abs(pairs[0].difference - 0.1) < 1e-6
        assert pairs[1].index == 2
        assert pairs[1].difference == float("inf")

    def test_none_base_models_excluded_via_mask(self) -> None:
        """mask=False 的位置（None base model）不应出现在结果中。"""
        import numpy as np

        est = self._make_estimator_with_mask([True, False, True, False], max_similar=10)
        pairs = est._select_top_difference_pairs(
            np.array([0.5, 0.1, 0.3, 0.0], dtype=np.float32)
        )
        returned_indices = {p.index for p in pairs}
        assert 1 not in returned_indices
        assert 3 not in returned_indices
        assert returned_indices == {0, 2}

    def test_numpy_and_python_paths_remain_equivalent_with_float_noise(self) -> None:
        """向量化路径与标量路径在浮点噪声下仍保持等价语义。

        preflop 距离在该夹具下可严格一致。
        postflop 距离会出现 1e-15 级别噪声, 因而只校验候选集合与逐索引距离近似相等。
        """
        pool = _make_player_pool(15)
        target = _make_player_stats("hero", vpip=0.28, total_hands=200)

        est_with_cache = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=7)
        # 强制清除 cache，触发 Python 标量回退路径
        est_no_cache = OpponentEstimator(pool, TableType.SIX_MAX, random_seed=7)
        del est_no_cache._np_valid_mask

        bm = est_with_cache._estimate_base_model(target)

        pre_np = est_with_cache._get_similar_opponents_preflop(bm)
        pre_py = est_no_cache._get_similar_opponents_preflop(bm)
        post_np = est_with_cache._get_similar_opponents_postflop(bm)
        post_py = est_no_cache._get_similar_opponents_postflop(bm)

        assert [p.index for p in pre_np] == [p.index for p in pre_py], (
            "preflop 向量化路径与标量路径索引顺序应一致"
        )
        post_np_by_index = {pair.index: pair.difference for pair in post_np}
        post_py_by_index = {pair.index: pair.difference for pair in post_py}

        assert post_np_by_index.keys() == post_py_by_index.keys(), (
            "postflop 向量化路径与标量路径应返回同一批候选玩家"
        )
        for index, scalar_distance in post_py_by_index.items():
            assert post_np_by_index[index] == pytest.approx(
                scalar_distance,
                abs=1e-12,
            ), f"postflop index={index} 的距离只允许出现可忽略浮点噪声"
