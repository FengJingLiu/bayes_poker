"""PHH 格式序列化与反序列化模块。

提供 pokerkit State 与 PHH (Poker Hand History) 格式之间的转换工具，
用于 client-server 之间的游戏状态传输。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pokerkit import Game, State, HandHistory

LOGGER = logging.getLogger(__name__)


@dataclass
class PHHSerializeResult:
    """PHH 序列化结果。

    Attributes:
        phh_str: PHH 格式字符串
        success: 是否成功
        error: 错误信息（如果失败）
    """

    phh_str: str
    success: bool
    error: str | None = None


@dataclass
class PHHDeserializeResult:
    """PHH 反序列化结果。

    Attributes:
        game: pokerkit Game 对象
        state: pokerkit State 对象（最新状态）
        hand_history: pokerkit HandHistory 对象
        success: 是否成功
        error: 错误信息（如果失败）
    """

    game: "Game | None"
    state: "State | None"
    hand_history: "HandHistory | None"
    success: bool
    error: str | None = None


def state_to_phh(
    game: "Game",
    state: "State",
    players: list[str] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> PHHSerializeResult:
    """将 pokerkit Game+State 序列化为 PHH 格式字符串。

    Args:
        game: pokerkit Game 对象
        state: pokerkit State 对象（可以是进行中的牌局）
        players: 玩家名称列表（可选）
        extra_fields: 额外字段写入 PHH（可选）

    Returns:
        PHHSerializeResult 包含序列化结果
    """
    try:
        from pokerkit import HandHistory
    except ImportError as e:
        return PHHSerializeResult(
            phh_str="",
            success=False,
            error=f"需要安装 pokerkit: {e}",
        )

    try:
        hh = HandHistory.from_game_state(game, state)

        if players:
            hh.players = players

        if extra_fields:
            for key, value in extra_fields.items():
                setattr(hh, key, value)

        phh_str = hh.dumps()

        LOGGER.debug("State 序列化为 PHH 成功，长度: %d", len(phh_str))
        return PHHSerializeResult(phh_str=phh_str, success=True)

    except Exception as e:
        LOGGER.warning("State 序列化失败: %s", e)
        return PHHSerializeResult(
            phh_str="",
            success=False,
            error=str(e),
        )


def phh_to_state(phh_str: str) -> PHHDeserializeResult:
    """将 PHH 格式字符串反序列化为 pokerkit State。

    Args:
        phh_str: PHH 格式字符串

    Returns:
        PHHDeserializeResult 包含恢复的 Game、State 对象
    """
    try:
        from pokerkit import HandHistory
    except ImportError as e:
        return PHHDeserializeResult(
            game=None,
            state=None,
            hand_history=None,
            success=False,
            error=f"需要安装 pokerkit: {e}",
        )

    try:
        hh = HandHistory.loads(phh_str)

        # 迭代 HandHistory 获取最终状态
        final_state = None
        for state in hh:
            final_state = state

        if final_state is None:
            return PHHDeserializeResult(
                game=None,
                state=None,
                hand_history=hh,
                success=False,
                error="无法从 PHH 恢复状态",
            )

        # 从 HandHistory 创建 Game 对象
        game = hh.create_game()

        LOGGER.debug(
            "PHH 反序列化成功，actor_index: %s, pot: %s",
            final_state.actor_index,
            final_state.total_pot_amount,
        )
        return PHHDeserializeResult(
            game=game,
            state=final_state,
            hand_history=hh,
            success=True,
        )

    except Exception as e:
        LOGGER.warning("PHH 反序列化失败: %s", e)
        return PHHDeserializeResult(
            game=None,
            state=None,
            hand_history=None,
            success=False,
            error=str(e),
        )


def extract_state_info(state: "State") -> dict[str, Any]:
    """从 pokerkit State 提取策略计算所需的关键信息。

    Args:
        state: pokerkit State 对象

    Returns:
        包含状态关键信息的字典
    """
    board_cards = [str(card) for card in state.board_cards] if state.board_cards else []

    # 确定当前街道
    board_count = len(board_cards)
    if board_count == 0:
        street = "preflop"
    elif board_count == 3:
        street = "flop"
    elif board_count == 4:
        street = "turn"
    elif board_count == 5:
        street = "river"
    else:
        street = "unknown"

    return {
        "street": street,
        "actor_index": state.actor_index,
        "board": board_cards,
        "pot": float(state.total_pot_amount),
        "stacks": [float(s) for s in state.stacks],
        "bets": [float(b) for b in state.bets] if hasattr(state, "bets") else [],
        "is_complete": state.status is False,
    }
