# comm/ — 通信层 CLAUDE.md

> 模块路径：`src/bayes_poker/comm/`
> 职责：Windows 客户端 ↔ Linux 策略服务器的 WebSocket 双向通信

---

## 模块结构

```
comm/
├── protocol.py          # 协议定义（版本、消息类型、信封格式）
├── messages.py          # 业务 Payload 数据类
├── payload_base.py      # PayloadBase 抽象基类（to_dict）
├── server.py            # WebSocketServer（Linux 端）
├── client.py            # WebSocketClient（Windows 端）
├── agent.py             # TableClientAgent（客户端状态同步代理）
├── session.py           # ClientSession / TableSession / SessionManager
└── strategy_history.py  # 策略历史记录
```

---

## 协议格式（`protocol.py`）

**协议版本**：`PROTOCOL_VERSION = 1`

**消息信封**：
```python
MessageEnvelope(
    v=1,
    type=MessageType,          # str Enum
    ts_ms=int,                 # 毫秒时间戳
    session_id=str | None,     # 牌桌会话 ID（table-xxxxxx）
    client_id=str | None,      # 客户端 ID（client-xxxxxx）
    seq=int | None,            # 服务端发送序号（用于断线重传）
    request_id=str | None,     # 请求 UUID
    payload=dict,              # 业务数据
)
```

**消息类型**（`MessageType`）：

| 类型 | 方向 | 说明 |
|------|------|------|
| `HELLO` | C→S | 握手第一步，携带版本信息 |
| `AUTH` | C→S | API Key 认证 |
| `AUTH_RESPONSE` | S→C | 认证结果 |
| `SUBSCRIBE` | C→S | 订阅一张牌桌（创建 TableSession） |
| `UNSUBSCRIBE` | C→S | 取消订阅 |
| `RESUME` | C→S | 断线重连，携带 last_ack_seq |
| `TABLE_SNAPSHOT` | C→S | 全量牌桌状态推送 |
| `STRATEGY_RESPONSE` | S→C | 策略建议（含动作、EV、范围） |
| `ACK` | C→S | 确认已收到 seq |
| `PING/PONG` | 双向 | 心跳 |
| `ERROR` | S→C | 错误通知 |
| `SERVER_NOTICE` | S→C | 服务器公告 |

**错误码**（`ErrorCode`）：`AUTH_FAILED`, `AUTH_EXPIRED`, `SESSION_NOT_FOUND`, `OUT_OF_SYNC`, `SCHEMA_INVALID`, `RATE_LIMITED`, `INTERNAL_ERROR`, `NOT_AUTHORIZED`

---

## 服务端（`server.py`）

### `WebSocketServer`

```python
server = create_server(
    host="0.0.0.0",
    port=8765,
    api_keys={"my-secret-key"},
    ssl_certfile=None,
    strategy_handler=engine,   # StrategyHandler Protocol
)
await server.start()
```

**握手流程**：
1. 客户端发送 `HELLO`
2. 客户端发送 `AUTH`（携带 `api_key`）
3. 服务器验证并返回 `AUTH_RESPONSE`（含 `client_id`，有效期 24h）

**消息路由**：

| 消息类型 | 处理器 |
|---------|--------|
| `SUBSCRIBE` | 创建 TableSession，绑定 client |
| `RESUME` | 重放缓冲区或要求重新快照 |
| `TABLE_SNAPSHOT` | 反序列化 → 检测 Hero 回合 → 触发策略 |
| `ACK` | 更新客户端确认序号 |
| `PING` | 回复 PONG |

**关键配置**（`ServerConfig`）：
- `heartbeat_timeout=60.0s`
- `max_message_size=1MB`
- `rate_limit_per_second=100`
- 支持 SSL（`ssl_certfile` + `ssl_keyfile`）

---

## 客户端代理（`agent.py`）

### `TableClientAgent`

运行在 Windows 端，负责：
1. 维护 WebSocket 连接（`WebSocketClient`）
2. 将 `TableParser` 输出的 `ObservedTableState` 全量推送为 `TABLE_SNAPSHOT`
3. 接收 `STRATEGY_RESPONSE` 并回调 `strategy_callback`

```python
agent = create_agent(
    server_url="ws://linux-server:8765/ws",
    api_key="my-secret-key",
    strategy_callback=handle_strategy,
)
session_id = await agent.register_table(window_index=0)
await agent.sync_table_state(0, table_context)
```

**版本保护**：通过 `state_version` 丢弃过期策略响应（乱序保护）。

---

## 会话管理（`session.py`）

### `SessionManager`

- `ClientSession`：WebSocket 连接状态 + 接收序号 + 最后活跃时间
- `TableSession`：牌桌状态 + 最后快照 + 重放缓冲区（用于断线重传）
- `cleanup_expired()`：定期（60s）清理超时会话

---

## 重要约束

- 策略请求**不由客户端主动发送**，由服务器在收到 `TABLE_SNAPSHOT` 后自动判断 Hero 回合
- 客户端每次解析到新动作都发送**全量快照**（非增量），服务器维护状态一致性
- `StrategyHandler` 是 `Protocol`，任何实现 `async def __call__(session_id, observed_state) -> StrategyDecision` 的对象均可注入
