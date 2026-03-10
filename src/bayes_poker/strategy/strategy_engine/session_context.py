"""strategy_engine v2 的会话内存状态。"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from bayes_poker.strategy.range import PreflopRange


@dataclass(slots=True)
class StrategySessionContext:
    """单个牌桌会话的策略上下文。"""

    session_id: str
    table_id: str
    hand_id: str
    state_version: int
    player_ranges: dict[int, PreflopRange] = field(default_factory=dict)
    player_summaries: dict[int, dict[str, str | float | int]] = field(
        default_factory=dict
    )
    last_action_fingerprint: str = ""
    last_seen_monotonic: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class StrategySessionStore:
    """管理策略引擎的会话内存。"""

    def __init__(self, *, session_timeout: float = 300.0) -> None:
        """初始化会话存储。

        Args:
            session_timeout: 会话过期秒数。
        """

        self._session_timeout = session_timeout
        self._contexts: dict[str, StrategySessionContext] = {}

    def cleanup_expired(self) -> None:
        """清理过期会话。"""

        now = time.monotonic()
        expired_keys = [
            session_id
            for session_id, context in self._contexts.items()
            if now - context.last_seen_monotonic > self._session_timeout
        ]
        for session_id in expired_keys:
            del self._contexts[session_id]

    def get_or_create(
        self,
        *,
        session_id: str,
        table_id: str,
        hand_id: str,
        state_version: int,
    ) -> StrategySessionContext:
        """获取或创建会话上下文。"""

        context = self._contexts.get(session_id)
        if context is None:
            context = StrategySessionContext(
                session_id=session_id,
                table_id=table_id,
                hand_id=hand_id,
                state_version=state_version,
            )
            self._contexts[session_id] = context
            return context

        if context.table_id != table_id or context.hand_id != hand_id:
            context = StrategySessionContext(
                session_id=session_id,
                table_id=table_id,
                hand_id=hand_id,
                state_version=state_version,
            )
            self._contexts[session_id] = context
            return context

        context.state_version = state_version
        context.last_seen_monotonic = time.monotonic()
        return context
