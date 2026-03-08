"""翻前 solver 节点映射与先验读取测试."""

from __future__ import annotations

from pathlib import Path

import pytest

import bayes_poker.strategy.preflop_engine.mapper as mapper_module
from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_engine.mapper import (
    MappedSolverContext,
    PreflopNodeMapper,
)
from bayes_poker.strategy.preflop_engine.solver_prior import SolverPriorBuilder
from bayes_poker.strategy.preflop_engine.state import (
    ActionFamily,
    PreflopDecisionState,
)
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.domain.table import Position as TablePosition


def _make_action_record(
    *,
    order_index: int,
    action_code: str,
    action_type: str,
    bet_size_bb: float | None,
    total_frequency: float,
) -> ParsedStrategyActionRecord:
    """构造测试用动作记录."""

    return ParsedStrategyActionRecord(
        order_index=order_index,
        action_code=action_code,
        action_type=action_type,
        bet_size_bb=bet_size_bb,
        is_all_in=False,
        total_frequency=total_frequency,
        next_position="",
        preflop_range=PreflopRange.zeros(),
        total_ev=0.0,
        total_combos=0.0,
    )


def _make_node_record(
    *,
    history_full: str,
    history_actions: str,
    acting_position: TablePosition,
    action_family: ActionFamily,
    aggressor_position: TablePosition | None,
    call_count: int,
    limp_count: int,
    raise_size_bb: float | None,
    is_in_position: bool | None,
) -> ParsedStrategyNodeRecord:
    """构造测试用节点记录."""

    return ParsedStrategyNodeRecord(
        stack_bb=100,
        history_full=history_full,
        history_actions=history_actions,
        history_token_count=len([token for token in history_full.split("-") if token]),
        acting_position=acting_position.value,
        source_file="test.json",
        action_family=action_family,
        actor_position=acting_position,
        aggressor_position=aggressor_position,
        call_count=call_count,
        limp_count=limp_count,
        raise_size_bb=raise_size_bb,
        is_in_position=is_in_position,
    )


def _build_repository(
    tmp_path: Path,
    *,
    include_call_vs_open: bool = True,
    include_limp: bool = False,
) -> tuple[PreflopStrategyRepository, int, dict[str, int]]:
    """构造用于 mapper 与 solver prior 测试的 sqlite 仓库."""

    repo = PreflopStrategyRepository(tmp_path / "preflop_strategy.db")
    repo.connect()
    source_id = repo.upsert_source(
        strategy_name="TestStrategy",
        source_dir="/tmp/TestStrategy",
        format_version=1,
    )

    node_records: list[ParsedStrategyNodeRecord] = []
    node_actions: dict[str, tuple[ParsedStrategyActionRecord, ...]] = {}

    if include_call_vs_open:
        node_records.append(
            _make_node_record(
                history_full="R2-C",
                history_actions="R-C",
                acting_position=TablePosition.CO,
                action_family=ActionFamily.CALL_VS_OPEN,
                aggressor_position=TablePosition.UTG,
                call_count=1,
                limp_count=0,
                raise_size_bb=2.0,
                is_in_position=True,
            )
        )
        node_actions["R2-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.10,
            ),
            _make_action_record(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                total_frequency=0.80,
            ),
            _make_action_record(
                order_index=2,
                action_code="R9.5",
                action_type="RAISE",
                bet_size_bb=9.5,
                total_frequency=0.10,
            ),
        )
        node_records.append(
            _make_node_record(
                history_full="R2.5-C",
                history_actions="R-C",
                acting_position=TablePosition.CO,
                action_family=ActionFamily.CALL_VS_OPEN,
                aggressor_position=TablePosition.UTG,
                call_count=1,
                limp_count=0,
                raise_size_bb=2.5,
                is_in_position=True,
            )
        )
        node_actions["R2.5-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.90,
            ),
            _make_action_record(
                order_index=1,
                action_code="R9.5",
                action_type="RAISE",
                bet_size_bb=9.5,
                total_frequency=0.10,
            ),
        )

    node_records.append(
        _make_node_record(
            history_full="F-F-F-R2",
            history_actions="F-F-F-R",
            acting_position=TablePosition.SB,
            action_family=ActionFamily.OPEN,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_size_bb=None,
            is_in_position=None,
        )
    )
    node_actions["F-F-F-R2"] = (
        _make_action_record(
            order_index=0,
            action_code="F",
            action_type="FOLD",
            bet_size_bb=None,
            total_frequency=0.40,
        ),
        _make_action_record(
            order_index=1,
            action_code="C",
            action_type="CALL",
            bet_size_bb=None,
            total_frequency=0.60,
        ),
    )

    if include_limp:
        node_records.append(
            _make_node_record(
                history_full="F-C",
                history_actions="F-C",
                acting_position=TablePosition.CO,
                action_family=ActionFamily.LIMP,
                aggressor_position=None,
                call_count=0,
                limp_count=1,
                raise_size_bb=None,
                is_in_position=None,
            )
        )
        node_actions["F-C"] = (
            _make_action_record(
                order_index=0,
                action_code="F",
                action_type="FOLD",
                bet_size_bb=None,
                total_frequency=0.20,
            ),
            _make_action_record(
                order_index=1,
                action_code="C",
                action_type="CALL",
                bet_size_bb=None,
                total_frequency=0.50,
            ),
            _make_action_record(
                order_index=2,
                action_code="R4",
                action_type="RAISE",
                bet_size_bb=4.0,
                total_frequency=0.30,
            ),
        )

    node_ids = repo.insert_nodes(source_id=source_id, node_records=tuple(node_records))
    for history_full, action_records in node_actions.items():
        repo.insert_actions(
            node_id=node_ids[history_full],
            action_records=action_records,
        )
    return repo, source_id, node_ids


