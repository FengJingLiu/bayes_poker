"""
测试 GGPoker 手牌历史解析的各类边缘场景。

本模块确保 sanitize_hand_text 函数能够正确处理以下特例，并且解析结果与预期金额一致（金额单位：分）：
1. EV Cashout (忽略非标准行，验证底池分配)
2. Run It Twice (验证多板面总奖金正确)
3. Multi-Pot Collection (验证同一玩家多次 collected 合并正确)
4. Showdown Folds (验证 shows 后的 folds 被正确处理)
5. Preflop Uncalled Bet (3-way All-in) (验证 raises -> calls 转换)
6. Deep Stack Uncalled Bet (验证 non-all-in uncalled bet 转换)
"""

from io import BytesIO
import logging

import pytest
from bayes_poker.hand_history.parse_gg_poker import (
    RushCashPokerStarsParser,
    extract_cash_drop_total_cents,
    parse_hand_text,
    parse_value_in_cents,
    sanitize_hand_text,
)
from pokerkit.notation import HandHistory

# --- Test Data Samples (Real Verified Hands) ---

SAMPLE_CASH_DROP_FAIL = """PokerStars Hand #03113263412: Hold'em No Limit ($0.01/$0.02) - 2024/12/01 14:29:28
Table 'GG_RushAndCash21277728' 6-max Seat #1 is the button
Seat 1: Skipbuffer ($1.95 in chips)
Seat 2: YUKIA ($1.57 in chips)
Seat 3: FICO97 ($1.96 in chips)
Seat 4: izydi ($2.41 in chips)
Seat 5: ArhiTema ($4.84 in chips)
Seat 6: Meteo Fukuhara ($10.18 in chips)
Cash Drop to Pot : total $0.20
YUKIA: posts small blind $0.01
FICO97: posts big blind $0.02
*** HOLE CARDS ***
izydi: folds
ArhiTema: raises $0.02 to $0.04
Meteo Fukuhara: folds
Skipbuffer: raises $0.18 to $0.22
YUKIA: folds
FICO97: raises $1.74 to $1.96 and is all-in
ArhiTema: raises $2.88 to $4.84 and is all-in
Skipbuffer: folds
Uncalled bet ($2.88) returned to ArhiTema
ArhiTema: shows [Kd Ad]
FICO97: shows [Ts As]
*** FLOP *** [8d Ah 6d]
*** TURN *** [8d Ah 6d] [Th]
*** RIVER *** [8d Ah 6d Th] [2s]
*** SHOWDOWN *** 
FICO97 collected $4.26 from pot
*** SUMMARY ***
Total pot $4.15 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [8d Ah 6d Th 2s]
Seat 1: Skipbuffer (button) folded before Flop
Seat 2: YUKIA (small blind) folded before Flop (didn't bet)
Seat 3: FICO97 (big blind) showed [Ts As] and won ($4.26)
Seat 4: izydi folded before Flop (didn't bet)
Seat 5: ArhiTema showed [Kd Ad] and lost
Seat 6: Meteo Fukuhara folded before Flop (didn't bet)
"""

SAMPLE_CASH_DROP_SUCCESS = """PokerStars Hand #03029669289: Hold'em No Limit ($0.01/$0.02) - 2024/11/01 22:55:05
Table 'GG_RushAndCash346807' 6-max Seat #1 is the button
Seat 1: timoni ($2.00 in chips)
Seat 2: mcdonalds123 ($4.85 in chips)
Seat 3: Gelds ($6.11 in chips)
Seat 4: Decapitador ($2.09 in chips)
Seat 5: BlurryMoth ($5.91 in chips)
Seat 6: beautysha ($2.34 in chips)
Cash Drop to Pot : total $0.20
mcdonalds123: posts small blind $0.01
Gelds: posts big blind $0.02
*** HOLE CARDS ***
Decapitador: folds
BlurryMoth: calls $0.02
beautysha: calls $0.02
timoni: folds
mcdonalds123: calls $0.01
Gelds: checks
*** FLOP *** [8h 8c Jh]
mcdonalds123: checks
Gelds: checks
BlurryMoth: checks
beautysha: checks
*** TURN *** [8h 8c Jh] [Qc]
mcdonalds123: checks
Gelds: checks
BlurryMoth: bets $0.16
beautysha: folds
mcdonalds123: folds
Gelds: folds
Uncalled bet ($0.16) returned to BlurryMoth
*** SHOWDOWN *** 
BlurryMoth collected $0.27 from pot
*** SUMMARY ***
Total pot $0.08 | Rake $0.01 | Jackpot $0.00 | Bingo $0 | Fortune $0 | Tax $0
Board [8h 8c Jh Qc]
Seat 1: timoni (button) folded before Flop (didn't bet)
Seat 2: mcdonalds123 (small blind) folded on the Turn (didn't bet)
Seat 3: Gelds (big blind) folded on the Turn (didn't bet)
Seat 4: Decapitador folded before Flop (didn't bet)
Seat 5: BlurryMoth collected ($0.27)
Seat 6: beautysha folded on the Turn (didn't bet)
"""

