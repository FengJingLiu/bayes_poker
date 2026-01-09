"""
GGPoker Rush & Cash 手牌历史解析模块。

本模块提供解析 GGPoker Rush & Cash 导出的手牌历史文件的功能。
使用 pokerkit 库进行底层解析。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from operator import add
from pathlib import Path
from re import DOTALL, MULTILINE, compile, search, sub

from pokerkit.notation import HandHistory, PokerStarsParser, parse_time

# 路径配置
HAND_HISTORY_PATH = Path(
    "data/handhistory/11351348hhd_RushCash_5_NLH2SH_2025-01-12.txt"
)
PERSISTED_HAND_HISTORY_PATH = Path("data/outputs/hand_histories.phhs")
FAILED_HANDS_DIR = Path("logs/hand_history_failures")
FAILED_HANDS_LOG_PATH = Path("logs/hand_history_failures.log")

# 日志配置
LOGGER = logging.getLogger(__name__)


@dataclass
class RushCashPokerStarsParser(PokerStarsParser):
    """
    GGPoker Rush & Cash 手牌历史解析器。

    继承自 pokerkit 的 PokerStarsParser，针对 GGPoker 的格式进行了定制。
    """

    HAND = compile(
        r"^PokerStars Hand #.+?(?=^PokerStars Hand #|\Z)",
        DOTALL | MULTILINE,
    )
    CHECKING_OR_CALLING = compile(r"^(?P<player>.+): c(all|heck)s\b")
    VARIANT = compile(r":\s+(?P<variant>Hold'em No Limit) \(")
    DATETIME = compile(
        (
            r" -"
            r" (?P<year>\d+)/(?P<month>\d+)/(?P<day>\d+)"
            r" (?P<time>\d{1,2}:\d{2}:\d{2})"
            r"(?: (?P<time_zone_abbreviation>\S+))?"
        )
    )
    VARIABLES = {
        "time": (DATETIME, parse_time),
        "day": (DATETIME, int),
        "month": (DATETIME, int),
        "year": (DATETIME, int),
        "hand": (compile(r"PokerStars (Hand|Game) #(?P<hand>\d+):"), int),
        "seat_count": (compile(r" (?P<seat_count>\d+)-max "), int),
        "table": (compile(r"Table '(?P<table>.+)'"), str),
        "currency_symbol": (
            compile(r"\((?P<currency_symbol>\D?)[0-9.,]+ in chips\)"),
            str,
        ),
    }
    PLAYER_VARIABLES = {
        "winnings": (
            compile(
                r"^(?P<player>.+?) collected \D?(?P<winnings>[0-9.,]+) from pot"
            ),
            None,
            int,
            add,
        ),
    }


def parse_value_in_cents(raw_value: str) -> int:
    """
    将金额字符串解析为美分整数。

    Args:
        raw_value: 金额字符串，如 "1.50"。

    Returns:
        美分整数，如 150。

    Raises:
        ValueError: 如果金额格式无效。
    """
    try:
        amount = Decimal(raw_value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid value: {raw_value}") from exc

    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_hand_histories(path: Path) -> tuple[list[HandHistory], int]:
    """
    解析手牌历史文件。

    Args:
        path: 手牌历史文件路径。

    Returns:
        元组 (成功解析的手牌列表, 总手牌数)。
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    parser = RushCashPokerStarsParser()
    hand_texts = parser.HAND.findall(text)
    total = len(hand_texts)
    configure_logging(FAILED_HANDS_LOG_PATH)
    hand_histories: list[HandHistory] = []

    for hand_text in hand_texts:
        try:
            hand_histories.append(
                parser._parse(
                    hand_text,
                    parse_value=parse_value_in_cents,
                )
            )
        except (KeyError, ValueError, RecursionError) as exc:
            hand_id, table = extract_hand_metadata(hand_text)
            LOGGER.warning(
                "解析失败: hand=%s table=%s error=%s", hand_id, table, exc
            )
            save_failed_hand(hand_text, hand_id, table)

    return hand_histories, total


def format_time(hand_history: HandHistory) -> str:
    """
    格式化手牌历史的时间。

    Args:
        hand_history: 手牌历史对象。

    Returns:
        格式化的时间字符串。
    """
    if hand_history.year is None:
        return "未知时间"

    return (
        f"{hand_history.year:04d}-{hand_history.month:02d}-"
        f"{hand_history.day:02d} {hand_history.time}"
    )


def save_hand_histories(
    path: Path,
    hand_histories: Sequence[HandHistory],
) -> None:
    """
    保存手牌历史到文件。

    Args:
        path: 保存路径。
        hand_histories: 手牌历史序列。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        HandHistory.dump_all(hand_histories, file)


def load_hand_histories(path: Path) -> list[HandHistory]:
    """
    从文件加载手牌历史。

    Args:
        path: 文件路径。

    Returns:
        手牌历史列表。
    """
    with path.open("rb") as file:
        return list(HandHistory.load_all(file, parse_value=parse_value_in_cents))


def configure_logging(log_path: Path) -> None:
    """
    配置日志记录。

    Args:
        log_path: 日志文件路径。
    """
    if LOGGER.handlers:
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)
    LOGGER.setLevel(logging.INFO)


def extract_hand_metadata(hand_text: str) -> tuple[str, str]:
    """
    从手牌文本中提取元数据。

    Args:
        hand_text: 手牌文本。

    Returns:
        元组 (hand_id, table_name)。
    """
    hand_match = search(r"PokerStars Hand #(?P<hand>\d+):", hand_text)
    table_match = search(r"Table '(?P<table>[^']+)'", hand_text)
    hand_id = hand_match["hand"] if hand_match else "unknown"
    table = table_match["table"] if table_match else "unknown"
    return hand_id, table


def save_failed_hand(hand_text: str, hand_id: str, table: str) -> Path:
    """
    保存解析失败的手牌到文件。

    Args:
        hand_text: 手牌文本。
        hand_id: 手牌 ID。
        table: 牌桌名。

    Returns:
        保存的文件路径。
    """
    FAILED_HANDS_DIR.mkdir(parents=True, exist_ok=True)
    safe_table = sub(r"[^A-Za-z0-9_.-]+", "_", table)
    safe_hand = sub(r"[^0-9]+", "", hand_id) or "unknown"
    path = FAILED_HANDS_DIR / f"hand_{safe_hand}_table_{safe_table}.txt"
    path.write_text(hand_text, encoding="utf-8")
    return path


def main() -> None:
    """主函数，用于测试解析功能。"""
    if PERSISTED_HAND_HISTORY_PATH.exists():
        hand_histories = load_hand_histories(PERSISTED_HAND_HISTORY_PATH)
        total = len(hand_histories)
        print(f"从缓存恢复: {len(hand_histories)} 手")
    else:
        hand_histories, total = parse_hand_histories(HAND_HISTORY_PATH)
        save_hand_histories(PERSISTED_HAND_HISTORY_PATH, hand_histories)
        print(f"解析完成: {len(hand_histories)} / {total} 手")

    for hand_history in hand_histories[:5]:
        players = hand_history.players or []
        print(
            " | ".join(
                [
                    f"Hand {hand_history.hand}",
                    f"Table {hand_history.table}",
                    f"Time {format_time(hand_history)}",
                    f"Players {len(players)}",
                    f"Blinds {hand_history.blinds_or_straddles}",
                    f"Winnings {hand_history.winnings}",
                ]
            )
        )


if __name__ == "__main__":
    main()
