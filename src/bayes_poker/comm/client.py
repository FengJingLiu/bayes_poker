"""WebSocket 客户端实现。

运行在 Windows 端，负责与 Linux 策略服务器通信。
支持自动重连、消息确认、断线恢复。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from bayes_poker.comm.protocol import (
    ErrorCode,
    MessageEnvelope,
    MessageType,
    generate_client_id,
    generate_request_id,
)
from bayes_poker.comm.messages import (
    AckPayload,
    AuthPayload,
    HelloPayload,
    ResumePayload,
    SubscribePayload,
)

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)


class ConnectionState(Enum):
    """连接状态。"""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    AUTHENTICATED = auto()
    RECONNECTING = auto()


@dataclass
class PendingRequest:
    """等待响应的请求。"""

    request_id: str
    sent_at: float
    future: asyncio.Future[MessageEnvelope]


@dataclass
class ClientConfig:
    """客户端配置。"""

    server_url: str = "ws://localhost:8765/ws"
    api_key: str = ""
    client_id: str = field(default_factory=generate_client_id)

    reconnect_delay_base: float = 0.5
    reconnect_delay_max: float = 30.0
    reconnect_attempts: int = -1

    heartbeat_interval: float = 30.0
    request_timeout: float = 10.0
    ack_interval: float = 1.0

    replay_buffer_size: int = 100


MessageHandler = Callable[[MessageEnvelope], Awaitable[None] | None]


class WebSocketClient:
    """WebSocket 客户端。

    特性：
    - 自动重连（指数退避）
    - 消息序号与确认（seq/ack）
    - 断线恢复（resume）
    - 请求-响应模式（request_id 匹配）
    - 心跳保活
    """

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._ws = None

        self._send_seq = 0
        self._recv_seq = 0
        self._last_ack_seq = 0

        self._pending_requests: dict[str, PendingRequest] = {}
        self._send_buffer: deque[MessageEnvelope] = deque(
            maxlen=config.replay_buffer_size
        )

        self._handlers: dict[MessageType, list[MessageHandler]] = {}
        self._default_handler: MessageHandler | None = None

        self._reconnect_attempt = 0
        self._running = False
        self._tasks: list[asyncio.Task] = []

        self._current_session_id: str | None = None

    @property
    def state(self) -> ConnectionState:
        """当前连接状态。"""
        return self._state

    @property
    def is_connected(self) -> bool:
        """是否已连接。"""
        return self._state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED)

    @property
    def client_id(self) -> str:
        """客户端 ID。"""
        return self._config.client_id

    def on(self, msg_type: MessageType, handler: MessageHandler) -> None:
        """注册消息处理器。"""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)

    def on_default(self, handler: MessageHandler) -> None:
        """注册默认处理器。"""
        self._default_handler = handler

    async def connect(self) -> bool:
        """连接服务器。"""
        try:
            import websockets  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError("需要安装 websockets: uv add websockets") from e

        self._state = ConnectionState.CONNECTING
        LOGGER.info("正在连接: %s", self._config.server_url)

        try:
            self._ws = await websockets.connect(
                self._config.server_url,
                ping_interval=20,
                ping_timeout=10,
            )
            self._state = ConnectionState.CONNECTED
            self._reconnect_attempt = 0
            LOGGER.info("已连接")

            await self._send_hello()
            await self._authenticate()

            if self._state == ConnectionState.AUTHENTICATED:
                await self._send_resume()

            return True

        except Exception as e:
            LOGGER.error("连接失败: %s", e)
            self._state = ConnectionState.DISCONNECTED
            return False

    async def disconnect(self) -> None:
        """断开连接。"""
        self._running = False

        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._state = ConnectionState.DISCONNECTED
        LOGGER.info("已断开连接")

    async def start(self) -> None:
        """启动客户端（包含自动重连循环）。"""
        self._running = True

        while self._running:
            if not await self.connect():
                await self._handle_reconnect()
                continue

            self._tasks = [
                asyncio.create_task(self._recv_loop()),
                asyncio.create_task(self._heartbeat_loop()),
                asyncio.create_task(self._ack_loop()),
            ]

            try:
                await asyncio.gather(*self._tasks)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                LOGGER.exception("运行异常: %s", e)

            if self._running:
                await self._handle_reconnect()

    async def stop(self) -> None:
        """停止客户端。"""
        self._running = False
        await self.disconnect()

    async def send(self, msg: MessageEnvelope) -> None:
        """发送消息。"""
        if not self._ws:
            raise RuntimeError("未连接")

        self._send_seq += 1
        msg.seq = self._send_seq
        msg.client_id = self._config.client_id

        self._send_buffer.append(msg)

        data = json.dumps(msg.to_dict())
        await self._ws.send(data)

        LOGGER.debug("发送 [seq=%d]: %s", msg.seq, msg.type)

    async def request(
        self, msg: MessageEnvelope, timeout: float | None = None
    ) -> MessageEnvelope:
        """发送请求并等待响应。"""
        if timeout is None:
            timeout = self._config.request_timeout

        request_id = generate_request_id()
        msg.request_id = request_id

        loop = asyncio.get_event_loop()
        future: asyncio.Future[MessageEnvelope] = loop.create_future()

        self._pending_requests[request_id] = PendingRequest(
            request_id=request_id,
            sent_at=time.time(),
            future=future,
        )

        try:
            await self.send(msg)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise
        finally:
            self._pending_requests.pop(request_id, None)

    async def subscribe(
        self,
        session_id: str,
        table_type: str = "6max",
        blinds: tuple[float, float] = (0.5, 1.0),
    ) -> bool:
        """订阅牌桌。"""
        msg = MessageEnvelope(
            type=MessageType.SUBSCRIBE,
            session_id=session_id,
            payload=SubscribePayload(
                session_id=session_id,
                table_type=table_type,
                small_blind=blinds[0],
                big_blind=blinds[1],
            ).to_dict(),
        )

        try:
            response = await self.request(msg)
            if response.type == MessageType.ERROR:
                LOGGER.error("订阅失败: %s", response.payload)
                return False
            self._current_session_id = session_id
            return True
        except asyncio.TimeoutError:
            LOGGER.error("订阅超时")
            return False

    async def send_snapshot(self, session_id: str, payload: dict[str, Any]) -> None:
        """发送牌桌全量快照。"""
        msg = MessageEnvelope(
            type=MessageType.TABLE_SNAPSHOT,
            session_id=session_id,
            payload=payload,
        )
        await self.send(msg)

    async def _send_hello(self) -> None:
        """发送 Hello。"""
        msg = MessageEnvelope(
            type=MessageType.HELLO,
            payload=HelloPayload().to_dict(),
        )
        await self.send(msg)

    async def _authenticate(self) -> None:
        """认证。"""
        msg = MessageEnvelope(
            type=MessageType.AUTH,
            payload=AuthPayload(
                api_key=self._config.api_key,
                timestamp=int(time.time()),
            ).to_dict(),
        )

        try:
            response = await self.request(msg, timeout=5.0)
            if response.type == MessageType.AUTH_RESPONSE:
                if response.payload.get("success"):
                    self._state = ConnectionState.AUTHENTICATED
                    LOGGER.info("认证成功")
                else:
                    LOGGER.error("认证失败: %s", response.payload.get("message"))
            elif response.type == MessageType.ERROR:
                LOGGER.error("认证错误: %s", response.payload)
        except asyncio.TimeoutError:
            LOGGER.error("认证超时")

    async def _recv_loop(self) -> None:
        """接收消息循环。"""
        if not self._ws:
            return

        try:
            async for raw_message in self._ws:
                try:
                    data = json.loads(raw_message)
                    msg = MessageEnvelope.from_dict(data)
                    await self._handle_message(msg)
                except json.JSONDecodeError as e:
                    LOGGER.warning("JSON 解析失败: %s", e)
                except Exception as e:
                    LOGGER.exception("消息处理异常: %s", e)
        except Exception as e:
            LOGGER.warning("接收循环异常: %s", e)
            raise

    async def _handle_message(self, msg: MessageEnvelope) -> None:
        """处理接收到的消息。"""
        if msg.seq is not None and msg.seq > self._recv_seq:
            self._recv_seq = msg.seq

        LOGGER.debug("接收 [seq=%s]: %s", msg.seq, msg.type)

        if msg.request_id and msg.request_id in self._pending_requests:
            pending = self._pending_requests.pop(msg.request_id)
            if not pending.future.done():
                pending.future.set_result(msg)
            return

        if msg.type == MessageType.PONG:
            return

        if msg.type == MessageType.ACK:
            self._last_ack_seq = msg.payload.get("last_seq", self._last_ack_seq)
            return

        if msg.type == MessageType.ERROR:
            code = msg.payload.get("code")
            if code == ErrorCode.OUT_OF_SYNC.value:
                LOGGER.warning("状态不同步，需要重新同步")
            return

        handlers = self._handlers.get(msg.type, [])
        for handler in handlers:
            result = handler(msg)
            if asyncio.iscoroutine(result):
                await result

        if not handlers and self._default_handler:
            result = self._default_handler(msg)
            if asyncio.iscoroutine(result):
                await result

    async def _heartbeat_loop(self) -> None:
        """心跳循环。"""
        while self._running and self._ws:
            await asyncio.sleep(self._config.heartbeat_interval)

            if self._ws:
                msg = MessageEnvelope(
                    type=MessageType.PING,
                    payload={},
                )
                try:
                    await self.send(msg)
                except Exception as e:
                    LOGGER.warning("心跳发送失败: %s", e)
                    break

    async def _ack_loop(self) -> None:
        """确认循环。"""
        while self._running and self._ws:
            await asyncio.sleep(self._config.ack_interval)

            if self._recv_seq > self._last_ack_seq:
                msg = MessageEnvelope(
                    type=MessageType.ACK,
                    payload=AckPayload(last_seq=self._recv_seq).to_dict(),
                )
                try:
                    await self.send(msg)
                    self._last_ack_seq = self._recv_seq
                except Exception as e:
                    LOGGER.warning("ACK 发送失败: %s", e)

    async def _handle_reconnect(self) -> None:
        """处理重连。"""
        self._state = ConnectionState.RECONNECTING
        self._reconnect_attempt += 1

        if (
            self._config.reconnect_attempts >= 0
            and self._reconnect_attempt > self._config.reconnect_attempts
        ):
            LOGGER.error("超过最大重连次数")
            self._running = False
            return

        delay = min(
            self._config.reconnect_delay_base * (2 ** (self._reconnect_attempt - 1)),
            self._config.reconnect_delay_max,
        )

        LOGGER.info("将在 %.1f 秒后重连 (尝试 #%d)", delay, self._reconnect_attempt)
        await asyncio.sleep(delay)

    async def _send_resume(self) -> None:
        """发送恢复请求。"""
        if not self._current_session_id:
            return

        msg = MessageEnvelope(
            type=MessageType.RESUME,
            session_id=self._current_session_id,
            payload=ResumePayload(
                session_id=self._current_session_id,
                last_ack_seq=self._last_ack_seq,
            ).to_dict(),
        )
        await self.send(msg)


def create_client(
    server_url: str,
    api_key: str = "",
    client_id: str | None = None,
) -> WebSocketClient:
    """创建 WebSocket 客户端。"""
    config = ClientConfig(
        server_url=server_url,
        api_key=api_key,
        client_id=client_id or generate_client_id(),
    )
    return WebSocketClient(config)