SAMPLE_EV_CASHOUT = """PokerStars Hand #03233240624: Hold'em No Limit ($0.01/$0.02) - 2025/01/12 06:25:02
Table 'GG_RushAndCash1694930' 6-max Seat #1 is the button
Seat 1: hfyinh ($2.88 in chips)
Seat 2: gravesJG ($3.20 in chips)
Seat 3: Angrykillki ($0.67 in chips)
Seat 4: Andryxa_M16 ($2.06 in chips)
Seat 5: hyydra ($3.66 in chips)
Seat 6: Andzdsl ($2.32 in chips)
gravesJG: posts small blind $0.01
Angrykillki: posts big blind $0.02
*** HOLE CARDS ***
Andryxa_M16: folds
hyydra: raises $0.03 to $0.05
Andzdsl: folds
hfyinh: folds
gravesJG: folds
Angrykillki: calls $0.03
*** FLOP *** [Ac 2c 3d]
Angrykillki: bets $0.06
hyydra: calls $0.06
*** TURN *** [Ac 2c 3d] [5s]
Angrykillki: bets $0.12
hyydra: raises $3.43 to $3.55 and is all-in
Angrykillki: calls $0.44 and is all-in
Uncalled bet ($2.99) returned to hyydra
hyydra: shows [Qd As]
Angrykillki: shows [4h 7h]
Angrykillki: Chooses to EV Cashout
*** RIVER *** [Ac 2c 3d 5s] [Ad]
Angrykillki: Pays Cashout Risk ($1.26)
*** SHOWDOWN *** 
Angrykillki collected $1.26 from pot
*** SUMMARY ***
Total pot $1.35 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [Ac 2c 3d 5s Ad]
Seat 1: hfyinh (button) folded before Flop (didn't bet)
Seat 2: gravesJG (small blind) folded before Flop (didn't bet)
Seat 3: Angrykillki (big blind) showed [4h 7h] and won ($1.26), Cashout Risk ($1.26)
Seat 4: Andryxa_M16 folded before Flop (didn't bet)
Seat 5: hyydra showed [Qd As] and lost
Seat 6: Andzdsl folded before Flop (didn't bet)
"""

