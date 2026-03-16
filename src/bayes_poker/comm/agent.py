"""客户端代理。

集成 TableParser 与 WebSocket 客户端，实现自动状态同步。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from bayes_poker.comm.client import WebSocketClient, create_client
from bayes_poker.comm.protocol import MessageEnvelope, MessageType, generate_session_id
from bayes_poker.comm.messages import StrategyResponsePayload

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


class TableClientAgent:
    """牌桌客户端代理。

    负责：
    - 将 TableParser 的状态全量同步到服务器
    - 接收并分发策略响应

    策略请求由服务器端自动判断触发，客户端不再主动请求。
    """

    def __init__(
        self,
        config: AgentConfig,
        strategy_callback: StrategyCallback | None = None,
    ) -> None:
        """初始化客户端代理。

        Args:
            config: 代理配置。
            strategy_callback: 策略响应回调函数。
        """
        self._config = config
        self._strategy_callback = strategy_callback

        self._client = create_client(
            server_url=config.server_url,
            api_key=config.api_key,
        )

        self._sessions: dict[int, str] = {}
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
        """处理策略响应。

        Args:
            msg: 消息信封。
        """
        session_id = msg.session_id
        state_version = msg.payload.get("state_version", 0)

        session_key = session_id or ""
        current_version = self._last_strategy_version.get(session_key, 0)
        if state_version < current_version:
            LOGGER.debug("忽略过期策略响应: %d < %d", state_version, current_version)
            return

        self._last_strategy_version[session_key] = state_version

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
                action_distribution=msg.payload.get("action_distribution", {}),
                selected_node_id=msg.payload.get("selected_node_id"),
                selected_source_id=msg.payload.get("selected_source_id"),
                sampling_random=msg.payload.get("sampling_random"),
                range_breakdown=msg.payload.get("range_breakdown", {}),
                notes=msg.payload.get("notes", ""),
                is_stale=msg.payload.get("is_stale", False),
                compute_time_ms=msg.payload.get("compute_time_ms", 0),
            )
            self._strategy_callback(response)

    async def _on_error(self, msg: MessageEnvelope) -> None:
        """处理错误。

        Args:
            msg: 消息信封。
        """
        LOGGER.error("服务器错误: %s", msg.payload)

    async def _on_notice(self, msg: MessageEnvelope) -> None:
        """处理通知。

        Args:
            msg: 消息信封。
        """
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
            window_index: 窗口索引。
            table_type: 牌桌类型。
            blinds: 盲注。

        Returns:
            会话 ID。
        """
        session_id = generate_session_id()
        self._sessions[window_index] = session_id

        if self._client.is_connected:
            await self._client.subscribe(session_id, table_type, blinds)

        return session_id

    async def unregister_table(self, window_index: int) -> None:
        """取消注册牌桌。

        Args:
            window_index: 窗口索引。
        """
        session_id = self._sessions.pop(window_index, None)
        if session_id:
            self._last_strategy_version.pop(session_id, None)

    async def sync_table_state(self, window_index: int, context: TableContext) -> None:
        """同步牌桌状态（全量发送）。

        每次解析到新动作时调用，发送完整的 ObservedTableState 到服务器。
        服务器负责判断是否需要触发策略计算。

        Args:
            window_index: 窗口索引。
            context: 牌桌上下文。
        """
        session_id = self._sessions.get(window_index)
        if not session_id or not self._client.is_connected:
            return

        if not context.observed_state:
            LOGGER.debug("无观察者状态，跳过同步")
            return

        await self._send_snapshot(session_id, context)

    async def _send_snapshot(self, session_id: str, context: TableContext) -> None:
        """发送全量快照。

        直接将 ObservedTableState 序列化后发送。

        Args:
            session_id: 会话 ID。
            context: 牌桌上下文。
        """
        if not context.observed_state:
            return

        await self._client.send_snapshot(session_id, context.observed_state.to_dict())


def create_agent(
    server_url: str,
    api_key: str = "",
    strategy_callback: StrategyCallback | None = None,
) -> TableClientAgent:
    """创建客户端代理。

    Args:
        server_url: 服务器 URL。
        api_key: API 密钥。
        strategy_callback: 策略响应回调函数。

    Returns:
        客户端代理实例。
    """
    config = AgentConfig(
        server_url=server_url,
        api_key=api_key,
    )
    return TableClientAgent(config, strategy_callback)
