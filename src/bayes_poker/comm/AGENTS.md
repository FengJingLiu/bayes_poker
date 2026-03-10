# comm 模块说明

> WebSocket 通信模块，负责 Windows ↔ Linux 之间的实时牌桌状态同步与策略通信。

## 模块架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          调用关系总览                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────────┐   │
│  │ Windows 端   │      │  WebSocket   │      │     Linux 端         │   │
│  │              │      │              │      │                      │   │
│  │ TableParser  │────▶│   Client     │─────▶│   WebSocketServer    │   │
│  │      │       │      │      │       │      │         │            │   │
│  │      ▼       │      │      ▼       │      │         ▼            │   │
│  │ TableContext │      │  Agent       │      │  SessionManager      │   │
│  │      │       │      │ (封装层)     │      │         │            │   │
│  │      ▼       │      │      │       │      │         ▼            │   │
│  │ ObservedTable│────▶│ sync_table   │─────▶│  _handle_table_      │   │
│  │    State     │      │    state()   │      │    snapshot()        │   │
│  │              │      │              │      │         │            │   │
│  │              │      │              │      │    ┌────┴────┐       │   │
│  │              │      │              │      │    ▼         ▼       │   │
│  │              │      │              │      │ Hero回合?  非Hero    │   │
│  │              │      │              │      │    │         │       │   │
│  │              │      │              │      │    ▼         ▼       │   │
│  │              │      │              │      │ 策略计算   更新对手   │   │
│  │              │      │              │      │            范围       │   │
│  │              │      │              │      │    │                 │   │
│  │              │      │              │      │    ▼                 │   │
│  │              │◀────│   Client     │◀─────│ STRATEGY_RESPONSE    │   │
│  │              │      │              │      │                      │   │
│  └──────────────┘      └──────────────┘      └──────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 核心文件职责

| 文件 | 职责 |
|------|------|
| `protocol.py` | 协议层：消息信封、类型定义、ID 生成器 |
| `messages.py` | 业务消息：各种 Payload 的 dataclass 定义 |
| `payload_base.py` | Payload 基类：提供 to_dict/from_dict 序列化 |
| `session.py` | 会话管理：客户端/牌桌会话、消息重放缓存、断线恢复 |
| `client.py` | WebSocket 客户端：自动重连、心跳、消息确认、请求-响应模式 |
| `server.py` | WebSocket 服务器：多客户端、认证、消息路由、策略触发 |
| `agent.py` | 客户端代理：集成 TableParser，状态同步封装 |
| `strategy_history.py` | 工具：动作序列编码为翻前 history 字符串 |

## 协议层详解

### 消息信封结构 (`MessageEnvelope`)

```python
{
    "v": 1,                    # 协议版本
    "type": "table_snapshot",  # 消息类型 (MessageType)
    "ts_ms": 1710000000000,    # 时间戳
    "session_id": "table-xxx", # 牌桌会话 ID
    "client_id": "client-xxx", # 客户端 ID
    "seq": 42,                 # 消息序号（用于确认和重放）
    "request_id": "uuid",      # 请求 ID（用于匹配响应）
    "payload": {...}           # 业务数据
}
```

### 消息类型 (`MessageType`)

| 类别 | 消息类型 | 方向 | 说明 |
|------|----------|------|------|
| 握手 | `HELLO` | C→S | 客户端版本声明 |
| 握手 | `AUTH` / `AUTH_RESPONSE` | C↔S | 认证流程 |
| 会话 | `SUBSCRIBE` / `UNSUBSCRIBE` | C→S | 订阅/取消订阅牌桌 |
| 会话 | `RESUME` | C→S | 断线恢复请求 |
| 数据 | `TABLE_SNAPSHOT` | C→S | 牌桌全量状态 |
| 数据 | `TABLE_STATE_UPDATE` | C→S | 增量状态更新（预留）|
| 数据 | `ACTION_EVENT` | C→S | 动作事件（预留）|
| 策略 | `STRATEGY_REQUEST` | C→S | 策略请求（预留）|
| 策略 | `STRATEGY_RESPONSE` | S→C | 策略响应 |
| 保活 | `PING` / `PONG` | C↔S | 心跳 |
| 确认 | `ACK` | C→S | 消息确认 |
| 控制 | `ERROR` | S→C | 错误通知 |
| 控制 | `SERVER_NOTICE` | S→C | 服务器通知 |

## 调用链详解

### 1. 连接建立流程