SAMPLE_RUN_IT_TWICE = """PokerStars Hand #03233241559: Hold'em No Limit ($0.01/$0.02) - 2025/01/12 06:26:37
Table 'GG_RushAndCash1695852' 6-max Seat #1 is the button
Seat 1: mesoporous ($1.10 in chips)
Seat 2: lukki004 ($3.08 in chips)
Seat 3: Hiu Chun Leung ($2.03 in chips)
Seat 4: toyzzzzzz ($2.12 in chips)
Seat 5: SuperZamba ($2.05 in chips)
Seat 6: Ywzzz_ ($2.18 in chips)
lukki004: posts small blind $0.01
Hiu Chun Leung: posts big blind $0.02
*** HOLE CARDS ***
toyzzzzzz: raises $0.02 to $0.04
SuperZamba: folds
Ywzzz_: raises $0.11 to $0.15
mesoporous: folds
lukki004: folds
Hiu Chun Leung: raises $1.88 to $2.03 and is all-in
toyzzzzzz: folds
Ywzzz_: calls $1.88
Hiu Chun Leung: shows [Kc Ac]
Ywzzz_: shows [Ad Qs]
*** FIRST FLOP *** [Td 4s 8d]
*** FIRST TURN *** [Td 4s 8d] [2h]
*** FIRST RIVER *** [Td 4s 8d 2h] [7d]
*** SECOND FLOP *** [2s Th 8c]
*** SECOND TURN *** [2s Th 8c] [Jc]
*** SECOND RIVER *** [2s Th 8c Jc] [6s]
*** FIRST SHOWDOWN *** 
Hiu Chun Leung collected $2.01 from pot
*** SECOND SHOWDOWN *** 
Hiu Chun Leung collected $2.01 from pot
*** SUMMARY ***
Total pot $4.11 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Hand was run twice times
FIRST Board [Td 4s 8d 2h 7d]
SECOND Board [2s Th 8c Jc 6s]
Seat 1: mesoporous (button) folded before Flop (didn't bet)
Seat 2: lukki004 (small blind) folded before Flop (didn't bet)
Seat 3: Hiu Chun Leung (big blind) showed [Kc Ac] and won ($2.01), and won ($2.01)
Seat 4: toyzzzzzz folded before Flop
Seat 5: SuperZamba folded before Flop (didn't bet)
Seat 6: Ywzzz_ showed [Ad Qs] and lost, and lost
"""

SAMPLE_RUN_IT_TWICE_UNCALLED_BET_AFTER_ALL_IN_RAISE = """PokerStars Hand #03035132399: Hold'em No Limit ($0.01/$0.02) - 2024/11/03 19:36:57
Table 'GG_RushAndCash1754753' 6-max Seat #1 is the button
Seat 1: SAWO4I ($2.42 in chips)
Seat 2: Tula_3 ($5.88 in chips)
Seat 3: Petrichor404 ($2.00 in chips)
Seat 4: saha3746 ($2.05 in chips)
Seat 5: Zolibacsi ($1.59 in chips)
Seat 6: eddiegaven_25 ($2.02 in chips)
Tula_3: posts small blind $0.01
Petrichor404: posts big blind $0.02
*** HOLE CARDS ***
saha3746: raises $0.03 to $0.05
Zolibacsi: folds
eddiegaven_25: folds
SAWO4I: raises $0.11 to $0.16
Tula_3: folds
Petrichor404: raises $0.29 to $0.45
saha3746: raises $1.60 to $2.05 and is all-in
SAWO4I: raises $0.37 to $2.42 and is all-in
Petrichor404: folds
Uncalled bet ($0.37) returned to SAWO4I
SAWO4I: shows [Ah Kh]
saha3746: shows [Kc Ks]
*** FIRST FLOP *** [4s Qc 8s]
*** FIRST TURN *** [4s Qc 8s] [6d]
*** FIRST RIVER *** [4s Qc 8s 6d] [5c]
*** SECOND FLOP *** [2d 8h 7d]
*** SECOND TURN *** [2d 8h 7d] [Ad]
*** SECOND RIVER *** [2d 8h 7d Ad] [Jc]
*** FIRST SHOWDOWN *** 
saha3746 collected $2.24 from pot
*** SECOND SHOWDOWN *** 
SAWO4I collected $2.23 from pot
*** SUMMARY ***
Total pot $4.56 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Hand was run twice times
FIRST Board [4s Qc 8s 6d 5c]
SECOND Board [2d 8h 7d Ad Jc]
Seat 1: SAWO4I (button) showed [Ah Kh] and lost, and won ($2.23) (didn't bet)
Seat 2: Tula_3 (small blind) folded before Flop (didn't bet)
Seat 3: Petrichor404 (big blind) folded before Flop (didn't bet)
Seat 4: saha3746 showed [Kc Ks] and won ($2.24), and lost (didn't bet)
Seat 5: Zolibacsi folded before Flop (didn't bet)
Seat 6: eddiegaven_25 folded before Flop (didn't bet)
"""

