"""翻前玩家画像与平滑层."""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.player_metrics.models import ActionStats, PlayerStats
from bayes_poker.player_metrics.params import PreFlopParams


def smooth_frequency(n_act: int, total: int, mu: float, k: float) -> float:
    """对动作频率做总体先验平滑.

    Args:
        n_act: 玩家在目标动作上的样本数.
        total: 玩家在当前场景下的总样本数.
        mu: 总体先验频率.
        k: 先验强度.

    Returns:
        融合总体先验与玩家样本后的动作频率.

    Raises:
        ValueError: 当输入样本或参数非法时抛出.
    """

    if n_act < 0:
        raise ValueError("n_act 不能为负数.")
    if total < 0:
        raise ValueError("total 不能为负数.")
    if n_act > total:
        raise ValueError("n_act 不能大于 total.")
    if not 0.0 <= mu <= 1.0:
        raise ValueError("mu 必须位于 [0.0, 1.0] 区间内.")
    if k <= 0.0:
        raise ValueError("k 必须大于 0.")

    return (n_act + (k * mu)) / (total + k)


def build_confidence(total: int, k: float) -> float:
    """根据玩家样本量构建置信度.

    Args:
        total: 玩家在当前场景下的总样本数.
        k: 置信度平滑系数.

    Returns:
        位于 [0.0, 1.0) 的置信度.

    Raises:
        ValueError: 当输入参数非法时抛出.
    """

    if total < 0:
        raise ValueError("total 不能为负数.")
    if k <= 0.0:
        raise ValueError("k 必须大于 0.")

    return total / (total + k)


@dataclass(frozen=True, slots=True)
class PlayerTendencyProfile:
    """单个翻前场景下的玩家画像.

    Attributes:
        open_freq: 激进行动频率.
        call_freq: 跟注频率.
        confidence: 玩家样本置信度.
        size_signal_enabled: 是否启用尺寸信号.
    """

    open_freq: float
    call_freq: float
    confidence: float
    size_signal_enabled: bool = False


class PlayerTendencyProfileBuilder:
    """构建翻前玩家画像的纯内存构建器."""

    def __init__(
        self,
        *,
        smoothing_k: float = 20.0,
        confidence_k: float = 20.0,
        size_signal_threshold: int = 20,
    ) -> None:
        """初始化玩家画像构建器.

        Args:
            smoothing_k: 动作频率的先验强度.
            confidence_k: 样本置信度的平滑系数.
            size_signal_threshold: 启用尺寸信号所需的最小样本数.

        Raises:
            ValueError: 当输入参数非法时抛出.
        """

        if smoothing_k <= 0.0:
            raise ValueError("smoothing_k 必须大于 0.")
        if confidence_k <= 0.0:
            raise ValueError("confidence_k 必须大于 0.")
        if size_signal_threshold < 0:
            raise ValueError("size_signal_threshold 不能为负数.")

        self._smoothing_k = smoothing_k
        self._confidence_k = confidence_k
        self._size_signal_threshold = size_signal_threshold

    def build(
        self,
        *,
        player_stats: PlayerStats,
        params: PreFlopParams,
        population_stats: ActionStats,
        size_signal_sample_count: int | None = None,
    ) -> PlayerTendencyProfile:
        """构建单个翻前场景的玩家画像.

        Args:
            player_stats: 玩家统计快照.
            params: 当前翻前场景参数.
            population_stats: 当前场景的总体统计先验.
            size_signal_sample_count: 可选的尺寸信号样本数.

        Returns:
            当前场景下的玩家画像.

        Raises:
            ValueError: 当尺寸样本数为负时抛出.
        """

        if size_signal_sample_count is not None and size_signal_sample_count < 0:
            raise ValueError("size_signal_sample_count 不能为负数.")

        action_stats = player_stats.get_preflop_stats(params)
        total = action_stats.total_samples()

        open_freq = smooth_frequency(
            action_stats.bet_raise_samples,
            total,
            population_stats.bet_raise_probability(),
            self._smoothing_k,
        )
        call_freq = smooth_frequency(
            action_stats.check_call_samples,
            total,
            population_stats.check_call_probability(),
            self._smoothing_k,
        )
        confidence = build_confidence(total, self._confidence_k)

        size_signal_enabled = (
            size_signal_sample_count is not None
            and size_signal_sample_count >= self._size_signal_threshold
        )

        return PlayerTendencyProfile(
            open_freq=open_freq,
            call_freq=call_freq,
            confidence=confidence,
            size_signal_enabled=size_signal_enabled,
        )


__all__ = [
    "PlayerTendencyProfile",
    "PlayerTendencyProfileBuilder",
    "build_confidence",
    "smooth_frequency",
]
