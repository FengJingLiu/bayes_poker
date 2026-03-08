"""翻前策略结构化记录解析测试。"""

from __future__ import annotations

import pytest

from bayes_poker.domain.table import Position as TablePosition
from bayes_poker.strategy.preflop_engine.state import ActionFamily
from bayes_poker.strategy.preflop_parse.parser import parse_strategy_node_records


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
    assert node_record.actor_position == TablePosition.CO
    assert node_record.aggressor_position == TablePosition.UTG
    assert node_record.call_count == 1
    assert node_record.limp_count == 0
    assert node_record.raise_size_bb == pytest.approx(2.0)
    assert node_record.is_in_position is True
    assert len(action_records) == 2
    assert action_records[0].action_code == "F"
    assert action_records[1].action_code == "C"
