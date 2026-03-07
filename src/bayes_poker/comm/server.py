"""WebSocket 网关服务器。

运行在 Linux 端，负责接收 Windows 客户端连接并路由消息。
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from bayes_poker.comm.protocol import (
    ErrorCode,
    MessageEnvelope,
    MessageType,
    generate_request_id,
)
from bayes_poker.comm.messages import (
    AuthResponsePayload,
    ErrorPayload,
)
from bayes_poker.comm.session import (
    ClientSession,
    SessionManager,
    TableSession,
)
from bayes_poker.table.observed_state import ObservedTableState

if TYPE_CHECKING:
    from bayes_poker.strategy.opponent_range.predictor import OpponentRangePredictor

LOGGER = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """服务器配置。"""

    host: str = "0.0.0.0"
    port: int = 8765
    api_keys: set[str] = field(default_factory=set)

    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None

    heartbeat_timeout: float = 60.0
    max_message_size: int = 1024 * 1024
    rate_limit_per_second: int = 100


StrategyHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class WebSocketServer:
    """WebSocket 网关服务器。

    特性：
    - 多客户端支持
    - 认证与授权
    - 会话管理
    - 消息路由
    - 策略请求分发
    """

    def __init__(
        self,
        config: ServerConfig,
        strategy_handler: StrategyHandler | None = None,
        range_predictor: "OpponentRangePredictor | None" = None,
    ) -> None:
        """初始化 WebSocket 服务器。

        Args:
            config: 服务器配置。
            strategy_handler: 策略处理器。
            range_predictor: 对手范围预测器（可选）。
        """
        self._config = config
        self._session_manager = SessionManager()
        self._strategy_handler = strategy_handler
        self._range_predictor = range_predictor

        self._processed_action_offsets: dict[str, int] = {}
        self._last_hand_by_table: dict[str, str] = {}

        self._running = False
        self._server = None

        self._send_seq = 0

    @property
    def session_manager(self) -> SessionManager:
        """会话管理器。"""
        return self._session_manager

    def set_strategy_handler(self, handler: StrategyHandler) -> None:
        """设置策略处理器。

        Args:
            handler: 策略处理器。
        """
        self._strategy_handler = handler

    def set_range_predictor(self, predictor: "OpponentRangePredictor") -> None:
        """设置对手范围预测器。

        Args:
            predictor: 对手范围预测器。
        """
        self._range_predictor = predictor

    async def start(self) -> None:
        """启动服务器。"""
        try:
            import websockets  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError("需要安装 websockets: uv add websockets") from e

        self._running = True

        ssl_context: ssl.SSLContext | None = None
        if self._config.ssl_certfile and self._config.ssl_keyfile:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(
                certfile=self._config.ssl_certfile,
                keyfile=self._config.ssl_keyfile,
            )

        self._server = await websockets.serve(
            self._handle_connection,
            self._config.host,
            self._config.port,
            max_size=self._config.max_message_size,
            ping_interval=20,
            ping_timeout=10,
            ssl=ssl_context,
        )

        scheme = "wss" if ssl_context else "ws"
        LOGGER.info(
            "服务器启动: %s://%s:%d", scheme, self._config.host, self._config.port
        )

        cleanup_task = asyncio.create_task(self._cleanup_loop())

        await self._server.wait_closed()
        cleanup_task.cancel()

    async def stop(self) -> None:
        """停止服务器。"""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        LOGGER.info("服务器已停止")

    async def _handle_connection(self, websocket, path: str) -> None:
        """处理新连接。"""
        client_id = None

        try:
            client_id = await self._handle_handshake(websocket)
            if not client_id:
                return

            client_session = self._session_manager.create_client_session(
                client_id, websocket
            )

            LOGGER.info("客户端连接: %s", client_id)

            await self._message_loop(client_session, websocket)

        except Exception as e:
            LOGGER.exception("连接处理异常: %s", e)
        finally:
            if client_id:
                session = self._session_manager.get_client_session(client_id)
                if session:
                    session.websocket = None
                LOGGER.info("客户端断开: %s", client_id)

    async def _handle_handshake(self, websocket) -> str | None:
        """处理握手（Hello + Auth）。"""
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(raw)
            msg = MessageEnvelope.from_dict(data)

            if msg.type != MessageType.HELLO:
                await self._send_error(
                    websocket,
                    ErrorCode.SCHEMA_INVALID,
                    "期望 Hello 消息",
                )
                return None

            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            data = json.loads(raw)
            msg = MessageEnvelope.from_dict(data)

            if msg.type != MessageType.AUTH:
                await self._send_error(
                    websocket,
                    ErrorCode.SCHEMA_INVALID,
                    "期望 Auth 消息",
                )
                return None

            api_key = msg.payload.get("api_key", "")

            if self._config.api_keys and api_key not in self._config.api_keys:
                await self._send_error(
                    websocket,
                    ErrorCode.AUTH_FAILED,
                    "无效的 API Key",
                    request_id=msg.request_id,
                )
                return None

            client_id = msg.client_id or f"client-{id(websocket)}"

            response = MessageEnvelope(
                type=MessageType.AUTH_RESPONSE,
                client_id=client_id,
                request_id=msg.request_id,
                payload=AuthResponsePayload(
                    success=True,
                    client_id=client_id,
                    expires_at=int(time.time()) + 86400,
                    message="认证成功",
                ).to_dict(),
            )
            await self._send_to_websocket(websocket, response)

            return client_id

        except asyncio.TimeoutError:
            LOGGER.warning("握手超时")
            return None
        except Exception as e:
            LOGGER.warning("握手失败: %s", e)
            return None

    async def _message_loop(self, client_session: ClientSession, websocket) -> None:
        """消息处理循环。"""
        async for raw in websocket:
            try:
                data = json.loads(raw)
                msg = MessageEnvelope.from_dict(data)

                client_session.last_activity = time.time()
                if msg.seq:
                    client_session.update_recv_seq(msg.seq)

                await self._route_message(client_session, msg)

            except json.JSONDecodeError as e:
                LOGGER.warning("JSON 解析失败: %s", e)
            except Exception as e:
                LOGGER.exception("消息处理异常: %s", e)

    async def _route_message(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """路由消息到对应处理器。"""
        handlers = {
            MessageType.SUBSCRIBE: self._handle_subscribe,
            MessageType.UNSUBSCRIBE: self._handle_unsubscribe,
            MessageType.RESUME: self._handle_resume,
            MessageType.TABLE_SNAPSHOT: self._handle_table_snapshot,
            MessageType.ACK: self._handle_ack,
            MessageType.PING: self._handle_ping,
        }

        handler = handlers.get(msg.type)
        if handler:
            await handler(client_session, msg)
        else:
            LOGGER.debug("未知消息类型: %s", msg.type)

    async def _handle_subscribe(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理订阅请求。"""
        session_id = msg.payload.get("session_id") or msg.session_id
        if not session_id:
            await self._send_error_to_client(
                client_session,
                ErrorCode.SCHEMA_INVALID,
                "缺少 session_id",
                request_id=msg.request_id,
            )
            return

        table_type = msg.payload.get("table_type", "6max")
        small_blind = msg.payload.get("small_blind", 0.5)
        big_blind = msg.payload.get("big_blind", 1.0)

        table = self._session_manager.create_table_session(
            session_id=session_id,
            client_id=client_session.client_id,
            table_type=table_type,
            blinds=(small_blind, big_blind),
        )

        self._session_manager.subscribe_client_to_table(
            client_session.client_id, session_id
        )

        response = MessageEnvelope(
            type=MessageType.SERVER_NOTICE,
            session_id=session_id,
            request_id=msg.request_id,
            payload={"notice_type": "subscribed", "message": "订阅成功"},
        )
        await self._send_to_client(client_session, response)

    async def _handle_unsubscribe(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理取消订阅。"""
        session_id = msg.session_id
        if session_id:
            self._session_manager.unsubscribe_client_from_table(
                client_session.client_id, session_id
            )

    async def _handle_resume(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理断线恢复。"""
        session_id = msg.payload.get("session_id")
        last_ack_seq = msg.payload.get("last_ack_seq", 0)

        success, messages = self._session_manager.handle_resume(
            client_session.client_id, session_id, last_ack_seq
        )

        if success:
            for replay_msg in messages:
                await self._send_to_client(client_session, replay_msg)
        else:
            table = self._session_manager.get_table_session(session_id)
            if table and table.last_snapshot:
                snapshot_msg = MessageEnvelope(
                    type=MessageType.TABLE_SNAPSHOT,
                    session_id=session_id,
                    payload=table.last_snapshot,
                )
                await self._send_to_client(client_session, snapshot_msg)
            else:
                await self._send_error_to_client(
                    client_session,
                    ErrorCode.OUT_OF_SYNC,
                    "需要重新发送快照",
                    request_id=msg.request_id,
                )

    async def _handle_table_snapshot(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理牌桌快照。

        收到全量状态后：
        - 保存快照
        - 反序列化为 ObservedTableState
        - 判断是否 Hero 回合
        - Hero 回合：触发策略生成
        - 非 Hero 回合：更新对手范围

        Args:
            client_session: 客户端会话。
            msg: 消息信封。
        """
        session_id = msg.session_id
        if not session_id:
            return

        table = self._session_manager.get_table_session(session_id)
        if table:
            table.set_snapshot(msg.payload)
            table.add_to_replay_buffer(msg.seq or 0, msg)

        # 反序列化状态
        try:
            observed_state = ObservedTableState.from_dict(msg.payload)
        except Exception as e:
            LOGGER.warning("状态反序列化失败: %s", e)
            return

        hero_seat = observed_state.hero_seat
        actor_seat = observed_state.actor_seat

        # 判断是否是 Hero 回合
        is_hero_turn = actor_seat is not None and actor_seat == hero_seat

        if is_hero_turn:
            # Hero 回合：触发策略生成
            if self._strategy_handler:
                await self._trigger_strategy(client_session, session_id, observed_state)
        else:
            # 非 Hero 回合：更新对手范围
            self._update_opponent_ranges(session_id, observed_state)

    def _update_opponent_ranges(
        self, session_id: str, observed_state: ObservedTableState
    ) -> None:
        """更新对手范围。

        使用 TableSession 中的 range_predictor 来隔离每个牌桌的范围预测状态。

        Args:
            session_id: 会话 ID。
            observed_state: 观察者状态。
        """
        table = self._session_manager.get_table_session(session_id)
        if not table:
            return

        # 获取或创建该牌桌的 range_predictor
        if table.range_predictor is None:
            if self._range_predictor is not None:
                # 使用全局 predictor 的配置创建新实例
                from bayes_poker.strategy.opponent_range.predictor import (
                    create_opponent_range_predictor,
                )

                table.range_predictor = create_opponent_range_predictor(
                    preflop_strategy=self._range_predictor.preflop_strategy,
                    preflop_strategy_repository=(
                        self._range_predictor.preflop_strategy_repository
                    ),
                    preflop_strategy_source_id=(
                        self._range_predictor.preflop_strategy_source_id
                    ),
                    stats_repo=self._range_predictor.stats_repo,
                    table_type=self._range_predictor.table_type,
                )
            else:
                return

        predictor = table.range_predictor
        hero_seat = observed_state.hero_seat
        hand_id = observed_state.hand_id or "__unknown_hand__"

        # 检测新手牌，重置范围和处理偏移
        if table.current_hand_id != hand_id:
            predictor.reset_all_ranges()
            table.current_hand_id = hand_id
            self._processed_action_offsets[session_id] = 0

        player_by_seat = {
            player.seat_index: player for player in observed_state.players
        }
        history_len = len(observed_state.action_history)
        processed_offset = self._processed_action_offsets.get(session_id, 0)
        if processed_offset < 0 or processed_offset > history_len:
            processed_offset = 0

        pending_actions = observed_state.action_history[processed_offset:history_len]
        if not pending_actions:
            return

        for relative_idx, action in enumerate(pending_actions):
            if action.player_index == hero_seat:
                continue

            player = player_by_seat.get(action.player_index)
            if player is None:
                continue

            absolute_idx = processed_offset + relative_idx
            action_prefix = observed_state.action_history[:absolute_idx]
            predictor.update_range_on_action(
                player,
                action,
                observed_state,
                action_prefix=action_prefix,
            )

        self._processed_action_offsets[session_id] = history_len

    async def _trigger_strategy(
        self,
        client_session: ClientSession,
        session_id: str,
        observed_state: ObservedTableState,
    ) -> None:
        """触发策略计算。

        Args:
            client_session: 客户端会话。
            session_id: 会话 ID。
            observed_state: 观察者状态。
        """
        if not self._strategy_handler:
            return

        # 先更新对手范围
        self._update_opponent_ranges(session_id, observed_state)

        payload = {
            "table_state": observed_state.to_dict(),
            "state_version": observed_state.state_version,
            "hero_seat": observed_state.hero_seat,
            "hero_cards": list(observed_state.hero_cards)
            if observed_state.hero_cards
            else [],
        }

        try:
            start_time = time.time()
            result = await self._strategy_handler(session_id, payload)
            compute_time = int((time.time() - start_time) * 1000)

            result["compute_time_ms"] = compute_time
            result["session_id"] = session_id

            response = MessageEnvelope(
                type=MessageType.STRATEGY_RESPONSE,
                session_id=session_id,
                payload=result,
            )
            await self._send_to_client(client_session, response)

        except Exception as e:
            LOGGER.exception("策略计算失败: %s", e)

    async def _handle_ack(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理确认。"""
        last_seq = msg.payload.get("last_seq", 0)
        client_session.update_ack(last_seq)

    async def _handle_ping(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """处理心跳。"""
        response = MessageEnvelope(
            type=MessageType.PONG,
            payload={},
        )
        await self._send_to_client(client_session, response)

    async def _send_to_client(
        self, client_session: ClientSession, msg: MessageEnvelope
    ) -> None:
        """发送消息到客户端。"""
        if not client_session.websocket:
            return

        self._send_seq += 1
        msg.seq = self._send_seq

        if msg.session_id:
            table = self._session_manager.get_table_session(msg.session_id)
            if table:
                table.add_to_replay_buffer(msg.seq, msg)

        await self._send_to_websocket(client_session.websocket, msg)

    async def _send_to_websocket(self, websocket, msg: MessageEnvelope) -> None:
        """发送消息到 WebSocket。"""
        data = json.dumps(msg.to_dict())
        await websocket.send(data)

    async def _send_error(
        self,
        websocket,
        code: ErrorCode,
        message: str,
        request_id: str | None = None,
    ) -> None:
        """发送错误消息。"""
        msg = MessageEnvelope(
            type=MessageType.ERROR,
            request_id=request_id,
            payload=ErrorPayload(
                code=code.value,
                message=message,
            ).to_dict(),
        )
        await self._send_to_websocket(websocket, msg)

    async def _send_error_to_client(
        self,
        client_session: ClientSession,
        code: ErrorCode,
        message: str,
        request_id: str | None = None,
    ) -> None:
        """发送错误消息到客户端。"""
        if client_session.websocket:
            await self._send_error(client_session.websocket, code, message, request_id)

    async def _cleanup_loop(self) -> None:
        """定期清理过期会话。"""
        while self._running:
            await asyncio.sleep(60.0)
            clients, tables = self._session_manager.cleanup_expired()
            if clients or tables:
                LOGGER.info("清理过期会话: clients=%d, tables=%d", clients, tables)


def create_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    api_keys: set[str] | None = None,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    strategy_handler: StrategyHandler | None = None,
) -> WebSocketServer:
    """创建 WebSocket 服务器。"""
    config = ServerConfig(
        host=host,
        port=port,
        api_keys=api_keys or set(),
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )
    return WebSocketServer(config, strategy_handler)


async def run_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    api_keys: set[str] | None = None,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    strategy_handler: StrategyHandler | None = None,
) -> None:
    """运行服务器（便捷函数）。"""
    server = create_server(
        host, port, api_keys, ssl_certfile, ssl_keyfile, strategy_handler
    )
    await server.start()
