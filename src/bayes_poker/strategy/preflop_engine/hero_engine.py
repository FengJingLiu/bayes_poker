"""Hero 翻前决策引擎."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from bayes_poker.strategy.preflop_engine.explain import (
    DecisionExplanation,
    build_summary,
)
from bayes_poker.strategy.preflop_engine.policy_calibrator import ActionPolicy
from bayes_poker.strategy.preflop_engine.range_engine import RangeBelief
from bayes_poker.strategy.preflop_engine.state import ActionFamily, PreflopDecisionState
from bayes_poker.strategy.preflop_engine.tendency import PlayerTendencyProfile
from bayes_poker.table.layout.base import Position as TablePosition

_EPSILON = 1e-9
_BTN_STEAL_CALL_THRESHOLD = 0.20
_LIMP_FOLD_THRESHOLD = 0.60


@dataclass(frozen=True, slots=True)
class HeroOpponentContext:
    """Hero 决策使用的最小对手上下文.

    Attributes:
        tendency_profile: 对手画像, 用于读取 open/call 倾向.
        range_belief: 可选后验范围, 当前最小实现保留给后续任务扩展.
        limp_fold_frequency: 对手 limp 后面对隔离加注的弃牌频率.
    """

    tendency_profile: PlayerTendencyProfile | None = None
    range_belief: RangeBelief | None = None
    limp_fold_frequency: float | None = None


@dataclass(frozen=True, slots=True)
class HeroDecision:
    """Hero 决策结果.

    Attributes:
        recommended_action: 推荐动作名称.
        recommended_size_bb: 推荐总尺度, 单位 BB.
        action_distribution: 归一化后的动作分布.
        explanation: 解释输出.
    """

    recommended_action: str
    recommended_size_bb: float | None
    action_distribution: dict[str, float]
    explanation: DecisionExplanation


class PreflopHeroEngine:
    """最小翻前 Hero 决策引擎."""

    def __init__(self, *, base_policy: ActionPolicy) -> None:
        """初始化 Hero 决策引擎.

        Args:
            base_policy: 基础动作策略.
        """

        self._base_policy = base_policy

    def decide(
        self,
        *,
        hero_state: PreflopDecisionState,
        opponents: Mapping[TablePosition, HeroOpponentContext] | None = None,
    ) -> HeroDecision:
        """根据共享状态与对手上下文产出 Hero 决策.

        Args:
            hero_state: 当前 Hero 翻前共享状态.
            opponents: 对手上下文映射.

        Returns:
            Hero 决策结果.
        """

        return self._build_decision(
            hero_state=hero_state,
            opponents=opponents or {},
        )

    def _build_decision(
        self,
        *,
        hero_state: PreflopDecisionState,
        opponents: Mapping[TablePosition, HeroOpponentContext],
    ) -> HeroDecision:
        """构建最小 Hero 决策结果.

        Args:
            hero_state: 当前 Hero 翻前共享状态.
            opponents: 对手上下文映射.

        Returns:
            Hero 决策结果.
        """

        distribution = self._build_base_distribution()
        reasons: list[str] = []

        if (
            hero_state.action_family == ActionFamily.OPEN
            and hero_state.actor_position == TablePosition.BTN
        ):
            self._apply_btn_steal_adjustment(
                distribution=distribution,
                opponents=opponents,
                reasons=reasons,
            )

        if hero_state.action_family == ActionFamily.LIMP:
            self._apply_iso_adjustment(
                distribution=distribution,
                opponents=opponents,
                reasons=reasons,
            )

        normalized_distribution = self._normalize_distribution(distribution)
        recommended_action = max(
            normalized_distribution.items(),
            key=lambda item: (item[1], item[0]),
        )[0]
        explanation = DecisionExplanation(
            summary=build_summary(
                recommended_action=recommended_action,
                reasons=reasons,
            ),
            reasons=tuple(reasons),
        )

        return HeroDecision(
            recommended_action=recommended_action,
            recommended_size_bb=self._infer_size_bb(
                hero_state=hero_state,
                recommended_action=recommended_action,
            ),
            action_distribution=normalized_distribution,
            explanation=explanation,
        )

    def _build_base_distribution(self) -> dict[str, float]:
        """读取基础策略总频率.

        Returns:
            以动作名为键的基础分布.
        """

        return {
            action_name: max(0.0, self._base_policy.total_frequency(action_name))
            for action_name in self._base_policy.action_names
        }

    def _apply_btn_steal_adjustment(
        self,
        *,
        distribution: dict[str, float],
        opponents: Mapping[TablePosition, HeroOpponentContext],
        reasons: list[str],
    ) -> None:
        """对 BTN first-in open 应用偷盲扩宽.

        Args:
            distribution: 当前动作分布.
            opponents: 对手上下文映射.
            reasons: 解释原因累积列表.
        """

        open_action = self._find_open_action(distribution)
        if open_action is None:
            return

        boost = 0.0
        under_defending_positions: list[str] = []
        for blind_position in (TablePosition.SB, TablePosition.BB):
            context = opponents.get(blind_position)
            profile = context.tendency_profile if context is not None else None
            if profile is None:
                continue

            if profile.call_freq < _BTN_STEAL_CALL_THRESHOLD:
                boost += (_BTN_STEAL_CALL_THRESHOLD - profile.call_freq) * max(
                    profile.confidence,
                    0.5,
                )
                under_defending_positions.append(blind_position.value)

        if boost <= _EPSILON:
            return

        shifted = self._shift_mass(
            distribution=distribution,
            target_action=open_action,
            source_actions=("FOLD", "CALL"),
            amount=min(boost, 0.35),
        )
        if shifted <= _EPSILON:
            return

        joined_positions = "/".join(under_defending_positions)
        reasons.append(f"{joined_positions} 防守偏弱, 扩宽 BTN steal")

    def _apply_iso_adjustment(
        self,
        *,
        distribution: dict[str, float],
        opponents: Mapping[TablePosition, HeroOpponentContext],
        reasons: list[str],
    ) -> None:
        """对 limp 场景应用隔离加注调整.

        Args:
            distribution: 当前动作分布.
            opponents: 对手上下文映射.
            reasons: 解释原因累积列表.
        """

        aggressive_action = self._find_aggressive_action(distribution)
        if aggressive_action is None:
            return

        best_limp_fold = max(
            (
                context.limp_fold_frequency
                for context in opponents.values()
                if context.limp_fold_frequency is not None
            ),
            default=None,
        )
        if best_limp_fold is None or best_limp_fold <= _LIMP_FOLD_THRESHOLD:
            return

        shifted = self._shift_mass(
            distribution=distribution,
            target_action=aggressive_action,
            source_actions=("FOLD", "CALL"),
            amount=min(best_limp_fold - 0.40, 0.30),
        )
        if shifted <= _EPSILON:
            return

        reasons.append("对手存在明显 limp-fold 倾向, 提升隔离加注频率")

    def _find_open_action(self, distribution: Mapping[str, float]) -> str | None:
        """识别 open 场景的激进行动名称.

        Args:
            distribution: 当前动作分布.

        Returns:
            open 对应的动作名, 若不存在则返回 None.
        """

        if "OPEN" in distribution:
            return "OPEN"
        return self._find_aggressive_action(distribution)

    def _find_aggressive_action(self, distribution: Mapping[str, float]) -> str | None:
        """识别首个激进行动名称.

        Args:
            distribution: 当前动作分布.

        Returns:
            首个非 `FOLD/CALL/CHECK` 的动作名, 若不存在则返回 None.
        """

        passive_actions = {"FOLD", "CALL", "CHECK"}
        for action_name in self._base_policy.action_names:
            if action_name not in passive_actions and action_name in distribution:
                return action_name
        return None

    def _shift_mass(
        self,
        *,
        distribution: dict[str, float],
        target_action: str,
        source_actions: tuple[str, ...],
        amount: float,
    ) -> float:
        """把概率质量从被动动作搬移到目标动作.

        Args:
            distribution: 当前动作分布.
            target_action: 需要提升的动作.
            source_actions: 允许扣减的来源动作.
            amount: 计划搬移的概率质量.

        Returns:
            实际搬移的概率质量.
        """

        if amount <= _EPSILON:
            return 0.0

        remaining = amount
        moved = 0.0
        for source_action in source_actions:
            source_value = distribution.get(source_action, 0.0)
            if source_value <= _EPSILON:
                continue

            shift = min(source_value, remaining)
            distribution[source_action] = source_value - shift
            remaining -= shift
            moved += shift
            if remaining <= _EPSILON:
                break

        distribution[target_action] = distribution.get(target_action, 0.0) + moved
        return moved

    def _normalize_distribution(
        self,
        distribution: Mapping[str, float],
    ) -> dict[str, float]:
        """归一化动作分布.

        Args:
            distribution: 待归一化分布.

        Returns:
            归一化后的新分布.
        """

        total = sum(max(0.0, value) for value in distribution.values())
        if total <= _EPSILON:
            uniform_weight = 1.0 / len(distribution)
            return {
                action_name: uniform_weight
                for action_name in distribution
            }

        return {
            action_name: max(0.0, value) / total
            for action_name, value in distribution.items()
        }

    def _infer_size_bb(
        self,
        *,
        hero_state: PreflopDecisionState,
        recommended_action: str,
    ) -> float | None:
        """推断推荐动作的最小尺寸.

        Args:
            hero_state: 当前 Hero 翻前共享状态.
            recommended_action: 推荐动作名称.

        Returns:
            推荐总尺度, 单位 BB. 被动动作返回 None.
        """

        if recommended_action in {"FOLD", "CALL", "CHECK"}:
            return None

        if hero_state.action_family == ActionFamily.OPEN:
            return 2.5

        if hero_state.action_family == ActionFamily.LIMP:
            return 3.0 + max(float(hero_state.limp_count), 1.0)

        return hero_state.raise_size_bb


__all__ = [
    "HeroDecision",
    "HeroOpponentContext",
    "PreflopHeroEngine",
]