SAMPLE_PREFLOP_UNCALLED_BET = """PokerStars Hand #02811042547: Hold'em No Limit ($0.01/$0.02) - 2024/08/18 04:39:14
Table 'GG_RushAndCash6278340' 6-max Seat #1 is the button
Seat 1: aube ($2.01 in chips)
Seat 2: pinkass! ($4.07 in chips)
Seat 3: As Rei ($2.00 in chips)
Seat 4: Franquito ($2.00 in chips)
Seat 5: Itaaaaaachi ($2.54 in chips)
Seat 6: ZSONG ($2.40 in chips)
pinkass!: posts small blind $0.01
As Rei: posts big blind $0.02
*** HOLE CARDS ***
Franquito: raises $0.04 to $0.06
Itaaaaaachi: folds
ZSONG: folds
aube: folds
pinkass!: raises $0.11 to $0.17
As Rei: calls $0.15
Franquito: raises $1.83 to $2.00 and is all-in
pinkass!: raises $2.07 to $4.07 and is all-in
As Rei: calls $1.83 and is all-in
Uncalled bet ($2.07) returned to pinkass!
pinkass!: shows [Jd Jh]
As Rei: shows [9s Ts]
Franquito: shows [Ah Kh]
*** FLOP *** [3d Qs 3c]
pinkass!: Chooses to EV Cashout
*** TURN *** [3d Qs 3c] [Tc]
pinkass!: Pays Cashout Risk ($5.91)
pinkass!: Chooses to EV Cashout
*** RIVER *** [3d Qs 3c Tc] [9d]
pinkass!: Pays Cashout Risk ($5.91)
*** SHOWDOWN *** 
pinkass! collected $5.91 from pot
*** SUMMARY ***
Total pot $6.00 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [3d Qs 3c Tc 9d]
Seat 1: aube (button) folded before Flop (didn't bet)
Seat 2: pinkass! (small blind) showed [Jd Jh] and won ($5.91), Cashout Risk ($5.91)
Seat 3: As Rei (big blind) showed [9s Ts] and lost
Seat 4: Franquito showed [Ah Kh] and lost
Seat 5: Itaaaaaachi folded before Flop (didn't bet)
Seat 6: ZSONG folded before Flop (didn't bet)
"""

# Covers both Multi-collected and Deep Stack Uncalled Bet
SAMPLE_DEEP_STACK_MULTI_COLLECTED = """PokerStars Hand #02812205389: Hold'em No Limit ($0.01/$0.02) - 2024/08/18 13:52:59
Table 'GG_RushAndCash6582340' 6-max Seat #1 is the button
Seat 1: pomor-men ($1.96 in chips)
Seat 2: Cannabikes ($5.79 in chips)
Seat 3: Catfishing1 ($2.32 in chips)
Seat 4: izipizi777 ($2.86 in chips)
Seat 5: Zsolt Gyero ($4.56 in chips)
Seat 6: Andrei M ($2.56 in chips)
Cannabikes: posts small blind $0.01
Catfishing1: posts big blind $0.02
*** HOLE CARDS ***
izipizi777: folds
Zsolt Gyero: raises $0.02 to $0.04
Andrei M: folds
pomor-men: raises $0.06 to $0.10
Cannabikes: folds
Catfishing1: calls $0.08
Zsolt Gyero: raises $0.44 to $0.54
pomor-men: calls $0.44
Catfishing1: raises $1.78 to $2.32 and is all-in
Zsolt Gyero: raises $1.78 to $4.10
pomor-men: calls $1.42 and is all-in
Uncalled bet ($1.78) returned to Zsolt Gyero
Zsolt Gyero: shows [Qc Qs]
pomor-men: shows [8d Jd]
Catfishing1: shows [Kh Ac]
*** FLOP *** [5d 7s 6h]
*** TURN *** [5d 7s 6h] [7c]
*** RIVER *** [5d 7s 6h 7c] [6d]
*** SHOWDOWN *** 
Zsolt Gyero collected $5.81 from pot
Zsolt Gyero collected $0.72 from pot
*** SUMMARY ***
Total pot $6.61 | Rake $0.05 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [5d 7s 6h 7c 6d]
Seat 1: pomor-men (button) showed [8d Jd] and lost
Seat 2: Cannabikes (small blind) folded before Flop
Seat 3: Catfishing1 (big blind) showed [Kh Ac] and lost
Seat 4: izipizi777 folded before Flop (didn't bet)
Seat 5: Zsolt Gyero showed [Qc Qs] and won ($5.81), and won ($0.72)
Seat 6: Andrei M folded before Flop (didn't bet)
"""

