"""通信模块。

提供 Windows ↔ Linux 的 WebSocket 通信功能。
"""

from bayes_poker.comm.protocol import (
    ErrorCode,
    MessageEnvelope,
    MessageType,
    PROTOCOL_VERSION,
    generate_client_id,
    generate_request_id,
    generate_session_id,
)
    AckPayload,
    AuthPayload,
    AuthResponsePayload,
    ErrorPayload,
    HelloPayload,
    ResumePayload,
    ServerNoticePayload,
    StrategyResponsePayload,
    SubscribePayload,
)
from bayes_poker.comm.client import (
    ClientConfig,
    ConnectionState,
    WebSocketClient,
    create_client,
)
from bayes_poker.comm.session import (
    ClientSession,
    SessionConfig,
    SessionManager,
    TableSession,
)
from bayes_poker.comm.server import (
    ServerConfig,
    WebSocketServer,
    create_server,
    run_server,
)
from bayes_poker.comm.agent import (
    AgentConfig,
    TableClientAgent,
    create_agent,
)

__all__ = [
    "PROTOCOL_VERSION",
    "MessageType",
    "ErrorCode",
    "MessageEnvelope",
    "generate_client_id",
    "generate_request_id",
    "generate_session_id",
    "HelloPayload",
    "AuthPayload",
    "AuthResponsePayload",
    "SubscribePayload",
    "ResumePayload",
    "StrategyResponsePayload",
    "AckPayload",
    "ErrorPayload",
    "ServerNoticePayload",
    "ClientConfig",
    "ConnectionState",
    "WebSocketClient",
    "create_client",
    "SessionConfig",
    "ClientSession",
    "TableSession",
    "SessionManager",
    "ServerConfig",
    "WebSocketServer",
    "create_server",
    "run_server",
    "AgentConfig",
    "TableClientAgent",
    "create_agent",
]
