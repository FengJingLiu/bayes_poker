"""策略请求的行动历史编码。

将 `PokerKitStateBridge` 的动作序列编码为翻前策略文件使用的 history 前缀：
    F / C / R{size_bb} / RAI
"""

from __future__ import annotations

from bayes_poker.table.state_bridge import ActionType, PlayerAction


def _format_bb(value: float) -> str:
    rounded = round(float(value), 2)
    text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def build_preflop_history(actions: list[PlayerAction], *, big_blind: float) -> str:
    """将动作序列编码为翻前 history 字符串。"""
    bb = float(big_blind) if big_blind and big_blind > 0 else 0.0
    tokens: list[str] = []

    for action in actions:
        match action.action_type:
            case ActionType.FOLD:
                tokens.append("F")
            case ActionType.CALL | ActionType.CHECK:
                tokens.append("C")
            case ActionType.BET | ActionType.RAISE:
                size_bb = (float(action.amount) / bb) if bb > 0 else float(action.amount)
                tokens.append(f"R{_format_bb(size_bb)}")
            case ActionType.ALL_IN:
                tokens.append("RAI")
            case _:
                continue

    return "-".join(tokens)

