"""翻前策略结构化记录解析测试。"""

from __future__ import annotations

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.strategy_engine.core_types import ActionFamily
from bayes_poker.strategy.preflop_parse.parser import (
    _derive_mapper_fields,
    parse_strategy_node_records,
)


def test_parse_strategy_node_records_extracts_mapper_fields() -> None:
    """应从节点历史中提取 mapper 所需的结构化字段。"""

    data = {
        "solutions": [
            {
                "action": {
                    "code": "F",
                    "position": "CO",
                    "type": "FOLD",
                    "next_position": "",
                    "allin": False,
                },
                "total_frequency": 0.2,
                "total_ev": 0.0,
                "total_combos": 10.0,
                "strategy": [0.2] * 169,
                "evs": [0.0] * 169,
            },
            {
                "action": {
                    "code": "C",
                    "position": "CO",
                    "type": "CALL",
                    "next_position": "",
                    "allin": False,
                },
                "total_frequency": 0.8,
                "total_ev": 0.1,
                "total_combos": 30.0,
                "strategy": [0.8] * 169,
                "evs": [0.1] * 169,
            },
        ]
    }

    records = parse_strategy_node_records(
        stack_bb=100,
        data=data,
        history_full="R2-C",
        source_file="test.json",
    )

    assert records is not None
    node_record, action_records = records
    assert node_record.stack_bb == 100
    assert node_record.history_full == "R2-C"
    assert node_record.history_actions == "R-C"
    assert node_record.action_family == ActionFamily.CALL_VS_OPEN
    assert node_record.actor_position == Position.CO
    assert node_record.aggressor_position == Position.UTG
    assert node_record.call_count == 1
    assert node_record.limp_count == 0
    assert node_record.raise_time == 1
    assert node_record.pot_size == pytest.approx(5.5)
    assert node_record.raise_size_bb == pytest.approx(2.0)
    assert node_record.is_in_position is True
    assert len(action_records) == 2
    assert action_records[0].action_code == "F"
    assert action_records[1].action_code == "C"


@pytest.mark.parametrize(
    ("acting_position", "history_full", "expected_family"),
    [
        ("UTG", "", ActionFamily.OPEN),
        ("CO", "F-C", ActionFamily.LIMP),
        ("BTN", "F-C-C", ActionFamily.OVERLIMP),
        ("BTN", "F-C-R4", ActionFamily.ISO_RAISE),
        ("CO", "R2-C", ActionFamily.CALL_VS_OPEN),
        ("CO", "R2-R7", ActionFamily.CALL_VS_3BET),
        ("BTN", "R2-C-R8", ActionFamily.SQUEEZE),
        ("BTN", "R2-R7-R16", ActionFamily.FOUR_BET),
        ("BTN", "R2-R7-RAI", ActionFamily.JAM),
    ],
)
def test_derive_mapper_fields_supports_extended_histories(
    acting_position: str,
    history_full: str,
    expected_family: ActionFamily,
) -> None:
    """应根据复杂历史推导扩展动作族。"""

    action_family, actor_position, _, _, _, raise_time, pot_size, *_ = (
        _derive_mapper_fields(
            acting_position=acting_position,
            history_full=history_full,
        )
    )

    assert actor_position is not None
    assert action_family == expected_family
    assert raise_time >= 0
    assert pot_size >= 1.5


@pytest.mark.parametrize(
    ("state_label", "expected_family"),
    [
        ("FOLD", ActionFamily.FOLD),
        ("LIMP", ActionFamily.LIMP),
        ("OVERLIMP", ActionFamily.OVERLIMP),
        ("OPEN", ActionFamily.OPEN),
        ("ISO_RAISE", ActionFamily.ISO_RAISE),
        ("CALL_VS_OPEN", ActionFamily.CALL_VS_OPEN),
        ("CALL_VS_3BET", ActionFamily.CALL_VS_3BET),
        ("THREE_BET", ActionFamily.THREE_BET),
        ("SQUEEZE", ActionFamily.SQUEEZE),
        ("FOUR_BET", ActionFamily.FOUR_BET),
        ("JAM", ActionFamily.JAM),
    ],
)
def test_derive_mapper_fields_supports_all_explicit_state_labels(
    state_label: str,
    expected_family: ActionFamily,
) -> None:
    """应支持状态标签覆盖映射到完整动作族集合。"""

    action_family, actor_position, *_ = _derive_mapper_fields(
        acting_position="CO",
        history_full="R2-C",
        state_label=state_label,
    )

    assert actor_position == Position.CO
    assert action_family == expected_family