SAMPLE_SHOWDOWN_FOLDS = """PokerStars Hand #03033503486: Hold'em No Limit ($0.01/$0.02) - 2024/11/03 08:10:07
Table 'GG_RushAndCash1319883' 6-max Seat #1 is the button
Seat 1: shirogoma ($2.13 in chips)
Seat 2: KingDuck ($2.45 in chips)
Seat 3: ha1des7 ($2.15 in chips)
Seat 4: Soichiro21 ($2.74 in chips)
Seat 5: SeeYouCoco ($2.00 in chips)
Seat 6: vudik ($1.97 in chips)
KingDuck: posts small blind $0.01
ha1des7: posts big blind $0.02
*** HOLE CARDS ***
Soichiro21: raises $0.02 to $0.04
SeeYouCoco: folds
vudik: folds
shirogoma: raises $0.11 to $0.15
KingDuck: folds
ha1des7: calls $0.13
Soichiro21: calls $0.11
*** FLOP *** [8h 5s Ad]
ha1des7: checks
Soichiro21: checks
shirogoma: checks
*** TURN *** [8h 5s Ad] [7d]
ha1des7: checks
Soichiro21: checks
shirogoma: bets $0.23
ha1des7: raises $0.46 to $0.69
Soichiro21: folds
shirogoma: calls $0.46
*** RIVER *** [8h 5s Ad 7d] [2c]
ha1des7: bets $1.31 and is all-in
shirogoma: calls $1.29 and is all-in
shirogoma: shows [Kh Ac]
ha1des7: folds
Uncalled bet ($0.02) returned to ha1des7
*** SHOWDOWN *** 
shirogoma collected $4.33 from pot
*** SUMMARY ***
Total pot $4.42 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [8h 5s Ad 7d 2c]
Seat 1: shirogoma (button) showed [Kh Ac] and won ($4.33)
Seat 2: KingDuck (small blind) folded before Flop (didn't bet)
Seat 3: ha1des7 (big blind) folded on the River (didn't bet)
Seat 4: Soichiro21 folded on the Turn (didn't bet)
Seat 5: SeeYouCoco folded before Flop (didn't bet)
Seat 6: vudik folded before Flop (didn't bet)
"""

SAMPLE_CASH_DROP_COMMAS = """PokerStars Hand #09999999999: Hold'em No Limit ($0.01/$0.02) - 2025/01/01 00:00:00
Table 'GG_RushAndCash_TEST' 6-max Seat #1 is the button
Cash Drop to Pot : total $1,234.56
"""

SAMPLE_CASH_DROP_INVALID_AMOUNT = """PokerStars Hand #08888888888: Hold'em No Limit ($0.01/$0.02) - 2025/01/01 00:00:00
Table 'GG_RushAndCash_TEST' 6-max Seat #1 is the button
Cash Drop to Pot : total $0.2.0
"""

SAMPLE_STANDARD_UNCALLED_BET_AFTER_FOLD = """PokerStars Hand #07777777777: Hold'em No Limit ($0.01/$0.02) - 2025/01/01 00:00:00
Table 'GG_RushAndCash_TEST' 6-max Seat #1 is the button
*** HOLE CARDS ***
Alice: raises $0.10 to $0.15
Bob: folds
Uncalled bet ($0.10) returned to Alice
"""

SAMPLE_CALLS_THEN_FOLDS_BEFORE_SHOWS = """PokerStars Hand #06666666666: Hold'em No Limit ($0.01/$0.02) - 2025/01/01 00:00:00
Table 'GG_RushAndCash_TEST' 6-max Seat #1 is the button
*** TURN *** [8h 5s Ad] [7d]
Alice: calls $0.23
Bob: folds
Alice: shows [Ah Kh]
*** SHOWDOWN ***
"""

