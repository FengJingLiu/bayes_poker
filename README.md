# bayes-poker

`bayes-poker` 是一个面向 GGPoker 的扑克数据与策略工具集, 覆盖离线手牌解析、玩家统计构建、策略解析与可选的实时牌桌通信链路。

## 功能概览

- 手牌历史解析:
  - 解析 GGPoker Rush & Cash 文本手牌。
  - 处理 EV Cashout、Run It Twice/Three、Cash Drop 等特殊格式。
  - 支持批量解析、多进程、去重输出 `.phhs`。
- 玩家统计构建（Rust 加速）:
  - 从 `.phhs` 批量写入 SQLite。
  - 支持去重手牌追踪与统计查询。
- 策略能力:
  - 解析 GTOWizard 风格翻前策略目录。
  - 支持对手范围预测（Opponent Range）。
- 实时扩展（可选）:
  - OCR 牌桌解析（Windows 环境）。
  - WebSocket 客户端/服务端通信（Windows ↔ Linux）。

## 环境要求

- Python `>= 3.12`
- [uv](https://github.com/astral-sh/uv)

可选依赖（按功能安装）:

- 实时解析: `cnocr`, `opencv-python`, `pywin32`
- 通信: `websockets`

## 安装

```bash
uv sync
```

安装可选依赖示例:

```bash
# 实时 OCR
uv add cnocr opencv-python pywin32

# WebSocket 通信
uv add websockets
```

## 快速开始

### 1) 批量解析手牌历史

```bash
uv run python scripts/batch_parse_handhistory.py data/handhistory -o data/outputs -w 4
```

### 2) 从 PHHS 构建玩家统计数据库（Rust 加速）

```bash
uv run python scripts/build_player_stats.py data/outputs -o data/database/player_stats.db
```

查看数据库统计:

```bash
uv run python scripts/build_player_stats.py --stats data/database/player_stats.db
```

### 3) 使用模块入口执行批处理

`bayes_poker.main` 会读取环境变量并调用 Rust 批处理接口:

```bash
export BAYES_POKER_PHHS_DIR=data/outputs
export BAYES_POKER_DB_PATH=data/database/base.db
export BAYES_POKER_MAX_FILES_IN_MEMORY=200
uv run python -m bayes_poker.main
```

### 4) 查询玩家统计

```python
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.storage import PlayerStatsRepository

with PlayerStatsRepository("data/database/player_stats.db") as repo:
    stats = repo.get("player_name", TableType.SIX_MAX)
    print(stats)
```

## 策略解析与范围预测

解析翻前策略目录:

```python
from pathlib import Path
from bayes_poker.strategy import parse_strategy_directory

strategy = parse_strategy_directory(Path("/path/to/preflop_strategy/Cash6m50zSimple25Open_SimpleIP"))
print(strategy.node_count())
```

范围预测器（最小示例）:

```python
from bayes_poker.strategy import create_opponent_range_predictor

predictor = create_opponent_range_predictor()
print(predictor)
```

## 实时牌桌解析（可选）

> 该功能依赖桌面截图与 OCR, 推荐在 Windows 环境使用。

```python
from bayes_poker.table import create_manager

manager = create_manager(small_blind=0.5, big_blind=1.0, max_tables=4)
started = manager.start_all()
print(f"启动解析器数量: {started}")

# ... 业务循环 ...

manager.stop_all()
```

## 通信服务（可选）

服务端示例:

```python
import asyncio
from bayes_poker.comm import run_server

async def compute_strategy(session_id: str, payload: dict) -> dict:
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

客户端示例:

```python
import asyncio
from bayes_poker.comm import create_agent


def on_strategy(resp) -> None:
    print(resp.recommended_action, resp.recommended_amount)

agent = create_agent(
    server_url="ws://127.0.0.1:8765/ws",
    api_key="your-api-key",
    strategy_callback=on_strategy,
)

asyncio.run(agent.start())
```

## 测试

运行全部测试:

```bash
uv run pytest -q
```

运行单文件:

```bash
uv run pytest tests/test_parse_failed_hands.py
```

运行大样本回归（默认跳过）:

```bash
BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample
```

## 项目结构

```text
src/bayes_poker/
├── hand_history/            # 手牌历史解析
├── player_metrics/          # 玩家统计（含 Rust API 封装）
├── strategy/                # 策略解析、运行时、范围预测
├── storage/                 # SQLite 仓储
├── table/                   # 实时牌桌解析
├── screen/                  # 截屏与区域识别
├── ocr/                     # OCR 封装
├── comm/                    # WebSocket 通信
├── domain/                  # 领域模型
├── config/                  # 配置
└── main.py                  # 批量处理入口
```

## 常用环境变量

- `BAYES_POKER_LOG_LEVEL`: 日志级别（`DEBUG/INFO/WARNING/ERROR/CRITICAL`）。
- `BAYES_POKER_PHHS_DIR`: `bayes_poker.main` 输入目录。
- `BAYES_POKER_DB_PATH`: `bayes_poker.main` 输出数据库路径。
- `BAYES_POKER_MAX_FILES_IN_MEMORY`: Rust 批处理单批加载文件数量。
- `BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS`: 是否运行 `large_sample` 测试。
- `GG_HANDHISTORY_DIR`: 大样本测试数据目录。

## 许可证

MIT
