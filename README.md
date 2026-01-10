# bayes-poker

GGPoker Rush & Cash 手牌历史解析器，将 GGPoker 导出的手牌历史文件转换为 [pokerkit](https://pokerkit.readthedocs.io/) PHHS 格式。

## 功能特性

- 解析 GGPoker Rush & Cash 手牌历史文件
- 处理 GGPoker 特有格式（EV Cashout、Run It Twice/Three、Cash Drop 等）
- 支持单文件或批量解析
- 支持多进程并行处理
- 输出标准 PHHS（Poker Hand History Standard）格式

## 环境要求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) 包管理器

## 快速开始

### 安装依赖

```bash
uv sync
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

### 直接运行解析模块（快速验证）

```bash
uv run python -m bayes_poker.hand_history.parse_gg_poker
```

## 项目结构

```
bayes_poker/
├── src/bayes_poker/
│   ├── hand_history/       # 手牌历史解析模块
│   │   └── parse_gg_poker.py
│   ├── config/             # 配置模块
│   └── utils/              # 工具函数
├── scripts/
│   └── batch_parse_handhistory.py  # 批量解析脚本
├── tests/                  # 测试用例
└── data/                   # 数据目录
```

## 测试

**运行全部测试：**

```bash
uv run pytest
```

**运行单个测试文件：**

```bash
uv run pytest tests/test_parse_failed_hands.py
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

- [pokerkit](https://pokerkit.readthedocs.io/) - 扑克工具库，提供底层解析能力

## 许可证

MIT
