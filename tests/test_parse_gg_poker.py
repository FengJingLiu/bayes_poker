from __future__ import annotations

import re
import unittest
from pathlib import Path
from warnings import filterwarnings

from bayes_poker.hand_history.parse_gg_poker import (
    HAND_HISTORY_PATH,
    RushCashPokerStarsParser,
    load_hand_histories,
    parse_value_in_cents,
    save_hand_histories,
)

PERSISTED_TEST_PATH = Path("data/outputs/test_hand_histories.phhs")


class TestParseGGPoker(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = HAND_HISTORY_PATH.read_text(encoding="utf-8").replace(
            "\r\n", "\n"
        )
        cls.raw_ids = [
            int(hand_id)
            for hand_id in re.findall(
                r"^PokerStars Hand #(?P<hand>\d+):",
                cls.text,
                re.MULTILINE,
            )
        ]
        parser = RushCashPokerStarsParser()
        filterwarnings("ignore", message="Unable to parse.*")
        cls.hand_histories = list(
            parser(cls.text, parse_value=parse_value_in_cents)
        )
        cls.hand_by_id = {
            hand.hand: hand
            for hand in cls.hand_histories
            if isinstance(hand.hand, int)
        }

    def test_missing_hand_ids_match_known_gap(self) -> None:
        # 校验解析缺失的手牌编号与已知缺口一致
        missing = [
            hand_id for hand_id in self.raw_ids if hand_id not in self.hand_by_id
        ]
        self.assertEqual(missing, [3233243312])

    def test_roundtrip_persistence_matches_parsed(self) -> None:
        # 校验持久化与加载后的手牌内容完全一致
        save_hand_histories(PERSISTED_TEST_PATH, self.hand_histories)
        loaded = load_hand_histories(PERSISTED_TEST_PATH)
        self.assertEqual(len(loaded), len(self.hand_histories))
        for original, restored in zip(self.hand_histories, loaded):
            self.assertEqual(original.dumps(), restored.dumps())

    def test_hand_metadata_and_actions(self) -> None:
        # 校验指定手牌的元数据与动作序列是否正确
        hand = self.hand_by_id[3233240450]
        self.assertEqual(hand.table, "GG_RushAndCash1694760")
        self.assertEqual(hand.seat_count, 6)
        self.assertEqual(hand.seats, [2, 3, 4, 5, 6, 1])
        self.assertEqual(
            hand.players,
            [
                "Dark KiMa",
                "DeathCard",
                "sambist2010",
                "Kinangcao",
                "i_m_bluffing",
                "kt_rym",
            ],
        )
        self.assertEqual(hand.blinds_or_straddles, [1, 2, 0, 0, 0, 0])
        self.assertEqual(hand.starting_stacks, [225, 354, 406, 307, 106, 200])
        self.assertEqual(hand.year, 2025)
        self.assertEqual(hand.month, 1)
        self.assertEqual(hand.day, 12)
        self.assertEqual(str(hand.time), "06:24:44")
        actions = [
            action for action in hand.actions if not action.startswith("d dh")
        ]
        self.assertEqual(
            actions,
            [
                "p3 cbr 4",
                "p4 cbr 14",
                "p5 f",
                "p6 f",
                "p1 f",
                "p2 f",
                "p3 f",
            ],
        )

    def test_run_it_twice_winnings(self) -> None:
        # 校验 run-it-twice 手牌的玩家顺序与分池金额
        hand = self.hand_by_id[3233240672]
        self.assertIn(
            "Hand was run twice times",
            self._extract_hand_text(3233240672),
        )
        self.assertEqual(
            hand.players,
            [
                "Dudk0",
                "Lucas Carter",
                "wstfwps",
                "PokerQiang",
                "thantaiden333",
                "Luen alwaysnuts",
            ],
        )
        self.assertEqual(hand.blinds_or_straddles, [1, 2, 0, 0, 0, 0])
        self.assertEqual(hand.winnings, [0, 125, 0, 0, 0, 125])
        self.assertIn("d db 9cTc7c", hand.actions)

    def _extract_hand_text(self, hand_id: int) -> str:
        hand_id_str = f"{hand_id:011d}"
        match = re.search(
            rf"PokerStars Hand #{hand_id_str}:.*?(?=\n\nPokerStars Hand #|\Z)",
            self.text,
            re.DOTALL | re.MULTILINE,
        )
        if match is None:
            raise AssertionError(f"hand {hand_id_str} not found in source")
        return match.group(0)


if __name__ == "__main__":
    unittest.main()
