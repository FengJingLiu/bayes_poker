"""
测试 .phhs 序列化/反序列化的端到端一致性。

目标：确保从源手牌文本解析出的 HandHistory 在 dump 到硬盘再 load 后，
关键信息不丢失且保持一致：
- 玩家姓名（players）
- 起始筹码（starting_stacks）
- 行动线（actions）
- board 发牌动作（从 actions 中提取）
- 赢钱数（winnings）
"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.hand_history.parse_gg_poker import (
    RushCashPokerStarsParser,
    load_hand_histories,
    parse_hand_text,
    save_hand_histories,
)


FIXTURE_SOURCE_HAND_PATH = (
    Path(__file__).resolve().parent / "data" / "sample_cash_drop_success.txt"
)


def _extract_board_actions(hand_history) -> list[str]:
    board_actions: list[str] = []
    for action in hand_history.actions:
        parts = str(action).split()
        if len(parts) >= 3 and parts[0] == "d" and parts[1] == "db":
            board_actions.append(parts[2])
    return board_actions


def test_phhs_roundtrip_matches_source_hand_text(tmp_path: Path) -> None:
    source_path = tmp_path / "source_hand_history.txt"
    source_path.write_text(
        FIXTURE_SOURCE_HAND_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    hand_text = source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    parser = RushCashPokerStarsParser()
    original = parse_hand_text(hand_text, parser=parser)

    phhs_path = tmp_path / "hand_histories.phhs"
    save_hand_histories(phhs_path, [original])

    loaded = load_hand_histories(phhs_path)
    assert len(loaded) == 1
    roundtripped = loaded[0]

    assert roundtripped.players == original.players
    assert roundtripped.starting_stacks == original.starting_stacks
    assert list(roundtripped.actions) == list(original.actions)
    assert _extract_board_actions(roundtripped) == _extract_board_actions(original)
    assert roundtripped.winnings == original.winnings
