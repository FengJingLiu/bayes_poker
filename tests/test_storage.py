"""storage 模块单元测试（精简版）。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bayes_poker.storage.actions import (
    ActionType,
    extract_board_tokens,
    generate_preflop_signature,
    generate_preflop_tokens,
    parse_preflop_actions,
    PreflopAction,
)
from bayes_poker.storage.hash import compute_hand_hash
from bayes_poker.storage.models import HandPlayerRecord, HandRecord
from bayes_poker.storage.position import compute_relative_position, map_all_positions
from bayes_poker.storage.repository import HandRepository
from bayes_poker.storage.schema import SCHEMA_VERSION


class TestPosition:
    def test_6max_positions(self):
        seats = [1, 2, 3, 4, 5, 6]
        button_seat = 1
        result = map_all_positions(button_seat, 6, seats)

        assert result[1] == "BTN"
        assert result[2] == "SB"
        assert result[3] == "BB"
        assert result[4] == "UTG"
        assert result[5] == "MP"
        assert result[6] == "CO"

    def test_5max_positions(self):
        seats = [1, 2, 3, 4, 5]
        button_seat = 1
        result = map_all_positions(button_seat, 6, seats)

        assert result[1] == "BTN"
        assert result[2] == "SB"
        assert result[3] == "BB"
        assert result[4] == "UTG"
        assert result[5] == "CO"

    def test_button_not_seat_1(self):
        seats = [1, 2, 3, 4, 5, 6]
        button_seat = 3
        result = map_all_positions(button_seat, 6, seats)

        assert result[3] == "BTN"
        assert result[4] == "SB"
        assert result[5] == "BB"
        assert result[6] == "UTG"
        assert result[1] == "MP"
        assert result[2] == "CO"


class TestHash:
    def test_hash_deterministic(self):
        # 新签名：(rel_pos, player_name, starting_stack)
        snapshots = [
            ("BTN", "Player1", 200),
            ("SB", "Player2", 200),
            ("BB", "Player3", 200),
        ]
        actions = ["d dh", "cbr 6", "f", "f"]
        board = "Td4s8d"

        hash1 = compute_hand_hash(20250110, snapshots, actions, board)
        hash2 = compute_hand_hash(20250110, snapshots, actions, board)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_hash_changes_with_different_date(self):
        snapshots = [("BTN", "Player1", 200), ("SB", "Player2", 200)]
        actions = ["d dh", "cbr 6"]
        board = ""

        hash1 = compute_hand_hash(20250110, snapshots, actions, board)
        hash2 = compute_hand_hash(20250111, snapshots, actions, board)

        assert hash1 != hash2

    def test_hash_changes_with_different_player_name(self):
        snapshots1 = [("BTN", "Player1", 200), ("SB", "Player2", 200)]
        snapshots2 = [("BTN", "DifferentPlayer", 200), ("SB", "Player2", 200)]
        actions = ["d dh", "cbr 6"]
        board = ""

        hash1 = compute_hand_hash(20250110, snapshots1, actions, board)
        hash2 = compute_hand_hash(20250110, snapshots2, actions, board)

        assert hash1 != hash2

    def test_hash_sorted_by_position(self):
        # 不同顺序输入，应产生相同哈希（因为会按 SB-BB-UTG-MP-CO-BTN 排序）
        snapshots1 = [("BTN", "P1", 200), ("SB", "P2", 200), ("BB", "P3", 200)]
        snapshots2 = [("SB", "P2", 200), ("BB", "P3", 200), ("BTN", "P1", 200)]
        actions = ["d dh", "cbr 6"]
        board = ""

        hash1 = compute_hand_hash(20250110, snapshots1, actions, board)
        hash2 = compute_hand_hash(20250110, snapshots2, actions, board)

        assert hash1 == hash2


class TestActions:
    def test_extract_board_tokens(self):
        actions = [
            "d dh p1 Ah Kh",
            "d dh p2 Qh Jh",
            "cbr 6",
            "cc",
            "d db Td 4s 8d",
            "cbr 10",
            "cc",
            "d db 2h",
            "cbr 20",
            "f",
        ]
        result = extract_board_tokens(actions)
        assert result == "Td4s8d|2h"

    def test_generate_preflop_tokens(self):
        preflop_actions = [
            PreflopAction("UTG", ActionType.OPEN, 6),
            PreflopAction("BTN", ActionType.THREE_BET, 18),
            PreflopAction("UTG", ActionType.CALL),
        ]
        result = generate_preflop_tokens(preflop_actions)
        assert result == "UTG_OPEN BTN_3B UTG_CALL"

    def test_generate_preflop_signature(self):
        preflop_actions = [
            PreflopAction("UTG", ActionType.OPEN, 6),
            PreflopAction("BTN", ActionType.THREE_BET, 18),
        ]
        result = generate_preflop_signature(preflop_actions)
        assert result == "UTG open -> BTN 3b"


class TestRepository:
    def test_insert_and_query_by_player(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with HandRepository(db_path) as repo:
                hand = HandRecord(
                    hand_hash="abc123",
                    hash_version=SCHEMA_VERSION,
                    yyyymmdd=20250110,
                    seat_count=6,
                    phhs_blob=b"",
                    players=[
                        HandPlayerRecord(
                            hand_hash="abc123",
                            player_id=0,
                            player_name="TestPlayer",
                            yyyymmdd=20250110,
                            seat_no=1,
                            rel_pos="BTN",
                            starting_stack=200,
                        ),
                    ],
                )

                repo.insert_hand(hand)

                results = repo.find_hands_by_player("TestPlayer")
                assert len(results) == 1
                assert results[0].hand_hash == "abc123"

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with HandRepository(db_path) as repo:
                stats = repo.get_stats()
                assert stats["hands"] == 0
                assert stats["players"] == 0

    def test_duplicate_hand_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with HandRepository(db_path) as repo:
                hand = HandRecord(
                    hand_hash="dup123",
                    hash_version=SCHEMA_VERSION,
                    yyyymmdd=20250110,
                    seat_count=6,
                    phhs_blob=b"test",
                    players=[
                        HandPlayerRecord(
                            hand_hash="dup123",
                            player_id=0,
                            player_name="Player1",
                            yyyymmdd=20250110,
                            seat_no=1,
                            rel_pos="BTN",
                            starting_stack=200,
                        ),
                    ],
                )

                result1 = repo.insert_hand(hand)
                result2 = repo.insert_hand(hand)

                assert result1 is True
                assert result2 is False

                stats = repo.get_stats()
                assert stats["hands"] == 1

    def test_query_by_date_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with HandRepository(db_path) as repo:
                for i, date in enumerate([20250108, 20250109, 20250110]):
                    hand = HandRecord(
                        hand_hash=f"hash_{date}",
                        hash_version=SCHEMA_VERSION,
                        yyyymmdd=date,
                        seat_count=6,
                        phhs_blob=b"",
                        players=[
                            HandPlayerRecord(
                                hand_hash=f"hash_{date}",
                                player_id=0,
                                player_name="TestPlayer",
                                yyyymmdd=date,
                                seat_no=1,
                                rel_pos="BTN",
                                starting_stack=200,
                            ),
                        ],
                    )
                    repo.insert_hand(hand)

                results = repo.find_hands_by_player(
                    "TestPlayer", start_date=20250109, end_date=20250109
                )
                assert len(results) == 1
                assert results[0].yyyymmdd == 20250109