def _build_state(*, raise_size_bb: float = 2.0) -> PreflopDecisionState:
    """构造 cold call vs open 的测试状态."""

    return PreflopDecisionState(
        action_family=ActionFamily.CALL_VS_OPEN,
        actor_position=TablePosition.CO,
        aggressor_position=TablePosition.UTG,
        call_count=1,
        limp_count=0,
        raise_size_bb=raise_size_bb,
    )


def _build_limp_state() -> PreflopDecisionState:
    """构造 limp family 的测试状态."""

    return PreflopDecisionState(
        action_family=ActionFamily.LIMP,
        actor_position=TablePosition.CO,
        aggressor_position=None,
        call_count=0,
        limp_count=1,
        raise_size_bb=None,
    )


def _limp_template_kind() -> object:
    """读取 limp family 对应的结构化模板枚举值."""

    return mapper_module.SyntheticTemplateKind.LIMP_FAMILY_LEVEL_3


def _get_blended_frequency(policy: object, action_name: str) -> float:
    """读取指定动作的聚合频率."""

    for action in policy.actions:
        if action.action_name == action_name:
            return action.blended_frequency
    raise AssertionError(f"未找到动作: {action_name}")


def test_mapper_reads_candidates_from_repository(tmp_path: Path) -> None:
    """测试 mapper 从 sqlite repository 读取候选节点."""

    repo, source_id, node_ids = _build_repository(tmp_path)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(_build_state())

    assert context.matched_level == 2
    assert context.matched_node_id == node_ids["R2-C"]
    assert context.matched_history == "R2-C"
    assert context.candidate_node_ids == (
        node_ids["R2-C"],
        node_ids["R2.5-C"],
    )
    assert context.candidate_histories == ("R2-C", "R2.5-C")
    assert context.candidate_distances[0] < context.candidate_distances[1]
    repo.close()


def test_mapper_prefers_closer_raise_size_within_same_family(tmp_path: Path) -> None:
    """测试同动作族节点会优先匹配尺度更接近的候选."""

    repo, source_id, node_ids = _build_repository(tmp_path)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(_build_state(raise_size_bb=2.45))

    assert context.matched_node_id == node_ids["R2.5-C"]
    assert context.candidate_node_ids == (
        node_ids["R2.5-C"],
        node_ids["R2-C"],
    )
    assert context.candidate_histories == ("R2.5-C", "R2-C")
    assert context.candidate_distances[0] < context.candidate_distances[1]
    repo.close()


def test_mapper_applies_price_adjustment_for_larger_open_size(tmp_path: Path) -> None:
    """测试更大的真实 open 尺度会触发最小价格修正标记."""

    repo, source_id, node_ids = _build_repository(tmp_path)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(_build_state(raise_size_bb=3.0))

    assert context.matched_node_id == node_ids["R2.5-C"]
    assert context.price_adjustment_applied is True
    assert context.price_adjustment_factor < 1.0
    repo.close()


def test_mapper_raises_when_no_same_family_candidate_exists(tmp_path: Path) -> None:
    """测试没有同动作族候选时映射器会拒绝映射."""

    repo, source_id, _ = _build_repository(tmp_path, include_call_vs_open=False)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    with pytest.raises(ValueError, match="同动作族"):
        mapper.map_state(_build_state())
    repo.close()


