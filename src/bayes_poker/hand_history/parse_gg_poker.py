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

from bayes_poker.config.settings import get_log_level

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

    # 6. 处理 Uncalled bet returned（修复 raises-over-all-in 导致 pokerkit 无法修复的场景）
    #
    # 关键约束（避免误伤正常手牌）：
    # - 仅在 Uncalled bet 对应玩家的“上一条动作”是 raises 时才尝试修复；
    #   否则（例如 bets 场景）保持原样，因为原始文本通常可被解析。
    # - raises $X ... 必须紧邻于当前 street 内，并且 $X == Uncalled bet 返回金额；
    # - 如果 raises 与 Uncalled bet 之间存在 folds，则仅在该 street 内出现过其他玩家 all-in 时才修复，
    #   以避免将标准的“开池加注 -> 全桌弃牌 -> 退回下注”误改写为 calls。
    lines = text.split("\n")
    uncalled_pattern = compile(r"^Uncalled bet \(\$(?P<amount>[\d.]+)\) returned to (?P<player>.+)$")
    raise_pattern = compile(
        r"^(?P<player>.+?): raises \$(?P<raise_amount>[\d.]+) to \$(?P<to_amount>[\d.]+)(?P<all_in> and is all-in)?$"
    )
    street_markers = ("*** HOLE CARDS ***", "*** FLOP ***", "*** TURN ***", "*** RIVER ***")

    for uncalled_index in range(len(lines) - 1, -1, -1):
        match = uncalled_pattern.match(lines[uncalled_index])
        if not match:
            continue

        uncalled_amount = match.group("amount")
        player = match.group("player")

        # 定位当前 street 起点，防止误匹配到更早街/更远处的 raises
        street_start = 0
        for i in range(uncalled_index - 1, -1, -1):
            if lines[i] in street_markers:
                street_start = i + 1
                break

        last_action_index: int | None = None
        for i in range(uncalled_index - 1, street_start - 1, -1):
            if lines[i].startswith(f"{player}: "):
                last_action_index = i
                break

        if last_action_index is None:
            continue

        raise_match = raise_pattern.match(lines[last_action_index])
        if not raise_match:
            continue

        raise_amount = raise_match.group("raise_amount")
        is_all_in_raise = raise_match.group("all_in") is not None
        if raise_amount != uncalled_amount:
            continue

        folds_between = any(
            ": folds" in lines[i] for i in range(last_action_index + 1, uncalled_index)
        )
        all_in_before_raise = any(
            "and is all-in" in lines[i] and not lines[i].startswith(f"{player}: ")
            for i in range(street_start, last_action_index)
        )

        if folds_between and not is_all_in_raise and not all_in_before_raise:
            continue

        lines[last_action_index] = f"{player}: calls ${raise_amount}"
        del lines[uncalled_index]
        LOGGER.debug(
            "修复 Uncalled bet: player=%s amount=%s folds_between=%s all_in_before_raise=%s",
            player,
            raise_amount,
            folds_between,
            all_in_before_raise,
        )

    text = "\n".join(lines)

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
    LOGGER.setLevel(get_log_level(logging.INFO))


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
