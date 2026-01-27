import json
import tempfile
from pathlib import Path

import pytest

from bayes_poker.strategy.preflop_parse import (
    STRATEGY_VECTOR_LENGTH,
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
    normalize_token,
    parse_all_strategies,
    parse_bet_size_from_code,
    parse_file_meta,
    parse_strategy_directory,
    parse_strategy_node,
    split_history_tokens,
)


class TestParseBetSizeFromCode:
    def test_raise_with_size(self) -> None:
        assert parse_bet_size_from_code("R2") == 2.0
        assert parse_bet_size_from_code("R2.5") == 2.5
        assert parse_bet_size_from_code("R17.5") == 17.5
        assert parse_bet_size_from_code("r3") == 3.0

    def test_rai_returns_none(self) -> None:
        assert parse_bet_size_from_code("RAI") is None
        assert parse_bet_size_from_code("rai") is None

    def test_fold_call_returns_none(self) -> None:
        assert parse_bet_size_from_code("F") is None
        assert parse_bet_size_from_code("C") is None

    def test_empty_returns_none(self) -> None:
        assert parse_bet_size_from_code("") is None


class TestNormalizeToken:
    def test_raise_variants(self) -> None:
        assert normalize_token("R2") == "R"
        assert normalize_token("R17.5") == "R"
        assert normalize_token("RAI") == "R"
        assert normalize_token("rai") == "R"

    def test_fold_call(self) -> None:
        assert normalize_token("F") == "F"
        assert normalize_token("C") == "C"
        assert normalize_token("c") == "C"

    def test_empty(self) -> None:
        assert normalize_token("") == ""


class TestSplitHistoryTokens:
    def test_multiple_tokens(self) -> None:
        tokens = split_history_tokens("F-R2-R6.5-F-R17.5-R35-RAI-C")
        assert tokens == ["F", "R2", "R6.5", "F", "R17.5", "R35", "RAI", "C"]

    def test_single_token(self) -> None:
        assert split_history_tokens("R2") == ["R2"]

    def test_empty(self) -> None:
        assert split_history_tokens("") == []
        assert split_history_tokens("   ") == []


class TestParseFileMeta:
    def test_root_file(self) -> None:
        result = parse_file_meta("Cash6m50zGeneral", "Cash6m50zGeneral_100")
        assert result == (100, "")

    def test_with_history(self) -> None:
        result = parse_file_meta(
            "Cash6m50zGeneral", "Cash6m50zGeneral_100_F-R2-R6.5-F-R17.5-R35-RAI-C"
        )
        assert result == (100, "F-R2-R6.5-F-R17.5-R35-RAI-C")

    def test_wrong_prefix(self) -> None:
        result = parse_file_meta("Cash6m50zGeneral", "OtherStrategy_100")
        assert result is None

    def test_invalid_stack(self) -> None:
        result = parse_file_meta("Cash6m50zGeneral", "Cash6m50zGeneral_abc")
        assert result is None


class TestParseStrategyNode:
    def test_valid_json(self) -> None:
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
                    "total_frequency": 0.824,
                    "total_ev": 0.085,
                    "total_combos": 1092.7,
                    "strategy": [0.82] * STRATEGY_VECTOR_LENGTH,
                    "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                },
                {
                    "action": {
                        "code": "R2",
                        "position": "UTG",
                        "type": "RAISE",
                        "next_position": "HJ",
                        "allin": False,
                    },
                    "total_frequency": 0.176,
                    "total_ev": 0.085,
                    "total_combos": 233.3,
                    "strategy": [0.18] * STRATEGY_VECTOR_LENGTH,
                    "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                },
            ]
        }

        node = parse_strategy_node(data, "", "test.json")

        assert node is not None
        assert node.history_full == ""
        assert node.history_actions == ""
        assert node.history_token_count == 0
        assert node.acting_position == "UTG"
        assert len(node.actions) == 2

        fold_action = node.actions[0]
        assert fold_action.action_code == "F"
        assert fold_action.action_type == "FOLD"
        assert fold_action.bet_size_bb is None
        assert fold_action.is_all_in is False
        assert fold_action.total_frequency == pytest.approx(0.824)

        raise_action = node.actions[1]
        assert raise_action.action_code == "R2"
        assert raise_action.bet_size_bb == 2.0
        assert raise_action.is_all_in is False

    def test_with_history(self) -> None:
        data = {
            "solutions": [
                {
                    "action": {
                        "code": "C",
                        "position": "BB",
                        "type": "CALL",
                        "next_position": "",
                        "allin": True,
                    },
                    "total_frequency": 0.5,
                    "total_ev": 9.5,
                    "total_combos": 8.5,
                    "strategy": [0.5] * STRATEGY_VECTOR_LENGTH,
                    "evs": [-0.04] * STRATEGY_VECTOR_LENGTH,
                },
            ]
        }

        node = parse_strategy_node(data, "F-R2-RAI", "test.json")

        assert node is not None
        assert node.history_full == "F-R2-RAI"
        assert node.history_actions == "F-R-R"
        assert node.history_token_count == 3

    def test_empty_solutions(self) -> None:
        data = {"solutions": []}
        node = parse_strategy_node(data, "", "test.json")
        assert node is None


