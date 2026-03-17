# bayes_poker — CLAUDE.md

> 生成时间：2026-03-18
> 工作目录：`/home/autumn/bayes_poker`

---

## 项目概述

`bayes_poker` 是一个**扑克实时辅助决策系统**，目标场景为 GGPoker Rush & Cash 在线扑克桌。系统通过屏幕截图 + OCR 识别当前牌局状态，将状态经 WebSocket 推送到 Linux 策略服务器，服务器运行贝叶斯推断引擎（结合 GTO 策略库与对手历史统计）实时给出行动建议。

```
Windows 客户端                   Linux 策略服务器
┌─────────────────────┐           ┌──────────────────────────────┐
│  screen/capture     │           │  comm/server (WebSocket)     │
│  ocr/engine         │──WS──────▶│  strategy_engine             │
│  table/parser       │           │    ├── opponent_pipeline      │
│  comm/agent         │◀─WS───────│    │     └── Bayesian belief  │
└─────────────────────┘           │    └── hero_resolver (GTO)   │
                                  │  storage/                     │
                                  │    ├── player_stats.db        │
                                  │    └── strategy.db            │
                                  └──────────────────────────────┘
```

---

## 技术栈

| 层次 | 语言/框架 |
|------|-----------|
| Python 包 | Python 3.12，`src/bayes_poker/` |
| Rust 扩展 | `crates/poker_stats_rs/`，通过 PyO3 暴露为 `poker_stats_rs` |
| 数据库 | SQLite（rusqlite bundled + Python sqlite3） |
| 通信 | WebSocket（`websockets` 库） |
| OCR | CnOcr（针对扑克元素定制字符集） |
| 屏幕截图 | Win32 API（`pywin32`），仅 Windows |
| 手牌历史 | pokerkit（PokerStarsParser 衍生） |
| 并行处理 | Rust rayon（手牌统计并行化） |

---

## 目录结构