SAMPLE_RUN_IT_THREE_TIMES_MINIMAL = """PokerStars Hand #05555555555: Hold'em No Limit ($0.01/$0.02) - 2025/01/01 00:00:00
Table 'GG_RushAndCash_TEST' 6-max Seat #1 is the button
*** HOLE CARDS ***
Alice: shows [Ah Kh]
Bob: shows [Qd Qc]
*** FIRST FLOP *** [Td 4s 8d]
*** SECOND FLOP *** [2s Th 8c]
*** THIRD FLOP *** [As Ks Qs]
*** FIRST SHOWDOWN *** 
Alice collected $0.01 from pot
*** SECOND SHOWDOWN *** 
Alice collected $0.01 from pot
*** THIRD SHOWDOWN *** 
Alice collected $0.01 from pot
*** SUMMARY ***
Hand was run three times
FIRST Board [Td 4s 8d]
SECOND Board [2s Th 8c]
THIRD Board [As Ks Qs]
"""


class TestParseFailedHands:
    """测试各类手牌场景的解析行为及金额准确性。"""

    @pytest.fixture
    def parser(self) -> RushCashPokerStarsParser:
        return RushCashPokerStarsParser()


    def test_cash_drop_fail(self, parser):
        """测试 Cash Drop 历史失败样本（回归用例：应能解析）。"""
        sanitized = sanitize_hand_text(SAMPLE_CASH_DROP_FAIL)
        parser._parse(sanitized, parse_value=parse_value_in_cents)

    @pytest.mark.parametrize(
        "case_name, hand_text, expected_winners, expected_board",
        [
            ("Cash Drop (Success)", SAMPLE_CASH_DROP_SUCCESS, {"BlurryMoth": 27}, None),
            ("EV Cashout", SAMPLE_EV_CASHOUT, {"Angrykillki": 126}, None),
            ("Run It Twice", SAMPLE_RUN_IT_TWICE, {"Hiu Chun Leung": 402}, ["Td4s8d", "2h", "7d"]),
            (
                "Run It Twice (Uncalled Bet After All-in Raise)",
                SAMPLE_RUN_IT_TWICE_UNCALLED_BET_AFTER_ALL_IN_RAISE,
                {"saha3746": 224, "SAWO4I": 223},
                ["4sQc8s", "6d", "5c"],
            ),
            ("Preflop Uncalled Bet", SAMPLE_PREFLOP_UNCALLED_BET, {"pinkass!": 591}, None),
            ("Deep Stack & Multi-Collected", SAMPLE_DEEP_STACK_MULTI_COLLECTED, {"Zsolt Gyero": 653}, None),
            ("Showdown Folds", SAMPLE_SHOWDOWN_FOLDS, {"shirogoma": 433}, None),
        ]
    )
    def test_sanitize_and_parse(
        self,
        parser: RushCashPokerStarsParser,
        case_name: str,
        hand_text: str,
        expected_winners: dict[str, int],
        expected_board: list[str] | None,
    ) -> None:
        """
        验证各类特例在 sanitize 后能成功解析，且金额正确，板面正确。
        
        Args:
            parser: 解析器
            case_name: 测试用例说明
            hand_text: 原始手牌文本
            expected_winners: 预期赢家及金额（分）
            expected_board: 预期板面发牌动作列表（如 ["Td4s8d", "2h", "7d"]），可选
        """
        # 1. Sanitize
        sanitized = sanitize_hand_text(hand_text)
        
        # 2. Parse check
        try:
            hh = parser._parse(sanitized, parse_value=parse_value_in_cents)
        except Exception as e:
            pytest.fail(f"[{case_name}] 解析失败: {e}")

        # 3. Verify Winnings (Amount X100)
        actual_winners = {}
        assert len(hh.players) == len(hh.winnings), "玩家列表与奖金列表长度不一致"
        
        for player, amount in zip(hh.players, hh.winnings):
            if amount > 0:
                actual_winners[player] = int(amount)
        
        missing_winners = set(expected_winners.keys()) - set(actual_winners.keys())
        assert not missing_winners, f"[{case_name}] 缺少赢家: {missing_winners}. 实际: {actual_winners}"
        
        for player, expected_amt in expected_winners.items():
            actual_amt = actual_winners.get(player, 0)
            assert actual_amt == expected_amt, (
                f"[{case_name}] {player} 奖金金额不匹配: 预期 {expected_amt}, 实际 {actual_amt}"
            )
            
        # 4. Verify Board (if expected_board is provided)
        if expected_board:
            # Find all "d db <cards>" actions
            # hh.actions contains strings here? No, earlier I saw 'str d dh ...'. 
            # Wait, `hh.actions` elements ARE simple strings in the `PokerStarsParser` implementation? 
            # Or strings that happen to print that way?
            # They print as "d db Ac2c3d". 
            # Let's check if they are strings or objects with repr.
            # Assuming str for simple check:
            
            parsed_board_actions = []
            for action in hh.actions:
                # Actions seem to be pure strings in the parser output I saw?
                # "0: str d dh p1 ????" -> type is str.
                # Yes, standard pokerkit HandHistory uses strings for phh notation actions sometimes?
                # Or it converts them?
                # Let's match string content.
                s_act = str(action)
                if "d db" in s_act:
                    # Extract cards part: "d db Td4s8d" -> "Td4s8d"
                    parts = s_act.split()
                    if len(parts) >= 3 and parts[0] == 'd' and parts[1] == 'db':
                        parsed_board_actions.append(parts[2])
            
            assert parsed_board_actions == expected_board, (
                f"[{case_name}] 板面发牌动作不匹配. 预期: {expected_board}, 实际: {parsed_board_actions}"
            )