```
┌─────────┐     ┌──────────┐     ┌───────────────┐
│ Client  │     │  Server  │     │ SessionManager│
└────┬────┘     └────┬─────┘     └───────┬───────┘
     │               │                   │
     │  connect()    │                   │
     │──────────────▶│                   │
     │               │                   │
     │  HELLO        │                   │
     │──────────────▶│                   │
     │               │                   │
     │  AUTH         │                   │
     │──────────────▶│                   │
     │               │  create_client_   │
     │               │  session()        │
     │               │──────────────────▶│
     │  AUTH_RESPONSE│                   │
     │◀──────────────│                   │
     │               │                   │
     │ [可选] RESUME │                   │
     │──────────────▶│  handle_resume()  │
     │               │──────────────────▶│
     │               │                   │
```

### 2. 牌桌状态同步流程

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│TableParser  │   │ TableAgent  │   │   Client    │   │   Server    │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │                 │
       │ 解析到动作       │                 │                 │
       │────────────────▶│                 │                 │
       │                 │                 │                 │
       │                 │ sync_table_state│                 │
       │                 │────────────────▶│                 │
       │                 │                 │                 │
       │                 │                 │ send_snapshot() │
       │                 │                 │────────────────▶│
       │                 │                 │                 │
       │                 │                 │                 │ _handle_table_
       │                 │                 │                 │ _snapshot()
       │                 │                 │                 │
       │                 │                 │                 │ ┌──────────┐
       │                 │                 │                 │ │反序列化为│
       │                 │                 │                 │ │Observed  │
       │                 │                 │                 │ │TableState│
       │                 │                 │                 │ └────┬─────┘
       │                 │                 │                 │      │
       │                 │                 │                 │      ▼
       │                 │                 │                 │ 判断是否
       │                 │                 │                 │ Hero回合
       │                 │                 │                 │
       │                 │                 │                 │ Hero? ────▶ 策略计算
       │                 │                 │                 │ 非Hero? ──▶ 更新范围
       │                 │                 │                 │
       │                 │                 │                 │
       │                 │                 │◀────────────────│ 策略响应
       │                 │                 │                 │
       │                 │ 策略回调         │                 │
       │                 │◀────────────────│                 │
       │                 │                 │                 │
```

### 3. 断线恢复流程

```
┌─────────┐                ┌──────────┐                    ┌─────────────┐
│ Client  │                │  Server  │                    │ TableSession│
└────┬────┘                └────┬─────┘                    └──────┬──────┘
     │                          │                                 │
     │ [断开连接]               │                                 │
     │                          │                                 │
     │ [重新连接]               │                                 │
     │─────────────────────────▶│                                 │
     │                          │                                 │
     │ HELLO + AUTH             │                                 │
     │─────────────────────────▶│                                 │
     │                          │                                 │
     │ RESUME                   │                                 │
     │ (session_id,             │                                 │
     │  last_ack_seq)           │                                 │
     │─────────────────────────▶│  handle_resume()                │
     │                          │────────────────────────────────▶│
     │                          │                                 │
     │                          │                                 │ 检查 seq
     │                          │                                 │ 是否在缓存
     │                          │                                 │
     │                          │◀────────────────────────────────│
     │                          │ 返回结果:                       │
     │                          │ - 成功: 重放消息列表             │
     │                          │ - 失败: 需要全量快照             │
     │                          │                                 │
     │ [成功] 接收重放消息       │                                 │
     │◀─────────────────────────│                                 │
     │                          │                                 │
     │ [失败] 重新发送快照       │                                 │
     │─────────────────────────▶│                                 │
     │                          │                                 │
```

### 4. 策略计算触发流程

```
┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
│    Server    │   │   _trigger_       │   │  strategy_handler│
│              │   │   strategy()       │   │  (用户注入)       │
└──────┬───────┘   └────────┬─────────┘   └────────┬─────────┘
       │                    │                      │
       │ 收到 TABLE_SNAPSHOT │                     │
       │ 且是 Hero 回合      │                     │
       │                    │                      │
       │───────────────────▶│                      │
       │                    │                      │
       │                    │  1. 先更新对手范围    │
       │                    │  _update_opponent_   │
       │                    │  ranges()            │
       │                    │                      │
       │                    │  2. 构建 payload      │
       │                    │  {                   │
       │                    │    table_state,      │
       │                    │    state_version,    │
       │                    │    hero_seat,        │
       │                    │    hero_cards        │
       │                    │  }                   │
       │                    │                      │
       │                    │─────────────────────▶│
       │                    │                      │
       │                    │  用户自定义策略计算    │
       │                    │                      │
       │                    │◀─────────────────────│
       │                    │  返回: {             │
       │                    │    recommended_action│
       │                    │    recommended_amount│
       │                    │    ev, confidence... │
       │                    │  }                   │
       │                    │                      │
       │◀───────────────────│                      │
       │ 发送 STRATEGY_     │                      │
       │ RESPONSE           │                      │
       │                    │                      │
