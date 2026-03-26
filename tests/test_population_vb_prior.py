"""population_vb prior 构建测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from bayes_poker.domain.table import Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import RANGE_169_LENGTH, PreflopRange
from bayes_poker.strategy.strategy_engine.population_vb.gto_family_prior import (
    GtoFamilyPriorBuilder,
)
from bayes_poker.strategy.strategy_engine.population_vb.holdcards import (
    combo_weights_169,
)
from bayes_poker.strategy.strategy_engine.population_vb.pseudo_call_prior import (
    build_pseudo_call_prior_from_raise_ev,
)


def _constant_range(strategy_value: float, ev_value: float) -> PreflopRange:
    """构造常量 preflop range。

    Args:
        strategy_value: 策略常数。
        ev_value: EV 常数。

    Returns:
        常量 `PreflopRange`。
    """

    return PreflopRange.from_list(
        strategy=[strategy_value] * RANGE_169_LENGTH,
        evs=[ev_value] * RANGE_169_LENGTH,
    )


def test_pseudo_call_prior_places_call_between_raise_and_fold() -> None:
    """中间强度手牌应获得更高的 call 先验质量。"""
    raise_score = np.linspace(-2.0, 2.0, RANGE_169_LENGTH, dtype=np.float32)
    combo_weights = combo_weights_169()
    empirical_mix = np.array([0.45, 0.30, 0.25], dtype=np.float32)

    prior = build_pseudo_call_prior_from_raise_ev(
        raise_score=raise_score,
        combo_weights=combo_weights,
        empirical_mix_fcr=empirical_mix,
        solver_raise_share=0.25,
    )

    assert prior.shape == (RANGE_169_LENGTH, 3)
    assert np.allclose(prior.sum(axis=1), 1.0, atol=1e-6)

    mid_index = int(np.argmin(np.abs(raise_score)))
    low_index = int(np.argmin(raise_score))
    high_index = int(np.argmax(raise_score))
    assert prior[mid_index, 1] > prior[low_index, 1]
    assert prior[mid_index, 1] > prior[high_index, 1]
    assert prior[high_index, 2] > prior[mid_index, 2]


def test_pseudo_call_prior_zero_call_when_empirical_call_zero() -> None:
    """当经验 call 质量为 0 时, 先验 call 维度应收缩到 0。"""
    raise_score = np.linspace(-1.0, 1.0, RANGE_169_LENGTH, dtype=np.float32)
    combo_weights = combo_weights_169()
    empirical_mix = np.array([0.7, 0.0, 0.3], dtype=np.float32)

    prior = build_pseudo_call_prior_from_raise_ev(
        raise_score=raise_score,
        combo_weights=combo_weights,
        empirical_mix_fcr=empirical_mix,
        solver_raise_share=0.3,
    )

    assert np.allclose(prior[:, 1], 0.0, atol=1e-6)
    assert np.allclose(prior.sum(axis=1), 1.0, atol=1e-6)


def test_direct_gto_prior_kept_when_solver_has_call_action(tmp_path: Path) -> None:
    """solver 自带 call 动作时应保持 direct_gto 先验。"""
    db_path = tmp_path / "strategy.db"
    repo = PreflopStrategyRepository(db_path)
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="unit-test-source",
        source_dir=str(tmp_path),
        format_version=1,
    )

    node_record = ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full="R2",
        history_actions="R",
        history_token_count=1,
        acting_position="UTG",
        source_file="unit.json",
        action_family=None,
        actor_position=Position.UTG,
        aggressor_position=None,
        call_count=0,
        limp_count=0,
        raise_time=0,
        pot_size=1.5,
        raise_size_bb=None,
        is_in_position=None,
    )
    node_id = repo.insert_node(source_id=source_id, node_record=node_record)
    repo.insert_actions(
        node_id=node_id,
        action_records=(
            ParsedStrategyActionRecord(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.2,
                next_position="HJ",
                preflop_range=_constant_range(0.2, -1.0),
                total_ev=-1.0,
                total_combos=0.2 * 1326.0,
            ),
            ParsedStrategyActionRecord(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                is_all_in=False,
                total_frequency=0.3,
                next_position="HJ",
                preflop_range=_constant_range(0.3, 0.1),
                total_ev=0.1,
                total_combos=0.3 * 1326.0,
            ),
            ParsedStrategyActionRecord(
                order_index=2,
                action_code="R4",
                action_type="RAISE",
                bet_size_bb=4.0,
                is_all_in=False,
                total_frequency=0.5,
                next_position="HJ",
                preflop_range=_constant_range(0.5, 0.8),
                total_ev=0.8,
                total_combos=0.5 * 1326.0,
            ),
        ),
    )
    repo.close()

    builder = GtoFamilyPriorBuilder(
        strategy_db_path=str(db_path),
        source_id=source_id,
        stack_bb=100,
    )
    priors = builder.build_all(table_type=6)
    param_index = PreFlopParams(
        table_type=TableType.SIX_MAX,
        position=MetricsPosition.UTG,
        num_callers=0,
        num_raises=0,
        num_active_players=6,
        previous_action=MetricsActionType.FOLD,
        in_position_on_flop=False,
    ).to_index()

    assert param_index in priors
    prior = priors[param_index]
    assert prior.prior_kind == "direct_gto"
    assert prior.probs_fcr.shape == (RANGE_169_LENGTH, 3)
    assert np.allclose(prior.probs_fcr.sum(axis=1), 1.0, atol=1e-6)
    assert np.all(prior.probs_fcr[:, 1] > 0.0)
