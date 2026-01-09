"""
大样本 .phhs 序列化/反序列化一致性测试（依赖本地手牌数据集）。

需求：从指定目录随机挑选 1000 个“复杂手牌”，对以下字段做 roundtrip 校验：
- 玩家姓名（players）
- 起始筹码（starting_stacks）
- 行动线（actions）
- board 发牌动作（从 actions 中提取）
- 赢钱数（winnings）

说明：
- 该测试默认跳过（避免 CI 依赖外部数据、避免日常测试过慢）。
- 运行方式：
  BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample
- 可通过 GG_HANDHISTORY_DIR 覆盖数据目录路径。
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest

from bayes_poker.hand_history.parse_gg_poker import (
    RushCashPokerStarsParser,
    load_hand_histories,
    parse_hand_text,
    save_hand_histories,
)


DEFAULT_HANDHISTORY_DIR = Path(
    "~/project/gg_handhistory/2025-02-13_GGHRC_NL2_SH_TGOVM255"
).expanduser()

COMPLEXITY_KEYWORDS: tuple[str, ...] = (
    "Chooses to EV Cashout",
    "Pays Cashout Risk",
    "Cash Drop to Pot",
    "Hand was run",
    "*** FIRST FLOP ***",
    "*** SECOND FLOP ***",
    "*** THIRD FLOP ***",
    "Uncalled bet",
    "and is all-in",
)


def _extract_board_actions(hand_history) -> list[str]:
    board_actions: list[str] = []
    for action in hand_history.actions:
        parts = str(action).split()
        if len(parts) >= 3 and parts[0] == "d" and parts[1] == "db":
            board_actions.append(parts[2])
    return board_actions


def _complexity_score(hand_text: str) -> int:
    score = sum(1 for key in COMPLEXITY_KEYWORDS if key in hand_text)
    if hand_text.count(" collected ") >= 2:
        score += 1
    return score


def _hand_id_from_text(hand_text: str) -> str:
    prefix = "PokerStars Hand #"
    idx = hand_text.find(prefix)
    if idx < 0:
        return "unknown"
    start = idx + len(prefix)
    end = hand_text.find(":", start)
    return hand_text[start:end].strip() if end > start else "unknown"


@pytest.mark.large_sample
def test_phhs_roundtrip_large_sample_complex_hands(tmp_path: Path) -> None:
    if os.environ.get("BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS") != "1":
        pytest.skip("未启用大样本测试（设置 BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 才运行）")

    dataset_dir = Path(os.environ.get("GG_HANDHISTORY_DIR", str(DEFAULT_HANDHISTORY_DIR))).expanduser()
    if not dataset_dir.exists():
        pytest.skip(f"手牌数据目录不存在: {dataset_dir}")

    parser = RushCashPokerStarsParser()
    rng = random.Random(20250213)

    files = sorted(dataset_dir.glob("*.txt"))
    if not files:
        pytest.skip(f"目录下未发现 .txt 手牌文件: {dataset_dir}")

    rng.shuffle(files)

    selected_texts: list[str] = []
    selected_originals = []

    scanned_hands = 0
    parse_failures = 0

    for file_path in files:
        if len(selected_texts) >= 1000:
            break

        text = file_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        hand_texts = parser.HAND.findall(text)
        if not hand_texts:
            continue

        rng.shuffle(hand_texts)
        for hand_text in hand_texts:
            if len(selected_texts) >= 1000:
                break

            scanned_hands += 1
            if _complexity_score(hand_text) < 2:
                continue

            try:
                original = parse_hand_text(hand_text, parser=parser)
            except Exception:
                parse_failures += 1
                continue

            selected_texts.append(hand_text)
            selected_originals.append(original)

    assert len(selected_texts) == 1000, (
        "复杂手牌样本不足，无法抽满 1000 手；"
        f"selected={len(selected_texts)} scanned_hands={scanned_hands} "
        f"parse_failures={parse_failures} dataset_dir={dataset_dir}"
    )

    phhs_path = tmp_path / "large_sample_hand_histories.phhs"
    save_hand_histories(phhs_path, selected_originals)
    loaded = load_hand_histories(phhs_path)

    assert len(loaded) == len(selected_originals)

    for idx, (original, roundtripped, hand_text) in enumerate(
        zip(selected_originals, loaded, selected_texts, strict=True)
    ):
        hand_id = _hand_id_from_text(hand_text)
        context = f"idx={idx} hand_id={hand_id}"

        assert roundtripped.players == original.players, context
        assert roundtripped.starting_stacks == original.starting_stacks, context
        assert list(roundtripped.actions) == list(original.actions), context
        assert _extract_board_actions(roundtripped) == _extract_board_actions(original), context
        assert roundtripped.winnings == original.winnings, context

