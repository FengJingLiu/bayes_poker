from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from operator import add
from pathlib import Path
from re import DOTALL, MULTILINE, compile, search, sub

from pokerkit.notation import HandHistory, PokerStarsParser, parse_time

HAND_HISTORY_PATH = Path(
    "data/handhistory/11351348hhd_RushCash_5_NLH2SH_2025-01-12.txt"
)
PERSISTED_HAND_HISTORY_PATH = Path("data/outputs/hand_histories.phhs")
FAILED_HANDS_DIR = Path("logs/hand_history_failures")
FAILED_HANDS_LOG_PATH = Path("logs/hand_history_failures.log")
LOGGER = logging.getLogger(__name__)
CASH_DROP_MARKER = "Cash Drop to Pot"
CASHOUT_MARKERS = ("Chooses to EV Cashout", "Pays Cashout Risk")
RAISE_TO_PATTERN = compile(
    (
        r"^(?P<player>.+): raises \D?[0-9.]+ to \D?(?P<to>[0-9.]+)"
        r"(?P<all_in> and is all-in)?$"
    )
)
BET_PATTERN = compile(
    r"^(?P<player>.+): bets \D?(?P<amount>[0-9.]+)(?P<all_in> and is all-in)?$"
)
UNCALLED_BET_PATTERN = compile(
    r"^Uncalled bet \(\D?(?P<amount>[0-9.]+)\) returned to (?P<player>.+)$"
)