def test_extract_cash_drop_total_cents() -> None:
    assert extract_cash_drop_total_cents(SAMPLE_CASH_DROP_SUCCESS) == 20
    assert extract_cash_drop_total_cents(SAMPLE_EV_CASHOUT) is None


def test_extract_cash_drop_total_cents_parses_commas() -> None:
    assert extract_cash_drop_total_cents(SAMPLE_CASH_DROP_COMMAS) == 123_456


def test_extract_cash_drop_total_cents_invalid_amount_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="bayes_poker.hand_history.parse_gg_poker"):
        assert extract_cash_drop_total_cents(SAMPLE_CASH_DROP_INVALID_AMOUNT) is None
    assert any("Cash Drop 金额解析失败" in record.getMessage() for record in caplog.records)


def test_sanitize_does_not_convert_standard_uncalled_bet_after_fold() -> None:
    sanitized = sanitize_hand_text(SAMPLE_STANDARD_UNCALLED_BET_AFTER_FOLD)
    assert "Alice: raises $0.10 to $0.15" in sanitized
    assert "Alice: calls" not in sanitized
    assert "Uncalled bet ($0.10) returned to Alice" in sanitized


def test_sanitize_removes_calls_then_folds_before_shows() -> None:
    sanitized = sanitize_hand_text(SAMPLE_CALLS_THEN_FOLDS_BEFORE_SHOWS)
    assert "Bob: folds" not in sanitized
    assert "Alice: calls $0.23" in sanitized
    assert "Alice: shows [Ah Kh]" in sanitized


def test_sanitize_run_it_three_times_removes_extra_boards() -> None:
    sanitized = sanitize_hand_text(SAMPLE_RUN_IT_THREE_TIMES_MINIMAL)
    assert "*** FLOP ***" in sanitized
    assert "*** FIRST FLOP ***" not in sanitized
    assert "*** SECOND FLOP ***" not in sanitized
    assert "*** THIRD FLOP ***" not in sanitized
    assert "Hand was run three times" not in sanitized
    assert "SECOND Board" not in sanitized
    assert "THIRD Board" not in sanitized


def test_parse_hand_text_preserves_cash_drop() -> None:
    parser = RushCashPokerStarsParser()
    hand_history = parse_hand_text(SAMPLE_CASH_DROP_SUCCESS, parser=parser)
    assert hand_history.user_defined_fields["_cash_drop_total_cents"] == 20


def test_cash_drop_persisted_in_dump_load_roundtrip() -> None:
    parser = RushCashPokerStarsParser()
    hand_history = parse_hand_text(SAMPLE_CASH_DROP_SUCCESS, parser=parser)

    buffer = BytesIO()
    HandHistory.dump_all([hand_history], buffer)
    buffer.seek(0)

    loaded = list(HandHistory.load_all(buffer, parse_value=parse_value_in_cents))
    assert loaded[0].user_defined_fields["_cash_drop_total_cents"] == 20
