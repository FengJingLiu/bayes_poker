"""客户端代理。

集成 TableParser 与 WebSocket 客户端，实现自动状态同步。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from bayes_poker.comm.client import WebSocketClient, ClientConfig, create_client
from bayes_poker.comm.protocol import MessageEnvelope, MessageType, generate_session_id
from bayes_poker.comm.messages import (
    TableSnapshotPayload,
    TableStateUpdatePayload,
    ActionEventPayload,
    StrategyRequestPayload,
    StrategyResponsePayload,
)

if TYPE_CHECKING:
    from bayes_poker.table.parser import TableContext

LOGGER = logging.getLogger(__name__)


StrategyCallback = Callable[[StrategyResponsePayload], None]


@dataclass
class AgentConfig:
    """代理配置。"""

    server_url: str = "ws://localhost:8765/ws"
    api_key: str = ""
    sync_interval: float = 0.5
    auto_request_strategy: bool = True


class TableClientAgent:
    """牌桌客户端代理。

    负责：
    - 将 TableParser 的状态同步到服务器
    - 在 Hero 行动时自动请求策略建议
    - 接收并分发策略响应
    """

    def __init__(
        self,
        config: AgentConfig,
        strategy_callback: StrategyCallback | None = None,
    ) -> None:
        self._config = config
        self._strategy_callback = strategy_callback

        self._client = create_client(
            server_url=config.server_url,
            api_key=config.api_key,
        )

        self._sessions: dict[int, str] = {}
        self._last_states: dict[str, dict[str, Any]] = {}
        self._last_strategy_version: dict[str, int] = {}

        self._running = False
        self._sync_task: asyncio.Task | None = None

        self._register_handlers()

    @property
    def client(self) -> WebSocketClient:
        """WebSocket 客户端。"""
        return self._client

    @property
    def is_connected(self) -> bool:
        """是否已连接。"""
        return self._client.is_connected

    def _register_handlers(self) -> None:
        """注册消息处理器。"""
        self._client.on(MessageType.STRATEGY_RESPONSE, self._on_strategy_response)
        self._client.on(MessageType.ERROR, self._on_error)
        self._client.on(MessageType.SERVER_NOTICE, self._on_notice)

    async def _on_strategy_response(self, msg: MessageEnvelope) -> None:
        """处理策略响应。"""
        session_id = msg.session_id
        state_version = msg.payload.get("state_version", 0)

        current_version = self._last_strategy_version.get(session_id, 0)
        if state_version < current_version:
            LOGGER.debug("忽略过期策略响应: %d < %d", state_version, current_version)
            return

        if self._strategy_callback:
            response = StrategyResponsePayload(
                session_id=session_id or "",
                state_version=state_version,
                request_id=msg.request_id or "",
                recommended_action=msg.payload.get("recommended_action", ""),
                recommended_amount=msg.payload.get("recommended_amount", 0.0),
                confidence=msg.payload.get("confidence", 0.0),
                ev=msg.payload.get("ev", 0.0),
                action_evs=msg.payload.get("action_evs", {}),
                range_breakdown=msg.payload.get("range_breakdown", {}),
                notes=msg.payload.get("notes", ""),
                is_stale=msg.payload.get("is_stale", False),
                compute_time_ms=msg.payload.get("compute_time_ms", 0),
            )
            self._strategy_callback(response)

    async def _on_error(self, msg: MessageEnvelope) -> None:
        """处理错误。"""
        LOGGER.error("服务器错误: %s", msg.payload)

    async def _on_notice(self, msg: MessageEnvelope) -> None:
        """处理通知。"""
        LOGGER.info("服务器通知: %s", msg.payload.get("message"))

    async def start(self) -> None:
        """启动代理。"""
        self._running = True

        client_task = asyncio.create_task(self._client.start())

        while self._running and not self._client.is_connected:
            await asyncio.sleep(0.1)

        await client_task

    async def stop(self) -> None:
        """停止代理。"""
        self._running = False

        if self._sync_task:
            self._sync_task.cancel()

        await self._client.stop()

    async def register_table(
        self,
        window_index: int,
        table_type: str = "6max",
        blinds: tuple[float, float] = (0.5, 1.0),
    ) -> str:
        """注册牌桌并订阅。

        Args:
            window_index: 窗口索引
            table_type: 牌桌类型
            blinds: 盲注

        Returns:
            session_id
        """
        session_id = generate_session_id()
        self._sessions[window_index] = session_id

        if self._client.is_connected:
            await self._client.subscribe(session_id, table_type, blinds)

        return session_id

    async def unregister_table(self, window_index: int) -> None:
        """取消注册牌桌。"""
        session_id = self._sessions.pop(window_index, None)
        if session_id:
            self._last_states.pop(session_id, None)
            self._last_strategy_version.pop(session_id, None)

    async def sync_table_state(self, window_index: int, context: TableContext) -> None:
        """同步牌桌状态。

        Args:
            window_index: 窗口索引
            context: 牌桌上下文
        """
        session_id = self._sessions.get(window_index)
        if not session_id or not self._client.is_connected:
            return

        state = self._context_to_state(context)
        last_state = self._last_states.get(session_id)

        if last_state is None:
            await self._send_snapshot(session_id, state)
        elif self._has_changes(last_state, state):
            await self._send_update(session_id, state, last_state)

        self._last_states[session_id] = state

        if (
            self._config.auto_request_strategy
            and self._is_hero_turn(context)
            and self._should_request_strategy(session_id, state)
        ):
            await self._request_strategy(session_id, state)

    def _context_to_state(self, context: TableContext) -> dict[str, Any]:
        """将 TableContext 转换为状态字典。"""
        players = []
        for p in context.player_states:
            players.append(
                {
                    "seat_index": p.seat_index,
                    "player_id": p.player_id,
                    "stack": p.chip_stack,
                    "bet": p.bet_size,
                    "is_folded": p.is_folded,
                    "is_button": p.is_button,
                    "is_thinking": p.is_thinking,
                    "vpip": p.vpip,
                }
            )

        hero_cards = []
        if context.hero_cards:
            hero_cards = [c.to_pokerkit_str() for c in context.hero_cards]

        board = [c.to_pokerkit_str() for c in context.board_cards]

        state_version = 0
        if context.state_bridge:
            state_version = len(context.state_bridge.get_action_history())

        return {
            "session_id": self._sessions.get(context.window_index, ""),
            "street": context.phase.name.lower(),
            "pot": context.state_bridge.total_pot if context.state_bridge else 0.0,
            "board": board,
            "hero_cards": hero_cards,
            "players": players,
            "btn_seat": context.btn_seat,
            "actor_seat": context.thinking_seat,
            "state_version": state_version,
        }

    def _has_changes(
        self, old_state: dict[str, Any], new_state: dict[str, Any]
    ) -> bool:
        """检查状态是否有变化。"""
        keys_to_check = [
            "street",
            "pot",
            "board",
            "hero_cards",
            "btn_seat",
            "actor_seat",
        ]

        for key in keys_to_check:
            if old_state.get(key) != new_state.get(key):
                return True

        old_players = old_state.get("players", [])
        new_players = new_state.get("players", [])

        if len(old_players) != len(new_players):
            return True

        for old_p, new_p in zip(old_players, new_players, strict=False):
            if old_p.get("bet") != new_p.get("bet"):
                return True
            if old_p.get("stack") != new_p.get("stack"):
                return True
            if old_p.get("is_folded") != new_p.get("is_folded"):
                return True

        return False

    def _is_hero_turn(self, context: TableContext) -> bool:
        """检查是否轮到 Hero。"""
        return context.thinking_seat == 0

    def _should_request_strategy(self, session_id: str, state: dict[str, Any]) -> bool:
        """检查是否应该请求策略。"""
        current_version = state.get("state_version", 0)
        last_version = self._last_strategy_version.get(session_id, -1)

        return current_version > last_version

    async def _send_snapshot(self, session_id: str, state: dict[str, Any]) -> None:
        """发送全量快照。"""
        payload = TableSnapshotPayload(
            session_id=session_id,
            street=state.get("street", "preflop"),
            pot=state.get("pot", 0.0),
            board=state.get("board", []),
            hero_cards=state.get("hero_cards", []),
            players=state.get("players", []),
            btn_seat=state.get("btn_seat", 0),
            actor_seat=state.get("actor_seat"),
            state_version=state.get("state_version", 0),
        )

        await self._client.send_snapshot(session_id, payload.to_dict())

    async def _send_update(
        self,
        session_id: str,
        new_state: dict[str, Any],
        old_state: dict[str, Any],
    ) -> None:
        """发送增量更新。"""
        changes = {}

        for key in ["street", "pot", "board", "hero_cards", "btn_seat", "actor_seat"]:
            if old_state.get(key) != new_state.get(key):
                changes[key] = new_state.get(key)

        if old_state.get("players") != new_state.get("players"):
            changes["players"] = new_state.get("players")

        payload = TableStateUpdatePayload(
            session_id=session_id,
            changes=changes,
            state_version=new_state.get("state_version", 0),
        )

        await self._client.send_state_update(session_id, payload.to_dict())

    async def _request_strategy(self, session_id: str, state: dict[str, Any]) -> None:
        """请求策略建议。"""
        state_version = state.get("state_version", 0)
        self._last_strategy_version[session_id] = state_version

        hero_seat = 0
        hero_player = None
        for p in state.get("players", []):
            if p.get("seat_index") == hero_seat:
                hero_player = p
                break

        payload = StrategyRequestPayload(
            session_id=session_id,
            state_version=state_version,
            street=state.get("street", "preflop"),
            pot=state.get("pot", 0.0),
            board=state.get("board", []),
            hero_cards=state.get("hero_cards", []),
            hero_seat=hero_seat,
            hero_stack=hero_player.get("stack", 0.0) if hero_player else 0.0,
            hero_position="",
        )

        await self._client.request_strategy(session_id, payload.to_dict())


def create_agent(
    server_url: str,
    api_key: str = "",
    strategy_callback: StrategyCallback | None = None,
) -> TableClientAgent:
    """创建客户端代理。"""
    config = AgentConfig(
        server_url=server_url,
        api_key=api_key,
    )
    return TableClientAgent(config, strategy_callback)
