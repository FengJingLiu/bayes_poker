"""Preflop 行动线解析与 token 生成。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ActionType(Enum):
    FOLD = "FOLD"
    LIMP = "LIMP"
    OPEN = "OPEN"
    CALL = "CALL"
    THREE_BET = "3B"
    FOUR_BET = "4B"
    FIVE_BET_PLUS = "5B+"
    ALL_IN = "ALLIN"


@dataclass
class PreflopAction:
    position: str
    action_type: ActionType
    amount: int | None = None


# pokerkit action patterns
# 格式：p<index> <action> [args] 或 d <deal_type> [cards]
PLAYER_ACTION_PATTERN = re.compile(r"^p(\d+)\s+(cbr|cc|f|sm)\s*(.*)$")
DEAL_BOARD_PATTERN = re.compile(r"^d\s+db\s+")
DEAL_HOLE_PATTERN = re.compile(r"^d\s+dh\s+")


def parse_preflop_actions(
    actions: list[str],
    position_map: dict[int, str],
    blinds_count: int = 2,
) -> list[PreflopAction]:
    """
    解析 preflop 行动。

    Args:
        actions: pokerkit action 列表
        position_map: seat_index (0-based) -> position 映射
        blinds_count: 盲注数量（通常2）

    Returns:
        PreflopAction 列表
    """
    result: list[PreflopAction] = []
    player_count = len(position_map)

    if player_count == 0:
        return result

    raise_count = 0
    has_open = False

    for action in actions:
        action = action.strip()

        if DEAL_BOARD_PATTERN.match(action):
            break

        if DEAL_HOLE_PATTERN.match(action) or action.startswith("d "):
            continue

        match = PLAYER_ACTION_PATTERN.match(action)
        if not match:
            continue

        player_idx = int(match.group(1)) - 1
        action_code = match.group(2)
        action_args = match.group(3).strip()

        position = position_map.get(player_idx)
        if not position:
            continue

        if action_code == "f":
            result.append(PreflopAction(position, ActionType.FOLD))

        elif action_code == "cc":
            if not has_open:
                result.append(PreflopAction(position, ActionType.LIMP))
            else:
                result.append(PreflopAction(position, ActionType.CALL))

        elif action_code == "cbr":
            amount = _parse_amount(action_args)

            if not has_open:
                has_open = True
                raise_count = 1
                result.append(PreflopAction(position, ActionType.OPEN, amount))
            else:
                raise_count += 1
                if raise_count == 2:
                    result.append(PreflopAction(position, ActionType.THREE_BET, amount))
                elif raise_count == 3:
                    result.append(PreflopAction(position, ActionType.FOUR_BET, amount))
                else:
                    result.append(
                        PreflopAction(position, ActionType.FIVE_BET_PLUS, amount)
                    )

    return result

    current_actor_idx = blinds_count % player_count
    raise_count = 0
    has_open = False

    for action in actions:
        action = action.strip()

        if DEAL_BOARD_PATTERN.match(action):
            break

        if DEAL_HOLE_PATTERN.match(action) or action.startswith("d "):
            continue

        match = ACTION_PATTERN.match(action)
        if not match:
            continue

        action_code = match.group(1)
        action_args = match.group(2).strip()

        position = position_map.get(current_actor_idx)
        if not position:
            current_actor_idx = (current_actor_idx + 1) % player_count
            continue

        if action_code == "f":
            result.append(PreflopAction(position, ActionType.FOLD))

        elif action_code == "cc":
            if not has_open:
                result.append(PreflopAction(position, ActionType.LIMP))
            else:
                result.append(PreflopAction(position, ActionType.CALL))

        elif action_code == "cbr":
            amount = _parse_amount(action_args)

            if not has_open:
                has_open = True
                raise_count = 1
                result.append(PreflopAction(position, ActionType.OPEN, amount))
            else:
                raise_count += 1
                if raise_count == 2:
                    result.append(PreflopAction(position, ActionType.THREE_BET, amount))
                elif raise_count == 3:
                    result.append(PreflopAction(position, ActionType.FOUR_BET, amount))
                else:
                    result.append(
                        PreflopAction(position, ActionType.FIVE_BET_PLUS, amount)
                    )

        current_actor_idx = (current_actor_idx + 1) % player_count

    return result


def _parse_amount(args: str) -> int | None:
    if not args:
        return None
    try:
        return int(args.split()[0])
    except (ValueError, IndexError):
        return None


def generate_preflop_tokens(preflop_actions: list[PreflopAction]) -> str:
    """
    生成用于 FTS5 检索的 preflop token 字符串。

    格式: "UTG_OPEN BTN_3B CO_FOLD"
    """
    tokens = []
    for action in preflop_actions:
        token = f"{action.position}_{action.action_type.value}"
        tokens.append(token)
    return " ".join(tokens)


def generate_preflop_signature(preflop_actions: list[PreflopAction]) -> str:
    """
    生成人类可读的 preflop 签名。

    格式: "UTG open -> BTN 3B -> UTG call"
    """
    parts = []
    for action in preflop_actions:
        action_str = action.action_type.value.lower()
        parts.append(f"{action.position} {action_str}")
    return " -> ".join(parts)


def extract_board_tokens(actions: list[str]) -> str:
    """
    从 actions 中提取 board tokens。

    Returns:
        格式如 "Td4s8d|2h|7d" (flop|turn|river)
    """
    boards = []

    for action in actions:
        action = action.strip()
        if DEAL_BOARD_PATTERN.match(action):
            cards = action.split()[2:]
            boards.append("".join(cards))

    if not boards:
        return ""

    return "|".join(boards)