```
bayes_poker/
├── src/bayes_poker/                # Python 主包
│   ├── main.py                     # 批处理入口：PHHS → SQLite
│   ├── config/
│   │   └── settings.py             # 日志级别（env: BAYES_POKER_LOG_LEVEL）
│   ├── domain/
│   │   ├── poker.py                # 扑克基础枚举（ActionType, Street）
│   │   └── table.py                # Player, PlayerAction, Position 数据类
│   ├── screen/                     # 屏幕截图模块（Windows 专属）
│   │   ├── capture.py              # ScreenCapture ABC / Win32ScreenCapture / MockScreenCapture
│   │   ├── table_region.py         # 桌面区域检测
│   │   └── types.py
│   ├── ocr/                        # OCR 引擎
│   │   ├── engine.py               # CnOcrEngine（NUMBER/CARD_RANK/TEXT 三模式）
│   │   ├── interface.py            # OCREngine ABC, OCRMode, OCRResult
│   │   └── schema.py               # Area 等结构
│   ├── table/                      # 牌桌状态解析
│   │   ├── observed_state.py       # ObservedTableState（核心数据模型，支持 JSON 序列化）
│   │   ├── parser.py               # TableParser, TableContext
│   │   ├── manager.py              # MultiTableManager（多桌管理）
│   │   ├── detector.py             # 牌桌检测
│   │   └── layout/                 # 桌型布局（gg_6max.py, base.py）
│   ├── hand_history/
│   │   └── parse_gg_poker.py       # GGPoker Rush & Cash 手牌历史解析（pokerkit）
│   ├── comm/                       # Windows ↔ Linux 通信层
│   │   ├── protocol.py             # MessageEnvelope, MessageType, ErrorCode（v1 协议）
│   │   ├── messages.py             # 各类 Payload 定义（Auth/Strategy/Ack/Error 等）
│   │   ├── server.py               # WebSocketServer（Linux 端网关）
│   │   ├── client.py               # WebSocketClient（Windows 端）
│   │   ├── agent.py                # TableClientAgent（客户端代理，状态同步）
│   │   ├── session.py              # ClientSession, TableSession, SessionManager
│   │   ├── strategy_history.py     # 策略历史记录
│   │   └── payload_base.py         # PayloadBase 基类
│   ├── player_metrics/             # 玩家统计（Python 模型层）
│   │   ├── models.py               # StatValue, ActionStats, PlayerStats
│   │   ├── enums.py                # ActionType, TableType（Python 侧）
│   │   ├── params.py               # PreFlopParams, PostFlopParams（参数索引）
│   │   ├── posterior.py            # 贝叶斯平滑：smooth_binary_counts / smooth_multinomial_counts
│   │   ├── rust_api.py             # Python 调 Rust 的入口：batch_process_phhs / load_player_stats
│   │   ├── builder.py              # Python 侧统计构建
│   │   ├── serialization.py        # player_stats_from_binary（二进制格式反序列化）
│   │   ├── analysis_helpers.py
│   │   └── core_stats_csv.py
│   ├── strategy/                   # 策略层
│   │   ├── range/                  # PreflopRange（169 手牌 + 1326 组合）
│   │   │   ├── models.py
│   │   │   └── mappings.py
│   │   ├── preflop_parse/          # GTOWizard JSON 策略导入管线
│   │   │   ├── parser.py           # 解析策略 JSON → ParsedStrategyNodeRecord
│   │   │   ├── records.py          # 节点/动作记录数据类
│   │   │   ├── models.py           # StrategyNode, StrategyAction, PreflopStrategy
│   │   │   ├── serialization.py    # PreflopRange 编解码（BLOB）
│   │   │   ├── query.py            # 节点查询
│   │   │   ├── loader.py           # 批量加载
│   │   │   └── importer.py         # 导入到 SQLite
│   │   └── strategy_engine/        # 策略引擎核心
│   │       ├── contracts.py        # StrategyDecision 联合类型 + StrategyHandler Protocol
│   │       ├── engine.py           # StrategyEngine facade + build_strategy_engine()
│   │       ├── opponent_pipeline.py# 对手贝叶斯信念更新（OpponentPipeline）
│   │       ├── hero_resolver.py    # Hero GTO 决策（HeroGtoResolver）
│   │       ├── calibrator.py       # 行动策略校准（multinomial/binary calibration）
│   │       ├── gto_policy.py       # GtoPriorPolicy / GtoPriorBuilder
│   │       ├── node_mapper.py      # 策略节点匹配（StrategyNodeMapper）
│   │       ├── context_builder.py  # 构建节点查询上下文
│   │       ├── repository_adapter.py# 策略仓库适配器
│   │       ├── stats_adapter.py    # 玩家统计适配器（PlayerNodeStatsAdapter）
│   │       ├── session_context.py  # 会话上下文存储（StrategySessionStore）
│   │       ├── core_types.py       # ActionFamily 等核心类型
│   │       ├── handler.py          # 顶层处理器组装
│   │       ├── posterior.py        # 策略后验计算
│   │       └── utg_open_ev_validation.py
│   └── storage/                    # SQLite 持久化仓库
│       ├── player_stats_repository.py  # PlayerStatsRepository（只读 + 贝叶斯平滑）
│       └── preflop_strategy_repository.py # PreflopStrategyRepository（读写）
│
├── crates/poker_stats_rs/          # Rust 扩展（PyO3 cdylib）
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs                  # PyO3 模块入口（暴露 py_* 函数）
│   │   ├── enums.rs                # TableType, Street, Position, ActionType, BetSizingCategory
│   │   ├── hand.rs                 # Hand, Action 数据结构
│   │   ├── hand_hash.rs            # 手牌去重 hash（SHA-2）
│   │   ├── phhs_parser.rs          # PHHS 文件解析
│   │   ├── player_stats.rs         # PlayerStats 统计计算
│   │   ├── action_stats.rs         # ActionStats 计数
│   │   ├── preflop_params.rs       # PreFlopParams 索引（54 桶）
│   │   ├── postflop_params.rs      # PostFlopParams 索引
│   │   ├── builder.rs              # build_player_stats_parallel（rayon 并行）
│   │   └── storage.rs              # PlayerStatsRepository（rusqlite 读写）
│   └── examples/
│       └── aggregate_sixmax.rs     # 生成 aggregated_sixmax_100 聚合玩家
│
└── data/                           # 运行时数据目录（不入版本库）
    ├── handhistory/                # GGPoker 手牌历史文件 (.txt)
    ├── outputs/                    # 解析后的 PHHS 文件
    └── database/
        ├── player_stats.db         # 玩家统计数据库
        └── strategy.db             # GTO 策略数据库
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BAYES_POKER_PHHS_DIR` | `data/outputs` | PHHS 文件目录（批处理模式） |
| `BAYES_POKER_DB_PATH` | `data/database/base.db` | SQLite 数据库路径 |
| `BAYES_POKER_MAX_FILES_IN_MEMORY` | 无（全量加载） | 每批最大 PHHS 文件数，控制内存 |
| `BAYES_POKER_LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |

---

## 数据流

### 1. 手牌历史导入（离线批处理）

```
GGPoker .txt 手牌历史
    → hand_history/parse_gg_poker.py  (pokerkit 解析)
    → .phhs 文件 (data/outputs/)
    → main.py → player_metrics/rust_api.py
    → poker_stats_rs::py_batch_process_phhs (Rust)
        ├── phhs_parser::parse_phhs_file
        ├── hand_hash::compute_hand_hash (SHA-2 去重)
        ├── builder::build_player_stats_parallel (rayon)
        └── storage::PlayerStatsRepository::upsert_batch
    → player_stats.db
