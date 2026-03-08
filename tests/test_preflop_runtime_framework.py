"""翻前策略 runtime 框架测试。"""

import asyncio
import json
import tempfile
from pathlib import Path

from bayes_poker.domain.poker import ActionType
from bayes_poker.domain.table import Player
from bayes_poker.table.observed_state import create_observed_state
from bayes_poker.strategy.runtime.preflop import (
    PreflopLayer,
    create_preflop_strategy_from_directory,
    infer_preflop_layer,
)


def test_infer_preflop_layer() -> None:
    """测试翻前分层推断。"""
    assert infer_preflop_layer("") == PreflopLayer.RFI
    assert infer_preflop_layer("C") == PreflopLayer.RFI
    assert infer_preflop_layer("F-R2") == PreflopLayer.THREE_BET
    assert infer_preflop_layer("F-R2-R6") == PreflopLayer.FOUR_BET


def test_create_preflop_strategy_from_directory_smoke() -> None:
    """测试从目录创建策略并执行。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy_dir = Path(tmpdir) / "Cash6m50zGeneral"
        strategy_dir.mkdir(parents=True)

        data = {
            "solutions": [
                {
                    "action": {
                        "code": "F",
                        "position": "UTG",
                        "type": "FOLD",
                        "next_position": "HJ",
                        "allin": False,
                    },
                    "total_frequency": 1.0,
                    "total_ev": 0.0,
                    "total_combos": 0.0,
                    "strategy": [1.0] * 169,
                    "evs": [0.0] * 169,
                }
            ]
        }

        (strategy_dir / "Cash6m50zGeneral_100.json").write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        handler = create_preflop_strategy_from_directory(strategy_dir=strategy_dir)

        # 创建 ObservedTableState
        observed_state = create_observed_state(
            player_count=6,
            small_blind=0.5,
            big_blind=1.0,
        )
        observed_state.btn_seat = 0
        observed_state.hero_seat = 3  # UTG
        observed_state.hero_cards = ("As", "Ah")
        observed_state.players = [
            Player(
                seat_index=i,
                player_id=f"P{i}",
                stack=100.0,
                bet=0.0,
                is_folded=False,
            )
            for i in range(6)
        ]

        result = asyncio.run(
            handler(
                "s1",
                {
                    "state_version": 1,
                    "observed_state": observed_state,
                },
            )
        )

        assert result["state_version"] == 1
        assert "matched" in str(result.get("notes", ""))


def test_create_preflop_strategy_accepts_table_state_payload() -> None:
    """测试 runtime 支持从 table_state 反序列化输入。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy_dir = Path(tmpdir) / "Cash6m50zGeneral"
        strategy_dir.mkdir(parents=True)

        data = {
            "solutions": [
                {
                    "action": {
                        "code": "F",
                        "position": "UTG",
                        "type": "FOLD",
                        "next_position": "HJ",
                        "allin": False,
                    },
                    "total_frequency": 1.0,
                    "total_ev": 0.0,
                    "total_combos": 0.0,
                    "strategy": [1.0] * 169,
                    "evs": [0.0] * 169,
                }
            ]
        }

        (strategy_dir / "Cash6m50zGeneral_100.json").write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        handler = create_preflop_strategy_from_directory(strategy_dir=strategy_dir)

        observed_state = create_observed_state(
            player_count=6,
            small_blind=0.5,
            big_blind=1.0,
        )
        observed_state.btn_seat = 0
        observed_state.hero_seat = 3  # UTG
        observed_state.hero_cards = ("As", "Ah")
        observed_state.players = [
            Player(
                seat_index=i,
                player_id=f"P{i}",
                stack=100.0,
                bet=0.0,
                is_folded=False,
            )
            for i in range(6)
        ]

        result = asyncio.run(
            handler(
                "s1",
                {
                    "state_version": 1,
                    "table_state": observed_state.to_dict(),
                },
            )
        )

        assert result["state_version"] == 1
        assert "matched" in str(result.get("notes", ""))