@dataclass
class RushCashPokerStarsParser(PokerStarsParser):
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
    try:
        amount = Decimal(raw_value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid value: {raw_value}") from exc

    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_hand_histories(path: Path) -> tuple[list[HandHistory], int]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    parser = RushCashPokerStarsParser()
    hand_texts = parser.HAND.findall(text)
    total = len(hand_texts)
    configure_logging(FAILED_HANDS_LOG_PATH)
    hand_histories: list[HandHistory] = []

    for hand_text in hand_texts:
        skip_reason = get_skip_reason(hand_text)
        if skip_reason:
            hand_id, table = extract_hand_metadata(hand_text)
            LOGGER.info(
                "跳过手牌: hand=%s table=%s reason=%s",
                hand_id,
                table,
                skip_reason,
            )
            continue
        try:
            hand_histories.append(
                parser._parse(
                    sanitize_hand_text(hand_text),
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
    if hand_history.year is None:
        return "未知时间"

    return (
        f"{hand_history.year:04d}-{hand_history.month:02d}-"
        f"{hand_history.day:02d} {hand_history.time}"
    )


def should_skip_hand(hand_text: str) -> bool:
    return get_skip_reason(hand_text) is not None


def get_skip_reason(hand_text: str) -> str | None:
    if CASH_DROP_MARKER in hand_text:
        return "cash_drop"
    return None


def sanitize_hand_text(hand_text: str) -> str:
    lines = hand_text.splitlines()
    if not any(marker in hand_text for marker in CASHOUT_MARKERS):
        return _sanitize_non_cashout_lines(lines)

    lines = [
        line
        for line in lines
        if not any(marker in line for marker in CASHOUT_MARKERS)
    ]
    return _sanitize_non_cashout_lines(lines)


def _sanitize_non_cashout_lines(lines: list[str]) -> str:
    lines = _adjust_actions_with_uncalled(lines)
    lines = _remove_muck_folds(lines)
    return "\n".join(lines)


def _adjust_actions_with_uncalled(lines: list[str]) -> list[str]:
    adjusted_lines = list(lines)
    skip_indices: set[int] = set()
    last_board_index = -1

    for index, line in enumerate(lines):
        if _is_board_line(line):
            last_board_index = index
            continue

        uncalled_match = UNCALLED_BET_PATTERN.match(line)
        if not uncalled_match:
            continue

        player = uncalled_match["player"]
        uncalled_amount = uncalled_match["amount"]
        for back in range(index - 1, last_board_index, -1):
            candidate = adjusted_lines[back]
            raise_match = RAISE_TO_PATTERN.match(candidate)
            if raise_match and raise_match["player"] == player:
                symbol = "$" if "$" in candidate else ""
                effective_value = _to_decimal(raise_match["to"]) - _to_decimal(
                    uncalled_amount
                )
                if effective_value <= 0:
                    skip_indices.add(index)
                    break
                effective = _format_amount(
                    effective_value,
                    raise_match["to"],
                    uncalled_amount,
                )
                suffix = " and is all-in" if raise_match["all_in"] else ""
                adjusted_lines[back] = (
                    f"{player}: calls {symbol}{effective}{suffix}"
                )
                skip_indices.add(index)
                break
            bet_match = BET_PATTERN.match(candidate)
            if bet_match and bet_match["player"] == player:
                symbol = "$" if "$" in candidate else ""
                effective_value = _to_decimal(bet_match["amount"]) - _to_decimal(
                    uncalled_amount
                )
                if effective_value <= 0:
                    skip_indices.add(index)
                    break
                effective = _format_amount(
                    effective_value,
                    bet_match["amount"],
                    uncalled_amount,
                )
                suffix = " and is all-in" if bet_match["all_in"] else ""
                adjusted_lines[back] = (
                    f"{player}: bets {symbol}{effective}{suffix}"
                )
                skip_indices.add(index)
                break

    return [
        line
        for index, line in enumerate(adjusted_lines)
        if index not in skip_indices
    ]


def _format_amount(amount: Decimal, left_raw: str, right_raw: str) -> str:
    scale = max(_decimal_places(left_raw), _decimal_places(right_raw))
    quantize_unit = Decimal("1").scaleb(-scale)
    return f"{amount.quantize(quantize_unit):f}"


def _decimal_places(raw: str) -> int:
    if "." not in raw:
        return 0
    return len(raw.split(".", 1)[1])


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw)


def _is_board_line(line: str) -> bool:
    return line.startswith(
        (
            "*** FLOP ***",
            "*** TURN ***",
            "*** RIVER ***",
            "*** FIRST FLOP ***",
            "*** FIRST TURN ***",
            "*** FIRST RIVER ***",
            "*** SECOND FLOP ***",
            "*** SECOND TURN ***",
            "*** SECOND RIVER ***",
        )
    )


def _remove_muck_folds(lines: list[str]) -> list[str]:
    has_show = any(": shows [" in line for line in lines)
    if not has_show:
        return lines

    river_index = _find_last_river_index(lines)
    if river_index is None:
        return lines

    filtered = []
    for index, line in enumerate(lines):
        if index > river_index and line.endswith(": folds"):
            continue
        filtered.append(line)
    return filtered


def _find_last_river_index(lines: list[str]) -> int | None:
    river_index = None
    for index, line in enumerate(lines):
        if line.startswith("*** RIVER ***"):
            river_index = index
            continue
        if line.startswith("*** FIRST RIVER ***"):
            river_index = index
            continue
        if line.startswith("*** SECOND RIVER ***"):
            river_index = index
    return river_index


def save_hand_histories(
    path: Path,
    hand_histories: Sequence[HandHistory],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        HandHistory.dump_all(hand_histories, file)


def load_hand_histories(path: Path) -> list[HandHistory]:
    with path.open("rb") as file:
        return list(HandHistory.load_all(file, parse_value=parse_value_in_cents))


def configure_logging(log_path: Path) -> None:
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
    hand_match = search(r"PokerStars Hand #(?P<hand>\d+):", hand_text)
    table_match = search(r"Table '(?P<table>[^']+)'", hand_text)
    hand_id = hand_match["hand"] if hand_match else "unknown"
    table = table_match["table"] if table_match else "unknown"
    return hand_id, table


def save_failed_hand(hand_text: str, hand_id: str, table: str) -> Path:
    FAILED_HANDS_DIR.mkdir(parents=True, exist_ok=True)
    safe_table = sub(r"[^A-Za-z0-9_.-]+", "_", table)
    safe_hand = sub(r"[^0-9]+", "", hand_id) or "unknown"
    path = FAILED_HANDS_DIR / f"hand_{safe_hand}_table_{safe_table}.txt"
    path.write_text(hand_text, encoding="utf-8")
    return path


def main() -> None:
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