```

### 5. 对手范围更新流程

```
┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
│    Server    │   │  _update_opponent_│   │ OpponentRange    │
│              │   │    ranges()        │   │    Predictor     │
└──────┬───────┘   └────────┬─────────┘   └────────┬─────────┘
       │                    │                      │
       │ 收到 TABLE_SNAPSHOT │                     │
       │ 且非 Hero 回合      │                     │
       │                    │                      │
       │───────────────────▶│                      │
       │                    │                      │
       │                    │ 检测新手牌?          │
       │                    │ 重置范围             │
       │                    │                      │
       │                    │ 获取未处理的动作      │
       │                    │ (action_prefix)      │
       │                    │                      │
       │                    │ 遍历 pending_actions │
       │                    │                      │
       │                    │─────────────────────▶│
       │                    │                      │
       │                    │  update_range_on_    │
       │                    │  action()            │
       │                    │  每动作更新一次       │
       │                    │                      │
       │                    │◀─────────────────────│
       │                    │                      │
       │                    │ 更新处理偏移          │
       │                    │                      │
```

## 关键数据结构

### ClientSession (客户端会话)

```python
@dataclass
class ClientSession:
    client_id: str              # 客户端 ID
    websocket: Any              # WebSocket 连接对象
    authenticated: bool         # 是否已认证
    connected_at: float         # 连接时间
    last_activity: float        # 最后活动时间
    subscribed_sessions: set    # 订阅的牌桌会话
    _send_seq: int              # 发送序号
    _recv_seq: int              # 接收序号
    _last_ack_seq: int          # 最后确认的序号
```

### TableSession (牌桌会话)

```python
@dataclass
class TableSession:
    session_id: str             # 会话 ID
    client_id: str              # 所属客户端 ID
    table_type: str             # 牌桌类型 (6max/9max)
    small_blind: float          # 小盲注
    big_blind: float            # 大盲注
    state_version: int          # 状态版本
    last_snapshot: dict         # 最新快照
    last_activity: float        # 最后活动时间
    range_predictor: OpponentRangePredictor  # 该牌桌的范围预测器
    current_hand_id: str        # 当前手牌 ID
    _replay_buffer: deque       # 消息重放缓存 (seq, ts, msg)
    _client_last_ack: int       # 客户端最后确认的序号
```

### StrategyResponsePayload (策略响应)

```python
@dataclass
class StrategyResponsePayload:
    session_id: str             # 牌桌会话 ID
    state_version: int          # 触发此策略的状态版本
    request_id: str             # 请求 ID
    recommended_action: str     # 推荐动作 (fold/call/raise...)
    recommended_amount: float   # 推荐金额
    confidence: float           # 置信度
    ev: float                   # 期望值
    action_evs: dict            # 各动作的 EV
    range_breakdown: dict       # 范围分解
    notes: str                  # 备注
    is_stale: bool              # 是否过期
    compute_time_ms: int        # 计算耗时
```

## 使用示例

### 服务端启动

```python
import asyncio
from bayes_poker.comm import run_server

async def compute_strategy(session_id: str, payload: dict) -> dict:
    """自定义策略处理器。"""
    return {
        "recommended_action": "raise",
        "recommended_amount": 3.0,
        "ev": 0.15,
    }

asyncio.run(
    run_server(
        host="0.0.0.0",
        port=8765,
        api_keys={"your-api-key"},
        strategy_handler=compute_strategy,
    )
)
```

### 客户端使用

```python
import asyncio
from bayes_poker.comm import create_agent

def on_strategy(resp) -> None:
    """策略响应回调。"""
    print(f"推荐动作: {resp.recommended_action}")
    print(f"推荐金额: {resp.recommended_amount}")

agent = create_agent(
    server_url="ws://127.0.0.1:8765/ws",
    api_key="your-api-key",
    strategy_callback=on_strategy,
)

asyncio.run(agent.start())
```

### 集成 TableParser

```python
# 在解析循环中同步状态
async def parse_loop(agent: TableClientAgent, contexts: list[TableContext]):
    for idx, ctx in enumerate(contexts):
        if ctx.has_update:
            await agent.sync_table_state(idx, ctx)
```

## 可靠性机制

1. **自动重连**：指数退避策略，可配置最大重试次数
2. **消息序号**：seq/ack 机制确保消息不丢失
3. **断线恢复**：通过 replay_buffer 重放丢失的消息
4. **心跳保活**：定期 PING/PONG 检测连接状态
5. **状态版本**：过滤过期的策略响应
6. **会话隔离**：每个牌桌独立的 range_predictor

## 扩展点

- 自定义 `strategy_handler` 注入策略逻辑
- 自定义 `range_predictor` 替换对手范围预测
- 通过 `WebSocketClient.on()` 注册自定义消息处理器
- 扩展 `MessageType` 添加新消息类型