```

### 2. 策略库导入

```
GTOWizard JSON 文件
    → strategy/preflop_parse/parser.py
    → strategy/preflop_parse/importer.py
    → storage/preflop_strategy_repository.py
    → strategy.db (solver_nodes + solver_actions 表)
```

### 3. 实时决策流程（在线）

```
Win32 屏幕截图 → OCR → TableParser → ObservedTableState
    → comm/agent.py::sync_table_state
    → WebSocket TABLE_SNAPSHOT
    → comm/server.py::_handle_table_snapshot
    → 检测是否 Hero 回合
    → strategy_engine/engine.py::__call__
        ├── opponent_pipeline.py::process_hero_snapshot
        │     ├── 构建 GTO 先验策略（StrategyNodeMapper + GtoPriorBuilder）
        │     ├── 加载玩家统计（PlayerNodeStatsAdapter）
        │     └── 贝叶斯信念更新（_adjust_belief_with_stats_and_ev）
        └── hero_resolver.py::resolve
    → StrategyDecision → STRATEGY_RESPONSE
    → TableClientAgent::_on_strategy_response
```

---

## 核心数据模型

### `ObservedTableState`（`table/observed_state.py`）
WebSocket 传输的核心状态对象，支持 `to_dict()` / `from_dict()` 完整序列化。

| 字段 | 类型 | 说明 |
|------|------|------|
| `table_id` | `str` | 牌桌标识 |
| `street` | `Street` | preflop/flop/turn/river |
| `hero_seat` | `int` | Hero 座位 |
| `actor_seat` | `int \| None` | 当前行动玩家座位 |
| `hero_cards` | `tuple[str,str] \| None` | Hero 底牌 |
| `players` | `list[Player]` | 各座位状态 |
| `action_history` | `list[PlayerAction]` | 当前手牌动作序列 |
| `state_version` | `int` | 单调递增版本号 |

### `StrategyDecision`（`strategy/strategy_engine/contracts.py`）
引擎返回的联合类型：

| 类型 | 含义 |
|------|------|
| `RecommendationDecision` | 有推荐动作（含 EV、置信度、范围分解） |
| `NoResponseDecision` | 非 Hero 回合，无需响应 |
| `UnsupportedScenarioDecision` | 超出支持矩阵（如翻后多方向） |
| `SafeFallbackDecision` | 可降级错误 |

### `PlayerStats` / `ActionStats`（`player_metrics/models.py`）
- `ActionStats`：7 维计数（fold/check_call/bet_0_40/bet_40_80/bet_80_120/bet_over_120/raise）
- `PlayerStats`：玩家名 + 桌型 + VPIP + preflop 统计数组（54 桶）+ postflop 统计数组

---

## WebSocket 协议

版本：`v=1`，消息格式为 `MessageEnvelope`：

```json
{
  "v": 1,
  "type": "<MessageType>",
  "ts_ms": 1234567890000,
  "session_id": "table-xxxx",
  "client_id": "client-xxxx",
  "seq": 42,
  "request_id": "uuid",
  "payload": {}
}
```

**握手流程**：`HELLO → AUTH → AUTH_RESPONSE`
**会话流程**：`SUBSCRIBE → TABLE_SNAPSHOT* → STRATEGY_RESPONSE`
**恢复流程**：`RESUME → 重放缓冲区 / TABLE_SNAPSHOT`

---

## SQLite Schema 速览

### `player_stats.db`

| 表 | 说明 |
|----|------|
| `player_stats` | `player_name, table_type, stats_binary(BLOB)` |
| `processed_hands` | `hand_hash TEXT PK, processed_at TEXT`（去重记录） |

### `strategy.db`

| 表 | 说明 |
|----|------|
| `strategy_sources` | `source_id, strategy_name, source_dir, format_version` |
| `solver_nodes` | `node_id, source_id, stack_bb, history_full, actor_position, ...` |
| `solver_actions` | `action_id, node_id, action_code, strategy_blob, ev_blob, ...` |

---

## Rust 扩展（`poker_stats_rs`）

PyO3 cdylib，暴露以下函数给 Python：

| 函数 | 说明 |
|------|------|
| `py_batch_process_phhs(dir, db, max_files)` | 批量处理 PHHS → SQLite（含去重） |
| `py_build_stats(hands_json, table_type)` | 内存中构建统计（无持久化） |
| `py_build_and_save_stats(hands_json, tt, db)` | 构建并写入 SQLite |
| `py_load_player_stats(db, names)` | 读取玩家统计（简单视图） |
| `py_load_player_stats_full(db, names, tt)` | 读取完整统计（含预翻后分桶） |

**聚合玩家**：`cargo run --example aggregate_sixmax` 生成 `aggregated_sixmax_100`，用作贝叶斯先验池。

---

## 关键算法：贝叶斯信念更新

位于 `strategy/strategy_engine/opponent_pipeline.py`：

1. **GTO 先验**：从 `strategy.db` 匹配策略节点，构建 169 手牌维度的先验概率分布
2. **统计校准**：用玩家历史 VPIP/fold/call/raise 频率（贝叶斯平滑后）重分配先验质量
3. **激进行为混合**：当行动为 raise/bet 时，混合全局 PFR 信号（`enable_global_raise_blending`）
4. **EV 排序**：增质量优先给高 EV 手牌，减质量从低 EV 手牌剪除

平滑算法（`player_metrics/posterior.py`）：
- **二元节点**（binary）：Beta 后验
- **多元节点**（multinomial）：Dirichlet 后验
- **先验强度**：`pool_prior_strength=20.0`（等效先验样本数）

---

## 开发注意事项

### Rust 扩展构建
```bash
cd crates/poker_stats_rs
cargo build --release
# 生成 .so 放入 Python 可发现路径
```

### Python 虚拟环境
```bash
# 项目使用 .venv（uv 管理）
uv sync
```

### 数据准备
1. 将 GGPoker 手牌历史放入 `data/handhistory/`
2. 解析为 PHHS：运行 `hand_history/parse_gg_poker.py`
3. 批处理导入：`python -m bayes_poker.main`
4. 生成聚合玩家：`cargo run --example aggregate_sixmax`
5. 导入 GTO 策略（GTOWizard JSON）：`strategy/preflop_parse/importer.py`

### 测试
Rust 单元测试：
```bash
cargo test -p poker_stats_rs
```
Python 测试：尚无测试框架配置，推荐使用 `pytest`。

---

## 模块级 CLAUDE.md 索引

| 模块 | 文档 |
|------|------|
| `comm/` | [`src/bayes_poker/comm/CLAUDE.md`](src/bayes_poker/comm/CLAUDE.md) |
| `strategy/strategy_engine/` | [`src/bayes_poker/strategy/strategy_engine/CLAUDE.md`](src/bayes_poker/strategy/strategy_engine/CLAUDE.md) |
| `storage/` | [`src/bayes_poker/storage/CLAUDE.md`](src/bayes_poker/storage/CLAUDE.md) |
| `crates/poker_stats_rs/` | [`crates/poker_stats_rs/CLAUDE.md`](crates/poker_stats_rs/CLAUDE.md) |
