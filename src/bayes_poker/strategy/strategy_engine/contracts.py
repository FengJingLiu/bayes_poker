"""strategy_engine v2 的强类型契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias

if TYPE_CHECKING:
    from bayes_poker.table.observed_state import ObservedTableState


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    """返回推荐动作的决策结果。"""

    state_version: int
    action_code: str | None
    amount: float | None
    confidence: float | None
    ev: float | None
    notes: str
    action_evs: dict[str, float] = field(default_factory=dict)
    action_distribution: dict[str, float] = field(default_factory=dict)
    selected_node_id: int | None = None
    selected_source_id: int | None = None
    sampling_random: float | None = None
    range_breakdown: dict[str, float] = field(default_factory=dict)
    kind: Literal["recommendation"] = "recommendation"


@dataclass(frozen=True, slots=True)
class NoResponseDecision:
    """表示当前不需要返回策略响应。"""

    state_version: int
    reason: str
    kind: Literal["no_response"] = "no_response"


@dataclass(frozen=True, slots=True)
class UnsupportedScenarioDecision:
    """表示当前场景超出 v1 支持矩阵。"""

    state_version: int
    reason: str
    kind: Literal["unsupported_scenario"] = "unsupported_scenario"


@dataclass(frozen=True, slots=True)
class SafeFallbackDecision:
    """表示发生可安全降级的错误。"""

    state_version: int
    error_code: str
    notes: str
    confidence: float | None = None
    ev: float | None = None
    kind: Literal["safe_fallback"] = "safe_fallback"


StrategyDecision: TypeAlias = (
    RecommendationDecision
    | NoResponseDecision
    | UnsupportedScenarioDecision
    | SafeFallbackDecision
)


class StrategyHandler(Protocol):
    """strategy_engine v2 对外暴露的强类型处理器。"""

    async def __call__(
        self,
        session_id: str,
        observed_state: ObservedTableState,
    ) -> StrategyDecision: ...
