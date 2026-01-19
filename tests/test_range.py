"""Range 模块单元测试。"""

import pytest

from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    RANGE_169_ORDER,
    RANGE_1326_LENGTH,
    PostflopRange,
    PreflopRange,
    card_to_index52,
    combo_to_index1326,
    combos_per_hand,
    get_hand_key_to_169_index,
    get_range_169_to_1326,
    get_range_1326_to_169,
    index1326_to_combo,
    index52_to_card,
)


class TestMappingsConstants:
    """映射常量测试。"""

    def test_range_169_order_length(self) -> None:
        assert len(RANGE_169_ORDER) == RANGE_169_LENGTH

    def test_range_169_order_unique(self) -> None:
        assert len(set(RANGE_169_ORDER)) == RANGE_169_LENGTH


class TestCardIndexConversion:
    """牌索引转换测试。"""

    def test_card_to_index52(self) -> None:
        # 2c = 0, 2d = 1, 2h = 2, 2s = 3
        assert card_to_index52("2", "c") == 0
        assert card_to_index52("2", "s") == 3
        # Ac = 48, As = 51
        assert card_to_index52("A", "c") == 48
        assert card_to_index52("A", "s") == 51

    def test_index52_to_card(self) -> None:
        assert index52_to_card(0) == ("2", "c")
        assert index52_to_card(51) == ("A", "s")

    def test_roundtrip(self) -> None:
        for idx in range(52):
            rank, suit = index52_to_card(idx)
            assert card_to_index52(rank, suit) == idx


class TestComboIndexConversion:
    """组合索引转换测试。"""

    def test_combo_to_index1326(self) -> None:
        # 第一个组合：(0, 1) = 2c2d
        assert combo_to_index1326(0, 1) == 0
        # 对称性
        assert combo_to_index1326(1, 0) == 0

    def test_index1326_to_combo(self) -> None:
        assert index1326_to_combo(0) == (0, 1)

    def test_roundtrip(self) -> None:
        for idx in range(RANGE_1326_LENGTH):
            c1, c2 = index1326_to_combo(idx)
            assert combo_to_index1326(c1, c2) == idx


class TestCombosPerHand:
    """手牌组合数测试。"""

    def test_pairs(self) -> None:
        assert combos_per_hand("AA") == 6
        assert combos_per_hand("22") == 6

    def test_suited(self) -> None:
        assert combos_per_hand("AKs") == 4
        assert combos_per_hand("32s") == 4

    def test_offsuit(self) -> None:
        assert combos_per_hand("AKo") == 12
        assert combos_per_hand("32o") == 12


class TestRange169To1326Mapping:
    """169↔1326 映射测试。"""

    def test_mapping_length(self) -> None:
        mapping = get_range_169_to_1326()
        assert len(mapping) == RANGE_169_LENGTH

    def test_all_combos_covered(self) -> None:
        mapping = get_range_169_to_1326()
        all_combos = set()
        for combo_list in mapping:
            all_combos.update(combo_list)
        assert len(all_combos) == RANGE_1326_LENGTH

    def test_reverse_mapping(self) -> None:
        mapping_1326_to_169 = get_range_1326_to_169()
        assert len(mapping_1326_to_169) == RANGE_1326_LENGTH


class TestHandKeyMapping:
    """手牌键映射测试。"""

    def test_all_keys_present(self) -> None:
        key_to_idx = get_hand_key_to_169_index()
        for hand_key in RANGE_169_ORDER:
            assert hand_key in key_to_idx


class TestPreflopRange:
    """PreflopRange 类测试。"""

    def test_zeros(self) -> None:
        r = PreflopRange.zeros()
        assert len(r) == RANGE_169_LENGTH
        assert all(v == 0.0 for v in r.strategy)

    def test_ones(self) -> None:
        r = PreflopRange.ones()
        assert len(r) == RANGE_169_LENGTH
        assert all(v == 1.0 for v in r.strategy)

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError, match="169"):
            PreflopRange(strategy=[1.0, 2.0])

    def test_total_frequency(self) -> None:
        r = PreflopRange.ones()
        assert r.total_frequency() == pytest.approx(1.0)

        r_zeros = PreflopRange.zeros()
        assert r_zeros.total_frequency() == pytest.approx(0.0)

    def test_to_postflop(self) -> None:
        r = PreflopRange.ones()
        postflop = r.to_postflop()
        assert len(postflop) == RANGE_1326_LENGTH
        assert all(v == 1.0 for v in postflop.strategy)

    def test_adjust_by_ev(self) -> None:
        r = PreflopRange(
            strategy=[1.0] * RANGE_169_LENGTH,
            evs=[0.5 if i < 50 else -0.5 for i in range(RANGE_169_LENGTH)],
        )
        r.adjust_by_ev(0.0)
        # EV < 0 的手牌策略应该变为 0
        for i in range(RANGE_169_LENGTH):
            if r.evs[i] < 0:
                assert r.strategy[i] == 0.0


class TestPostflopRange:
    """PostflopRange 类测试。"""

    def test_zeros(self) -> None:
        r = PostflopRange.zeros()
        assert len(r) == RANGE_1326_LENGTH

    def test_ones(self) -> None:
        r = PostflopRange.ones()
        assert len(r) == RANGE_1326_LENGTH

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError, match="1326"):
            PostflopRange(strategy=[1.0, 2.0])

    def test_total_frequency(self) -> None:
        r = PostflopRange.ones()
        assert r.total_frequency() == pytest.approx(1.0)

    def test_to_preflop(self) -> None:
        r = PostflopRange.ones()
        preflop = r.to_preflop()
        assert len(preflop) == RANGE_169_LENGTH
        assert all(v == pytest.approx(1.0) for v in preflop.strategy)

    def test_ban_cards(self) -> None:
        r = PostflopRange.ones()
        # 禁止 Ac (index 48)
        r.ban_cards([48])
        # 应该有一些位置变为 0
        zero_count = sum(1 for v in r.strategy if v == 0.0)
        # Ac 与其他 51 张牌组合
        assert zero_count == 51


class TestRoundtripConversion:
    """169↔1326 往返转换测试。"""

    def test_preflop_to_postflop_to_preflop(self) -> None:
        # 创建一个简单的 preflop range
        strategy_data = [0.5] * RANGE_169_LENGTH
        strategy_data[0] = 1.0  # 22 = 100%
        r = PreflopRange(strategy=strategy_data)

        # 转换到 postflop 再转回来
        postflop = r.to_postflop()
        back = postflop.to_preflop()

        # 应该一致
        for i in range(RANGE_169_LENGTH):
            assert back.strategy[i] == pytest.approx(r.strategy[i])
