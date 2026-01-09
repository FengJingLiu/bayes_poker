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
from re import DOTALL, MULTILINE, compile, search, sub, finditer, escape

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

CASH_DROP_TO_POT_PATTERN = compile(
    r"^Cash Drop to Pot\s*:\s*total\s*\$(?P<amount>[\d.,]+)\s*$",
    MULTILINE,
)


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
            compile(r"^(?P<player>.+?) collected \D?(?P<winnings>[0-9.,]+) from pot"),
            None,
            int,
            add,
        ),
    }


def sanitize_hand_text(text: str) -> str:
    """
    清理 GGPoker 手牌历史文本中的非标准行。

    处理以下情况：
    1. 移除 EV Cashout 相关行
    2. 处理 Run It Twice/Three 多板面，仅保留第一个 board
    3. 合并同一玩家的多次 collected 行
    4. 移除 SHOWDOWN 前的异常 folds 行
    5. 清理 SUMMARY 中的特殊格式

    Args:
        text: 原始手牌历史文本。

    Returns:
        清理后的手牌历史文本。
    """
    # 1. 移除 EV Cashout 相关行
    text = sub(r"^.+: Chooses to EV Cashout\n", "", text, flags=MULTILINE)
    text = sub(r"^.+: Pays Cashout Risk \(\$[\d.]+\)\n", "", text, flags=MULTILINE)

    # 2. 处理 Run It Twice/Three 多板面
    if search(r"\*\*\* FIRST FLOP \*\*\*", text):
        # 将 FIRST FLOP/TURN/RIVER 替换为标准格式
        text = sub(r"\*\*\* FIRST FLOP \*\*\*", "*** FLOP ***", text)
        text = sub(r"\*\*\* FIRST TURN \*\*\*", "*** TURN ***", text)
        text = sub(r"\*\*\* FIRST RIVER \*\*\*", "*** RIVER ***", text)

        # 移除 SECOND/THIRD FLOP/TURN/RIVER 行
        text = sub(
            r"^\*\*\* SECOND (?:FLOP|TURN|RIVER) \*\*\* .+\n",
            "",
            text,
            flags=MULTILINE,
        )
        text = sub(
            r"^\*\*\* THIRD (?:FLOP|TURN|RIVER) \*\*\* .+\n",
            "",
            text,
            flags=MULTILINE,
        )

        # 处理 SHOWDOWN：保留 FIRST，移除 SECOND/THIRD
        text = sub(r"\*\*\* FIRST SHOWDOWN \*\*\*", "*** SHOWDOWN ***", text)
        text = sub(r"^\*\*\* SECOND SHOWDOWN \*\*\* *\n", "", text, flags=MULTILINE)
        text = sub(r"^\*\*\* THIRD SHOWDOWN \*\*\* *\n", "", text, flags=MULTILINE)

        # 移除多次 SHOWDOWN 后的重复 collected 行
        lines = text.split("\n")
        new_lines = []
        showdown_count = 0
        for line in lines:
            if "*** SHOWDOWN ***" in line:
                showdown_count += 1
            if showdown_count <= 1 or "collected" not in line:
                new_lines.append(line)
        text = "\n".join(new_lines)

        # 清理 SUMMARY 中的多板面信息
        text = sub(r"^Hand was run (?:twice|three) times\n", "", text, flags=MULTILINE)
        text = sub(r"^FIRST Board .+\n", "", text, flags=MULTILINE)
        text = sub(r"^SECOND Board .+\n", "", text, flags=MULTILINE)
        text = sub(r"^THIRD Board .+\n", "", text, flags=MULTILINE)

    # 3. 合并同一玩家的多次 collected 行
    collected_pattern = compile(r"^(.+?) collected \$?([\d.,]+) from pot$", MULTILINE)
    collected_matches = collected_pattern.findall(text)

    if len(collected_matches) > 1:
        # 按玩家分组并合并金额
        player_winnings: dict[str, float] = {}
        for player, amount in collected_matches:
            amount_float = float(amount.replace(",", ""))
            player_winnings[player] = player_winnings.get(player, 0) + amount_float

        # 移除所有 collected 行
        text = sub(r"^.+ collected \$?[\d.,]+ from pot\n", "", text, flags=MULTILINE)

        # 在 SHOWDOWN 后重新添加合并后的 collected 行
        showdown_match = search(r"(\*\*\* SHOWDOWN \*\*\* *\n)", text)
        if showdown_match:
            insert_pos = showdown_match.end()
            collected_lines = ""
            for player, total in player_winnings.items():
                collected_lines += f"{player} collected ${total:.2f} from pot\n"
            text = text[:insert_pos] + collected_lines + text[insert_pos:]

    # 4. 移除 SHOWDOWN 前的异常 folds 行
    # 模式 A: shows 后出现的 folds (可能夹杂 Uncalled bet)
    def remove_folds_in_block(match):
        prefix = match.group(1)  # shows line
        block = match.group(2)  # intermediate lines
        suffix = match.group(3)  # SHOWDOWN line
        # 移除 block 中的 folds 行
        cleaned_block = sub(r"^.+: folds\n", "", block, flags=MULTILINE)
        return prefix + cleaned_block + suffix

    text = sub(
        r"(: shows \[.+?\]\n)((?:.+: folds\n|Uncalled bet .+\n)+)(\*\*\* SHOWDOWN \*\*\*)",
        remove_folds_in_block,
        text,
    )
    # 模式 B: calls 后紧跟 folds (在 shows 之前)
    text = sub(
        r"(: calls .+\n)(.+: folds\n)(.+: shows)",
        r"\1\3",
        text,
    )

    # 6. 处理 Uncalled bet returned (修复 3-way all-in 解析失败)
    # 当玩家 All-in 加注量正好等于被退回的 Uncalled bet 时，说明该加注实际无人跟注，
    # 也就是该玩家实际上只是 Call 了前一个人的 All-in。
    # 我们将 "raises $X to $Y" 修改为 "calls"，并移除 Uncalled bet 行。
    matches = list(
        finditer(r"^Uncalled bet \(\$([\d.]+)\) returned to (.+)\n", text, MULTILINE)
    )
    for match in reversed(matches):
        uncalled_amt = match.group(1)
        player = match.group(2)

        start_u = match.start()
        end_u = match.end()

        # Search backwards from start_u for the player's raise
        # Simple extraction
        search_limit = max(0, start_u - 2000)  # limit lookback
        search_area = text[search_limit:start_u]
        player_esc = escape(player)

        # Last matching raise
        # Note: we need absolute position for replacement
        # 查找模式: "Player: raises $Amount to $Total [and is all-in]"
        raise_pattern = compile(
            rf"^{player_esc}: raises \$([\d.]+) to \$[\d.]+(?: and is all-in)?",
            MULTILINE,
        )
        r_matches = list(raise_pattern.finditer(search_area))

        if r_matches:
            last_r = r_matches[-1]
            if last_r.group(1) == uncalled_amt:
                # Found it!
                abs_start_r = search_limit + last_r.start()
                abs_end_r = search_limit + last_r.end()

                # Safeguard: If FOLDS occurred between the raise and the uncalled bet,
                # the raise was real (forced folds) and should NOT be converted to a call.
                # This prevents regression on standard "Raise -> Fold -> Uncalled" hands.
                intermediate_text = text[abs_end_r:start_u]
                if "folds" in intermediate_text:
                    continue

                # Replace
                # 1. Remove Uncalled line first? (It's later in text)
                # If we modify later text, earlier indices (abs_start_r) remain valid.

                text = text[:start_u] + text[end_u:]  # Remove Uncalled line

                # Now replace Raise line
                # "Player: calls" (we remove 'and is all-in' if present because uncalled return implies not all-in, or covered)
                new_action = f"{player}: calls"
                text = text[:abs_start_r] + new_action + text[abs_end_r:]

    # 5. 清理 SUMMARY 中的特殊格式
    text = sub(r", Cashout Risk \(\$[\d.]+\)", "", text)
    # 合并多次 won: "and won ($X), and won ($Y)" -> "and won ($X)"
    text = sub(r"(and won \(\$[\d.,]+\))(?:, and won \(\$[\d.,]+\))+", r"\1", text)

    return text


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


