"""翻前贝叶斯范围引擎."""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.strategy.preflop_engine.policy_calibrator import ActionPolicy
from bayes_poker.strategy.range import PreflopRange, get_hand_key_to_169_index

_HAND_KEY_TO_169_INDEX = get_hand_key_to_169_index()


@dataclass(frozen=True, slots=True)
class RangeBelief:
    """翻前后验范围包装器.

    Attributes:
        _posterior_range: 私有后验范围.
    """

    _posterior_range: PreflopRange

    def total_frequency(self) -> float:
        """返回后验范围的总频率.

        Returns:
            组合加权后的总频率.
        """

        return self._posterior_range.total_frequency()

    def __getitem__(self, hand_key: str) -> float:
        """按 169 手牌键读取后验频率.

        Args:
            hand_key: 例如 `AQo` 或 `AJs` 的手牌键.

        Returns:
            指定手牌的后验频率.

        Raises:
            KeyError: 当手牌键不存在时抛出.
        """

        return self._posterior_range.strategy[_HAND_KEY_TO_169_INDEX[hand_key]]

    def to_preflop_range(self) -> PreflopRange:
        """返回后验范围副本.

        Returns:
            可独立修改的 PreflopRange 副本.
        """

        return PreflopRange(
            strategy=list(self._posterior_range.strategy),
            evs=list(self._posterior_range.evs),
        )


class RangeEngine:
    """最小翻前贝叶斯范围引擎."""

    def observe_action(
        self,
        *,
        prior: PreflopRange,
        calibrated_policy: ActionPolicy,
        action_name: str,
    ) -> RangeBelief:
        """基于观测动作更新后验范围.

        Args:
            prior: 观测前的先验范围.
            calibrated_policy: 已校准的动作策略.
            action_name: 当前观测到的动作名称.

        Returns:
            基于动作似然更新后的后验包装对象.
        """

        return RangeBelief(
            _posterior_range=update_posterior(
                prior=prior,
                calibrated_policy=calibrated_policy,
                action_name=action_name,
            )
        )


def update_posterior(
    prior: PreflopRange,
    calibrated_policy: ActionPolicy,
    action_name: str,
) -> PreflopRange:
    """根据观测动作执行最小贝叶斯后验更新.

    Args:
        prior: 观测前的先验范围.
        calibrated_policy: 已校准的动作策略.
        action_name: 当前观测到的动作名称.

    Returns:
        归一化后的后验范围.
    """

    action_likelihood = calibrated_policy.for_action(action_name)
    posterior = PreflopRange(
        strategy=[
            prior_probability * likelihood_probability
            for prior_probability, likelihood_probability in zip(
                prior.strategy,
                action_likelihood.strategy,
                strict=True,
            )
        ],
        evs=list(action_likelihood.evs),
    )
    posterior.normalize()
    return posterior


__all__ = [
    "RangeBelief",
    "RangeEngine",
    "update_posterior",
]
