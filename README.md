# bayes-poker

GGPoker 扑克辅助工具套件，包含手牌历史解析、实时牌桌 OCR 解析、策略计算通信等功能。

## 功能特性

### 手牌历史解析
- 解析 GGPoker Rush & Cash 手牌历史文件
- 处理 GGPoker 特有格式（EV Cashout、Run It Twice/Three、Cash Drop 等）
- 支持单文件或批量解析
- 支持多进程并行处理
- 输出标准 PHHS（Poker Hand History Standard）格式

### 实时牌桌解析 (NEW)
- Windows 端 OCR 实时解析 GGPoker 牌桌
- 自动检测游戏阶段、玩家动作、底池大小
- 动态缩放坐标系统，支持任意窗口尺寸
- 多窗口多进程并行解析（最多 8 桌）
- 集成 pokerkit.State 实时维护游戏状态

### Windows ↔ Linux 通信 (NEW)
- WebSocket 双向通信（可选 TLS：WSS）
- 自动重连与断线恢复
- 消息确认与重放缓存
- 策略请求/响应异步处理

## 环境要求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) 包管理器

## 快速开始

### 安装依赖

```bash
uv sync
```

### 安装可选依赖（实时解析/通信）

```bash
# Windows 端（牌桌解析）
uv add cnocr opencv-python pywin32

# 通信功能
uv add websockets
```

### 解析手牌历史

**解析单个文件：**

```bash
uv run python scripts/batch_parse_handhistory.py input.txt -o output/
```

**批量解析目录：**

```bash
uv run python scripts/batch_parse_handhistory.py data/handhistory/ -o output/
```

**使用多进程加速：**

```bash
uv run python scripts/batch_parse_handhistory.py data/handhistory/ -o output/ -w 4
```

### 实时牌桌解析 (Windows)

```python
from bayes_poker.table import create_manager

# 创建多牌桌管理器
manager = create_manager(small_blind=0.5, big_blind=1.0, max_tables=8)

# 启动所有解析器（自动发现 GGPoker 窗口）
manager.start_all()

# 获取解析状态
for parser_info in manager.parsers:
    ctx = parser_info.parser.context
    if ctx:
        print(f"窗口 {ctx.window_index}: {ctx.phase.name}, 底池 {ctx.state_bridge.total_pot if ctx.state_bridge else 0}")

# 停止
manager.stop_all()
```

#### 采集卡/无 HWND 场景（桌面模式）

当解析器运行在“采集卡电脑”上，只能拿到整屏画面、无法获取目标窗口 `hwnd` 时，使用桌面模式：

```python
from bayes_poker.table import create_manager

manager = create_manager(
    small_blind=0.5,
    big_blind=1.0,
    max_tables=8,
    capture_mode="desktop",
)
manager.start_all()
```

桌面模式会尝试自动识别牌桌区域（需要安装 `opencv-python`）。如果自动识别不稳定，可通过环境变量写死桌面位置（按桌面截图坐标）：

```bash
export BAYES_POKER_DESKTOP_TABLE_RECTS="0,0,1920,1080|1920,0,1920,1080|0,1080,1920,1080|1920,1080,1920,1080"
```

### 通信服务

**启动服务器 (Linux)：**

```python
import asyncio
from bayes_poker.comm import run_server

async def compute_strategy(session_id: str, payload: dict) -> dict:
    # 接入你的策略引擎
    return {"recommended_action": "raise", "recommended_amount": 3.0, "ev": 0.15}

asyncio.run(run_server(
    host="0.0.0.0",
    port=8765,
    api_keys={"your-api-key"},
    # 如需 WSS：传入证书与私钥路径（PEM）
    # ssl_certfile="/path/to/fullchain.pem",
    # ssl_keyfile="/path/to/privkey.pem",
    strategy_handler=compute_strategy,
))
```

**启动客户端 (Windows)：**

```python
import asyncio
from bayes_poker.comm import create_agent

def on_strategy(response):
    print(f"推荐: {response.recommended_action} {response.recommended_amount}")

agent = create_agent(
    # 默认 ws；如服务端启用 TLS 则用 wss
    server_url="ws://your-server.com:8765/ws",
    api_key="your-api-key",
    strategy_callback=on_strategy,
)
asyncio.run(agent.start())
```

## 项目结构

```
bayes_poker/
├── src/bayes_poker/
│   ├── hand_history/       # 手牌历史解析模块
│   ├── table/              # 实时牌桌解析模块 (NEW)
│   │   ├── layout/         # 布局配置（动态缩放）
│   │   ├── parser.py       # 多进程解析器
│   │   ├── detector.py     # 状态检测器
│   │   └── state_bridge.py # pokerkit 集成
│   ├── screen/             # 截屏与窗口管理 (NEW)
│   ├── ocr/                # OCR 引擎 (NEW)
│   ├── comm/               # 通信模块 (NEW)
│   │   ├── client.py       # WebSocket 客户端
│   │   ├── server.py       # WebSocket 服务器
│   │   └── agent.py        # TableParser 集成代理
│   ├── config/             # 配置模块
│   └── utils/              # 工具函数
├── scripts/
│   └── batch_parse_handhistory.py
├── tests/
└── data/
```

## 测试

**运行全部测试：**

```bash
uv run pytest
```

**运行牌桌解析测试：**

```bash
uv run pytest tests/test_table_parser.py -v
```

**运行大样本测试（需要本地数据集）：**

```bash
BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -k large_sample
```

## 配置

通过环境变量配置日志级别：

```bash
export BAYES_POKER_LOG_LEVEL=DEBUG  # 可选: DEBUG/INFO/WARNING/ERROR/CRITICAL
```

## 依赖

**核心依赖：**
- [pokerkit](https://pokerkit.readthedocs.io/) - 扑克工具库

**可选依赖（实时解析）：**
- [cnocr](https://github.com/breezedeus/CnOCR) - OCR 引擎
- [opencv-python](https://opencv.org/) - 图像处理
- [pywin32](https://github.com/mhammond/pywin32) - Windows API

**可选依赖（通信）：**
- [websockets](https://websockets.readthedocs.io/) - WebSocket 库

## 许可证

MIT