def test_mapper_falls_back_to_synthetic_template_for_limp_family(tmp_path: Path) -> None:
    """测试 limp family 在无同族 solver 节点时回退到 synthetic template."""

    repo, source_id, _ = _build_repository(tmp_path, include_limp=False)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(_build_limp_state())

    assert context.matched_level == 3
    assert context.synthetic_template_kind is _limp_template_kind()
    assert context.candidate_node_ids == ()
    repo.close()


def test_mapper_prefers_real_limp_candidate_before_synthetic_fallback(
    tmp_path: Path,
) -> None:
    """测试存在 limp 同族节点时应命中真实节点而非 synthetic."""

    repo, source_id, node_ids = _build_repository(tmp_path, include_limp=True)
    mapper = PreflopNodeMapper(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )

    context = mapper.map_state(_build_limp_state())

    assert context.matched_level == 2
    assert context.matched_node_id == node_ids["F-C"]
    assert context.matched_history == "F-C"
    assert context.synthetic_template_kind is None
    repo.close()


def test_solver_prior_batches_actions_by_candidate_node_ids(tmp_path: Path) -> None:
    """测试 solver prior 基于 candidate node_id 批量读取并聚合动作."""

    repo, source_id, node_ids = _build_repository(tmp_path)
    solver_prior = SolverPriorBuilder(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )
    context = MappedSolverContext(
        matched_level=2,
        matched_node_id=node_ids["R2-C"],
        matched_history="R2-C",
        distance_score=0.0,
        candidate_node_ids=(node_ids["R2.5-C"], node_ids["R2-C"]),
        candidate_histories=("R2.5-C", "R2-C"),
        candidate_distances=(5.0, 0.0),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=None,
    )

    policy = solver_prior.build_policy(context)

    assert policy.action_names == ("F", "C", "R9.5")
    assert _get_blended_frequency(policy, "C") > _get_blended_frequency(policy, "F")
    repo.close()


def test_solver_prior_preserves_frequencies_and_exposes_price_signal(
    tmp_path: Path,
) -> None:
    """测试 solver prior 透传价格修正 signal, 但不直接改动作频率."""

    repo, source_id, node_ids = _build_repository(tmp_path)
    solver_prior = SolverPriorBuilder(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )
    base_context = MappedSolverContext(
        matched_level=2,
        matched_node_id=node_ids["R2.5-C"],
        matched_history="R2.5-C",
        distance_score=0.0,
        candidate_node_ids=(node_ids["R2.5-C"],),
        candidate_histories=("R2.5-C",),
        candidate_distances=(0.0,),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=None,
    )
    adjusted_context = MappedSolverContext(
        matched_level=2,
        matched_node_id=node_ids["R2.5-C"],
        matched_history="R2.5-C",
        distance_score=0.0,
        candidate_node_ids=(node_ids["R2.5-C"],),
        candidate_histories=("R2.5-C",),
        candidate_distances=(0.0,),
        price_adjustment_applied=True,
        price_adjustment_factor=0.75,
        synthetic_template_kind=None,
    )

    base_policy = solver_prior.build_policy(base_context)
    adjusted_policy = solver_prior.build_policy(adjusted_context)

    assert adjusted_policy.price_adjustment_applied is True
    assert adjusted_policy.price_adjustment_factor == pytest.approx(0.75)
    assert _get_blended_frequency(adjusted_policy, "R9.5") == pytest.approx(
        _get_blended_frequency(base_policy, "R9.5"),
    )
    assert _get_blended_frequency(adjusted_policy, "F") == pytest.approx(
        _get_blended_frequency(base_policy, "F"),
    )
    repo.close()


def test_solver_prior_uses_synthetic_template_policy(tmp_path: Path) -> None:
    """测试存在结构化 synthetic template 时直接返回模板先验策略."""

    repo, source_id, _ = _build_repository(tmp_path, include_call_vs_open=False)
    solver_prior = SolverPriorBuilder(
        repository=repo,
        source_id=source_id,
        stack_bb=100,
    )
    context = MappedSolverContext(
        matched_level=3,
        matched_node_id=None,
        matched_history="",
        distance_score=0.0,
        candidate_node_ids=(),
        candidate_histories=(),
        candidate_distances=(),
        price_adjustment_applied=False,
        price_adjustment_factor=1.0,
        synthetic_template_kind=_limp_template_kind(),
    )

    policy = solver_prior.build_policy(context)

    assert policy.action_names == ("F", "C", "R4")
    assert policy.synthetic_template_kind is _limp_template_kind()
    assert _get_blended_frequency(policy, "C") == pytest.approx(0.5)
    repo.close()
