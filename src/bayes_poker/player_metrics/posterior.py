"""玩家池后验平滑原语."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import math

from .enums import ActionType, Position
from .params import PostFlopParams, PreFlopParams


class ActionBucket(StrEnum):
    """可装回 `ActionStats` 的动作桶."""

    FOLD = "fold"
    CHECK_CALL = "check_call"
    BET_RAISE = "bet_raise"


class ActionSpaceKind(StrEnum):
    """动作空间模式."""

    BINARY = "binary"
    MULTINOMIAL = "multinomial"


@dataclass(frozen=True, slots=True)
class BinaryPosteriorCounts:
    """Beta 平滑后二元节点的 pseudo-count.

    Attributes:
        positive: 正类 pseudo-count.
        total: 总 pseudo-count.
    """

    positive: float
    total: float


@dataclass(frozen=True, slots=True)
class PosteriorSmoothingConfig:
    """后验平滑配置.

    Attributes:
        enabled: 是否启用后验平滑.
        pool_prior_strength: 玩家池先验强度.
    """

    enabled: bool = False
    pool_prior_strength: float = 20.0

    def __post_init__(self) -> None:
        """校验后验平滑配置.

        Raises:
            ValueError: 当先验强度不为正时抛出.
        """

        if self.pool_prior_strength <= 0.0:
            raise ValueError("pool_prior_strength 必须大于 0.")


@dataclass(frozen=True, slots=True)
class ActionSpaceSpec:
    """动作空间描述.

    Attributes:
        kind: 当前动作空间模式.
        total_fields: 按固定顺序排列的动作字段.
        positive_field: 二元动作空间中的“正类”字段; 多元动作空间固定为 `None`.
    """

    kind: ActionSpaceKind
    total_fields: tuple[str, ...]
    positive_field: str | None = None

    def __post_init__(self) -> None:
        """校验动作空间定义.

        Raises:
            ValueError: 当动作空间定义与模式不匹配时抛出.
        """

        if not self.total_fields:
            raise ValueError("total_fields 不能为空.")

        if self.kind == ActionSpaceKind.BINARY:
            if len(self.total_fields) != 2:
                raise ValueError("binary 动作空间必须恰好包含两个动作字段.")
            if self.positive_field is None:
                raise ValueError("binary 动作空间必须指定 positive_field.")
            if self.positive_field not in self.total_fields:
                raise ValueError("positive_field 必须属于 total_fields.")
            return

        if self.positive_field is not None:
            raise ValueError("multinomial 动作空间不能指定 positive_field.")


def smooth_binary_counts(
    *,
    prior_probability: float,
    prior_strength: float,
    positive_count: float,
    total_count: float,
) -> BinaryPosteriorCounts:
    """按 Beta-Binomial 公式平滑二元动作计数.

    Args:
        prior_probability: 先验中的正类概率.
        prior_strength: 先验强度 `k`.
        positive_count: 玩家观测到的正类计数 `x`.
        total_count: 玩家总观测计数 `n`.

    Returns:
        二元后验 pseudo-count.

    Raises:
        ValueError: 当输入非法时抛出.
    """

    _validate_probability(prior_probability, field_name="prior_probability")
    _validate_positive_strength(prior_strength)
    _validate_non_negative(positive_count, field_name="positive_count")
    _validate_non_negative(total_count, field_name="total_count")
    if positive_count > total_count:
        raise ValueError("positive_count 不能大于 total_count.")

    return BinaryPosteriorCounts(
        positive=(prior_strength * prior_probability) + positive_count,
        total=prior_strength + total_count,
    )


def smooth_multinomial_counts(
    *,
    prior_probabilities: Sequence[float],
    prior_strength: float,
    counts: Sequence[float],
) -> tuple[float, ...]:
    """按 Dirichlet-Multinomial 公式平滑多元动作计数.

    Args:
        prior_probabilities: 先验动作分布.
        prior_strength: 先验强度 `k`.
        counts: 玩家观测计数.

    Returns:
        平滑后的 pseudo-count 元组.

    Raises:
        ValueError: 当输入非法时抛出.
    """

    _validate_positive_strength(prior_strength)
    if len(prior_probabilities) != len(counts):
        raise ValueError("prior_probabilities 与 counts 长度必须一致.")
    if not prior_probabilities:
        raise ValueError("prior_probabilities 不能为空.")

    for probability in prior_probabilities:
        _validate_probability(probability, field_name="prior_probabilities")
    for count in counts:
        _validate_non_negative(count, field_name="counts")

    prior_sum = float(sum(prior_probabilities))
    if not math.isclose(prior_sum, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("prior_probabilities 的 sum 必须为 1.0.")

    return tuple(
        (prior_strength * prior_probability) + count
        for prior_probability, count in zip(prior_probabilities, counts, strict=True)
    )


def classify_preflop_action_space(params: PreFlopParams) -> ActionSpaceSpec:
    """判定翻前动作空间.

    Args:
        params: 翻前情境参数.

    Returns:
        可驱动后续平滑与回填的动作空间描述.
    """

    if params.previous_action == ActionType.FOLD and params.num_raises == 0:
        if params.position == Position.BIG_BLIND:
            return ActionSpaceSpec(
                kind=ActionSpaceKind.BINARY,
                total_fields=(
                    ActionBucket.CHECK_CALL.value,
                    ActionBucket.BET_RAISE.value,
                ),
                positive_field=ActionBucket.BET_RAISE.value,
            )
        if params.position != Position.SMALL_BLIND and params.num_callers == 0:
            return ActionSpaceSpec(
                kind=ActionSpaceKind.BINARY,
                total_fields=(
                    ActionBucket.FOLD.value,
                    ActionBucket.BET_RAISE.value,
                ),
                positive_field=ActionBucket.BET_RAISE.value,
            )

    return ActionSpaceSpec(
        kind=ActionSpaceKind.MULTINOMIAL,
        total_fields=(
            ActionBucket.FOLD.value,
            ActionBucket.CHECK_CALL.value,
            ActionBucket.BET_RAISE.value,
        ),
    )


def classify_postflop_action_space(params: PostFlopParams) -> ActionSpaceSpec:
    """判定翻后动作空间.

    Args:
        params: 翻后情境参数.

    Returns:
        可驱动后续平滑与回填的动作空间描述.
    """

    if params.num_bets == 0:
        return ActionSpaceSpec(
            kind=ActionSpaceKind.BINARY,
            total_fields=(
                ActionBucket.CHECK_CALL.value,
                ActionBucket.BET_RAISE.value,
            ),
            positive_field=ActionBucket.BET_RAISE.value,
        )

    return ActionSpaceSpec(
        kind=ActionSpaceKind.MULTINOMIAL,
        total_fields=(
            ActionBucket.FOLD.value,
            ActionBucket.CHECK_CALL.value,
            ActionBucket.BET_RAISE.value,
        ),
    )


def _validate_probability(value: float, *, field_name: str) -> None:
    """校验概率输入.

    Args:
        value: 待校验概率.
        field_name: 字段名.

    Raises:
        ValueError: 当概率不在 `[0.0, 1.0]` 区间时抛出.
    """

    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} 必须位于 [0.0, 1.0] 区间内.")


def _validate_positive_strength(value: float) -> None:
    """校验先验强度.

    Args:
        value: 待校验先验强度.

    Raises:
        ValueError: 当先验强度不为正时抛出.
    """

    if value <= 0.0:
        raise ValueError("prior_strength 必须大于 0.")


def _validate_non_negative(value: float, *, field_name: str) -> None:
    """校验非负计数.

    Args:
        value: 待校验计数.
        field_name: 字段名.

    Raises:
        ValueError: 当计数为负时抛出.
    """

    if value < 0.0:
        raise ValueError(f"{field_name} 不能为负数.")


__all__ = [
    "ActionBucket",
    "ActionSpaceKind",
    "ActionSpaceSpec",
    "BinaryPosteriorCounts",
    "PosteriorSmoothingConfig",
    "classify_postflop_action_space",
    "classify_preflop_action_space",
    "smooth_binary_counts",
    "smooth_multinomial_counts",
]
