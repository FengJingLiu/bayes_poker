"""Hero 翻前决策引擎测试."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

from bayes_poker.strategy.preflop_engine.policy_calibrator import (
    ActionPolicy,
    ActionPolicyAction,
)
from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    PreflopDecisionState,
)
from bayes_poker.strategy.preflop_engine.tendency import PlayerTendencyProfile
from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH
from bayes_poker.table.layout.base import Position as TablePosition


def _load_hero_engine_module() -> ModuleType:
    """加载 Hero 决策引擎模块.

    Returns:
        Hero 决策引擎模块对象.
    """

    try:
        return importlib.import_module("bayes_poker.strategy.preflop_engine.hero_engine")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少 Hero 决策引擎模块: {exc}")


def _build_range(default_frequency: float) -> PreflopRange:
    """构造测试使用的统一频率范围.

    Args:
        default_frequency: 全部 169 手牌共享的默认频率.

    Returns:
        测试用 PreflopRange.
    """

    return PreflopRange(
        strategy=[default_frequency] * RANGE_169_LENGTH,
        evs=[0.0] * RANGE_169_LENGTH,
    )


def _build_policy(action_frequencies: dict[str, float]) -> ActionPolicy:
    """构造测试使用的基础策略.

    Args:
        action_frequencies: 每个动作的基础总频率.

    Returns:
        测试用 ActionPolicy.
    """

    return ActionPolicy(
        actions=tuple(
            ActionPolicyAction(
                action_name=action_name,
                range=_build_range(default_frequency=frequency),
            )
            for action_name, frequency in action_frequencies.items()
        )
    )


def test_hero_engine_widens_btn_steal_against_under_defending_blinds() -> None:
    """测试 Hero 引擎会在盲位防守不足时扩宽 BTN steal."""

    hero_engine_module = _load_hero_engine_module()
    hero_engine = hero_engine_module.PreflopHeroEngine(
        base_policy=_build_policy(
            {
                "FOLD": 0.52,
                "OPEN": 0.48,
            }
        )
    )

    result = hero_engine.decide(
        hero_state=PreflopDecisionState(
            action_family=ActionFamily.OPEN,
            actor_position=TablePosition.BTN,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_size_bb=None,
        ),
        opponents={
            TablePosition.SB: hero_engine_module.HeroOpponentContext(
                tendency_profile=PlayerTendencyProfile(
                    open_freq=0.12,
                    call_freq=0.05,
                    confidence=1.0,
                )
            ),
            TablePosition.BB: hero_engine_module.HeroOpponentContext(
                tendency_profile=PlayerTendencyProfile(
                    open_freq=0.10,
                    call_freq=0.08,
                    confidence=1.0,
                )
            ),
        },
    )

    assert result.recommended_action == "OPEN"
    assert sum(result.action_distribution.values()) == pytest.approx(1.0)


def test_hero_engine_does_not_widen_btn_steal_against_aggressive_blinds() -> None:
    """测试低跟注但高激进盲位不会被误判为防守不足."""

    hero_engine_module = _load_hero_engine_module()
    hero_engine = hero_engine_module.PreflopHeroEngine(
        base_policy=_build_policy(
            {
                "FOLD": 0.52,
                "OPEN": 0.48,
            }
        )
    )

    result = hero_engine.decide(
        hero_state=PreflopDecisionState(
            action_family=ActionFamily.OPEN,
            actor_position=TablePosition.BTN,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_size_bb=None,
        ),
        opponents={
            TablePosition.SB: hero_engine_module.HeroOpponentContext(
                tendency_profile=PlayerTendencyProfile(
                    open_freq=0.32,
                    call_freq=0.05,
                    confidence=1.0,
                )
            ),
            TablePosition.BB: hero_engine_module.HeroOpponentContext(
                tendency_profile=PlayerTendencyProfile(
                    open_freq=0.28,
                    call_freq=0.08,
                    confidence=1.0,
                )
            ),
        },
    )

    assert result.recommended_action == "FOLD"
    assert "防守偏弱" not in result.explanation.summary


def test_hero_engine_explains_iso_adjustment_against_limp_fold_player() -> None:
    """测试 Hero 引擎会解释针对 limp-fold 对手的 ISO 调整."""

    hero_engine_module = _load_hero_engine_module()
    hero_engine = hero_engine_module.PreflopHeroEngine(
        base_policy=_build_policy(
            {
                "FOLD": 0.40,
                "CALL": 0.35,
                "ISO_RAISE": 0.25,
            }
        )
    )

    result = hero_engine.decide(
        hero_state=PreflopDecisionState(
            action_family=ActionFamily.LIMP,
            actor_position=TablePosition.CO,
            aggressor_position=None,
            call_count=0,
            limp_count=1,
            raise_size_bb=None,
        ),
        opponents={
            TablePosition.UTG: hero_engine_module.HeroOpponentContext(
                limp_fold_frequency=0.78,
                is_limper=True,
            )
        },
    )

    assert result.recommended_action == "ISO_RAISE"
    assert "limp-fold" in result.explanation.summary


def test_hero_engine_ignores_high_limp_fold_player_when_not_limper() -> None:
    """测试非 limper 的高 limp-fold 频率不会触发 ISO 调整."""

    hero_engine_module = _load_hero_engine_module()
    hero_engine = hero_engine_module.PreflopHeroEngine(
        base_policy=_build_policy(
            {
                "FOLD": 0.40,
                "CALL": 0.35,
                "ISO_RAISE": 0.25,
            }
        )
    )

    result = hero_engine.decide(
        hero_state=PreflopDecisionState(
            action_family=ActionFamily.LIMP,
            actor_position=TablePosition.CO,
            aggressor_position=None,
            call_count=0,
            limp_count=1,
            raise_size_bb=None,
        ),
        opponents={
            TablePosition.UTG: hero_engine_module.HeroOpponentContext(
                limp_fold_frequency=0.90,
                is_limper=False,
            ),
            TablePosition.MP: hero_engine_module.HeroOpponentContext(
                limp_fold_frequency=0.20,
                is_limper=True,
            ),
        },
    )

    assert result.recommended_action == "FOLD"
    assert "limp-fold" not in result.explanation.summary


def test_hero_engine_raises_from_check_branch_against_limp_fold_limper() -> None:
    """测试 BB 的 CHECK/ISO_RAISE 分支也会因 limp-fold 倾向而提频."""

    hero_engine_module = _load_hero_engine_module()
    hero_engine = hero_engine_module.PreflopHeroEngine(
        base_policy=_build_policy(
            {
                "CHECK": 0.60,
                "ISO_RAISE": 0.40,
            }
        )
    )

    result = hero_engine.decide(
        hero_state=PreflopDecisionState(
            action_family=ActionFamily.LIMP,
            actor_position=TablePosition.BB,
            aggressor_position=None,
            call_count=0,
            limp_count=1,
            raise_size_bb=None,
        ),
        opponents={
            TablePosition.BTN: hero_engine_module.HeroOpponentContext(
                limp_fold_frequency=0.75,
                is_limper=True,
            )
        },
    )

    assert result.recommended_action == "ISO_RAISE"
    assert "limp-fold" in result.explanation.summary