class TestPreflopStrategy:
    def test_add_and_get_node(self) -> None:
        strategy = PreflopStrategy(name="TestStrategy", source_dir="/test")

        node = StrategyNode(
            history_full="",
            history_actions="",
            history_token_count=0,
            acting_position="UTG",
            source_file="test.json",
            actions=(),
        )

        strategy.add_node(100, node)

        retrieved = strategy.get_node(100, "")
        assert retrieved is node

        assert strategy.get_node(100, "nonexistent") is None
        assert strategy.get_node(50, "") is None

    def test_stack_sizes(self) -> None:
        strategy = PreflopStrategy(name="Test", source_dir="/test")

        node = StrategyNode(
            history_full="",
            history_actions="",
            history_token_count=0,
            acting_position="UTG",
            source_file="test.json",
            actions=(),
        )

        strategy.add_node(100, node)
        strategy.add_node(50, node)
        strategy.add_node(200, node)

        assert strategy.stack_sizes() == [50, 100, 200]

    def test_node_count(self) -> None:
        strategy = PreflopStrategy(name="Test", source_dir="/test")

        node1 = StrategyNode(
            history_full="",
            history_actions="",
            history_token_count=0,
            acting_position="UTG",
            source_file="test1.json",
            actions=(),
        )
        node2 = StrategyNode(
            history_full="F-R2",
            history_actions="F-R",
            history_token_count=2,
            acting_position="HJ",
            source_file="test2.json",
            actions=(),
        )

        strategy.add_node(100, node1)
        strategy.add_node(100, node2)
        strategy.add_node(50, node1)

        assert strategy.node_count(100) == 2
        assert strategy.node_count(50) == 1
        assert strategy.node_count() == 3


class TestParseStrategyDirectory:
    def test_parse_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_dir = Path(tmpdir) / "TestStrategy"
            strategy_dir.mkdir()

            root_data = {
                "solutions": [
                    {
                        "action": {
                            "code": "F",
                            "position": "UTG",
                            "type": "FOLD",
                            "next_position": "HJ",
                        },
                        "total_frequency": 0.8,
                        "strategy": [0.8] * STRATEGY_VECTOR_LENGTH,
                        "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                    }
                ]
            }

            (strategy_dir / "TestStrategy_100.json").write_text(
                json.dumps(root_data), encoding="utf-8"
            )

            history_data = {
                "solutions": [
                    {
                        "action": {
                            "code": "C",
                            "position": "HJ",
                            "type": "CALL",
                            "next_position": "CO",
                        },
                        "total_frequency": 0.5,
                        "strategy": [0.5] * STRATEGY_VECTOR_LENGTH,
                        "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                    }
                ]
            }

            (strategy_dir / "TestStrategy_100_F-R2.json").write_text(
                json.dumps(history_data), encoding="utf-8"
            )

            strategy = parse_strategy_directory(strategy_dir)

            assert strategy.name == "TestStrategy"
            assert strategy.node_count() == 2
            assert strategy.stack_sizes() == [100]

            root_node = strategy.get_node(100, "")
            assert root_node is not None
            assert root_node.acting_position == "UTG"

            history_node = strategy.get_node(100, "F-R2")
            assert history_node is not None
            assert history_node.history_actions == "F-R"


class TestParseAllStrategies:
    def test_parse_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            strategy1_dir = root / "Strategy1"
            strategy1_dir.mkdir()
            (strategy1_dir / "Strategy1_100.json").write_text(
                json.dumps(
                    {
                        "solutions": [
                            {
                                "action": {
                                    "code": "F",
                                    "position": "UTG",
                                    "type": "FOLD",
                                },
                                "total_frequency": 0.8,
                                "strategy": [0.8] * STRATEGY_VECTOR_LENGTH,
                                "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            strategy2_dir = root / "Strategy2"
            strategy2_dir.mkdir()
            (strategy2_dir / "Strategy2_100.json").write_text(
                json.dumps(
                    {
                        "solutions": [
                            {
                                "action": {
                                    "code": "R2",
                                    "position": "UTG",
                                    "type": "RAISE",
                                },
                                "total_frequency": 0.2,
                                "strategy": [0.2] * STRATEGY_VECTOR_LENGTH,
                                "evs": [0.1] * STRATEGY_VECTOR_LENGTH,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            strategies = parse_all_strategies(root)

            assert len(strategies) == 2
            names = {s.name for s in strategies}
            assert names == {"Strategy1", "Strategy2"}

    def test_filter_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            for name in ["StrategyA", "StrategyB", "StrategyC"]:
                d = root / name
                d.mkdir()
                (d / f"{name}_100.json").write_text(
                    json.dumps(
                        {
                            "solutions": [
                                {
                                    "action": {
                                        "code": "F",
                                        "position": "UTG",
                                        "type": "FOLD",
                                    },
                                    "total_frequency": 0.8,
                                    "strategy": [0.8] * STRATEGY_VECTOR_LENGTH,
                                    "evs": [0.0] * STRATEGY_VECTOR_LENGTH,
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            strategies = parse_all_strategies(
                root, strategy_filters=["StrategyA", "StrategyC"]
            )

            assert len(strategies) == 2
            names = {s.name for s in strategies}
            assert names == {"StrategyA", "StrategyC"}