def extract_cash_drop_total_cents(hand_text: str) -> int | None:
    """
    从手牌文本中提取 Cash Drop to Pot 的金额（单位：分）。

    Returns:
        若存在 Cash Drop 行则返回金额（分），否则返回 None。
    """
    match = CASH_DROP_TO_POT_PATTERN.search(hand_text)
    if not match:
        return None

    raw_amount = match.group("amount")
    try:
        return parse_value_in_cents(raw_amount)
    except ValueError as exc:
        hand_id, table = extract_hand_metadata(hand_text)
        LOGGER.warning(
            "Cash Drop 金额解析失败: hand=%s table=%s amount=%s error=%s",
            hand_id,
            table,
            raw_amount,
            exc,
        )
        return None


def parse_hand_text(
    hand_text: str,
    parser: RushCashPokerStarsParser | None = None,
) -> HandHistory:
    """
    解析单个手牌文本为 HandHistory，并保留 Cash Drop 信息。

    说明：
    - pokerkit 的 PokerStarsParser 不会将 GGPoker 的 Cash Drop 行映射到标准动作；
      为避免信息丢失，这里将金额写入 user_defined_fields["_cash_drop_total_cents"]。
    """
    parser = parser or RushCashPokerStarsParser()

    cash_drop_total_cents = extract_cash_drop_total_cents(hand_text)
    hand_text = sanitize_hand_text(hand_text)
    hand_history = parser._parse(
        hand_text,
        parse_value=parse_value_in_cents,
    )

    if cash_drop_total_cents is not None:
        if hand_history.user_defined_fields is None:
            hand_history.user_defined_fields = {}
        hand_history.user_defined_fields["_cash_drop_total_cents"] = cash_drop_total_cents
        LOGGER.debug(
            "检测到 Cash Drop: hand=%s table=%s total_cents=%d",
            hand_history.hand,
            hand_history.table,
            cash_drop_total_cents,
        )

    return hand_history


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
        # 跳过包含 Cash Drop to Pot 的手牌（GGPoker 彩池功能）
        # if "Cash Drop to Pot" in hand_text:
        #     hand_id, table = extract_hand_metadata(hand_text)
        #     LOGGER.info("跳过 Cash Drop 手牌: hand=%s table=%s", hand_id, table)
        #     continue

        try:
            hand_histories.append(parse_hand_text(hand_text, parser=parser))
        except (KeyError, ValueError, RecursionError) as exc:
            hand_id, table = extract_hand_metadata(hand_text)
            LOGGER.warning("解析失败: hand=%s table=%s error=%s", hand_id, table, exc)
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
