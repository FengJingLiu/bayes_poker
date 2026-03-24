## 📋 项目硬约束

1. 用中文回答输出。
2. `pokerkit` 文档: https://pokerkit.readthedocs.io/
3. 每个类、方法、函数都要添加 Google 风格中文注释, 标点用英文符号。
4. implement 和 task 统一用中文输出。
5. Python 代码必须带类型标注（Typing）。
6. 新增功能必须补测试覆盖。
7. 每个包下AGENTS.md有说明

# Agent Guide（供自动化编码代理使用）

> 约定: 与工具/模型交互用**英语**，与用户交互用**中文**。

## 项目概览

- 语言/版本: Python `>=3.12`（见 `pyproject.toml`）。
- 包管理/运行: 使用 `uv`。
- 虚拟环境 `.venv`
- 代码布局: `src/` 为可导入包, `tests/` 为测试, `scripts/` 为脚本。
- 主要依赖: `pokerkit`（文档: https://pokerkit.readthedocs.io/）。
- 可选依赖: `websockets`、`cnocr`、`opencv-python`、`pywin32`。

## 运行（run）

常用入口如下:

- 批量处理 PHHS 到 SQLite（模块入口）:
  - `uv run python -m bayes_poker.main`
- 解析手牌历史（模块入口）:
  - `uv run python -m bayes_poker.hand_history.parse_gg_poker`
- 批量解析脚本（支持目录、多进程）:
  - `uv run python scripts/batch_parse_handhistory.py <input_path> -o data/outputs -w 4`
- 构建玩家统计数据库（Rust 加速）:
  - `uv run python scripts/build_player_stats.py data/outputs -o data/database/player_stats.db`
- 导出玩家核心统计 CSV（VPIP/PFR/WTP/AGG/总手数）:
  - `uv run python scripts/export_player_core_stats_csv.py --db-path data/database/player_stats.db --output data/database/player_core_stats.csv`
- 验证 UTG open 节点 EV 调整并导出 GTO+ 文件:
  - `uv run python scripts/validate_utg_open_ev_adjustment.py --strategy-db data/database/preflop_strategy.sqlite3 --player-stats-db data/database/player_stats.db --player-csv data/database/player_core_stats.csv --output-dir data/database/utg_open_ev_validation --source-ids 1,2,3,4,5`

提示: `scripts/batch_parse_handhistory.py` 和 `scripts/build_player_stats.py` 会把 `src/` 加入 `sys.path`, 未安装 editable 也可运行。

## 构建（build）

- Python 包构建: `uv build`
- 快速语法检查: `uv run python -m compileall src`

## 测试（test）

测试框架: `pytest`（见 `pyproject.toml` 的 dev 依赖）。

### 运行全部测试

- `uv run pytest`
- 快速安静模式: `uv run pytest -q`

### 运行单个文件

- `uv run pytest tests/test_parse_failed_hands.py`

### 运行单个测试

- `uv run pytest tests/test_parse_failed_hands.py::test_extract_cash_drop_total_cents_invalid_amount_logs_warning`

### 关键字筛选

- `uv run pytest -k cash_drop`

### 大样本测试（默认跳过）

仓库定义 marker: `large_sample`（见 `pyproject.toml`）。

- 运行方式:
  - `BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample`
- 指定数据目录:
  - `GG_HANDHISTORY_DIR=/path/to/handhistory BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample`

### 常用 pytest 参数

- 失败即停: `-x` / `--maxfail=1`
- 打印 stdout: `-s`
- 详细输出: `-vv`
- 超时建议: 单条命令控制在 `60s` 内, 避免后台卡死。

## Lint / Format / Type Check（现状与建议）

现状: 仓库未默认配置 `ruff/black/mypy/pyright`。

如需引入静态检查（建议先征求维护者同意）:

- ruff:
  - 安装: `uv add --dev ruff`
  - 格式化: `uv run ruff format .`
  - 检查: `uv run ruff check .`
- mypy:
  - 安装: `uv add --dev mypy`
  - 运行: `uv run mypy src`

注意: 小功能修复不要顺手做全项目格式化或大规模 lint 清理, 除非需求明确要求。

## 代码风格（以现有代码为准）

### Imports

- 顺序: 标准库 → 第三方 → 本地包（`bayes_poker...`）。
- 优先使用标准库类型工具:
  - `from collections.abc import Sequence`
  - `from __future__ import annotations`
- 类型导入可用 `TYPE_CHECKING` 避免循环依赖。

### 格式化与排版

- 4 空格缩进。
- 多行结构使用尾逗号与垂直排列。
- Docstring 使用三引号, 并保持 Google 风格 `Args/Returns/Raises`。

### 类型（Typing）

- 公开函数必须有类型注解（Python 3.12 风格）。
- 避免滥用 `Any`。
- 返回 `None` 的语义在 docstring 中明确说明。

### 命名

- 常量: 全大写下划线。
- 私有辅助函数: `_` 前缀。
- 类: `CapWords`。
- 函数/变量: `snake_case`。

### 错误处理

- 捕获具体异常, 避免裸 `except:`。
- 需要保留上下文时使用 `raise ... from exc`。
- 可恢复错误记录日志后返回 `None` 或降级处理。

## 日志（logging）

- 日志等级由 `src/bayes_poker/config/settings.py` 控制。
- 环境变量: `BAYES_POKER_LOG_LEVEL`。
- 推荐格式:
  - `LOGGER = logging.getLogger(__name__)`
  - 使用 `%s` 参数化日志。
  - 异常堆栈使用 `LOGGER.exception(...)`。

## 文件与数据（I/O 约定）

- 使用 `pathlib.Path`。
- 文本读写显式 `encoding="utf-8"`。
- 写文件前确保目录存在: `path.parent.mkdir(parents=True, exist_ok=True)`。

## 测试风格（pytest）

- 使用 fixture 与 parametrize。
- 日志断言优先使用 `caplog`。
- 依赖外部数据的大样本测试默认跳过, 由环境变量开启。

## 开发者工具（编辑器配置）

- VSCode: `.vscode/settings.json` 已配置 `python.analysis.extraPaths = ["./src"]` 与 pytest。

## 变更原则（KISS/YAGNI）

- 改动最小化, 聚焦问题本身。
- 不在同一 PR 混合功能变更和全项目风格迁移。
- 新增工具或依赖时, 先说明收益与维护成本。

## Architecture

- **Current-Turn Slice Source**: preflop 当前决策点切片必须以 `ObservedTableState` 的只读查询接口为唯一事实源，不要再引入并维护平行的 slice/domain 对象。

## Conventions

- **PreFlopParams.previous_action 语义**: `previous_action=FOLD` 表示“该玩家在当前决策点之前尚未行动”，不是“真实上一动作就是 fold”。
- **Reentry 语义**: multi-action preflop 场景必须按“当前决策点之前的完整前缀 + 当前仍存活对手的最近一次动作”推导上下文，不能再按 actor 或 opponent 的第一次动作切片。
- **ClickHouse 查询**: 涉及 ClickHouse 查询、排障、SQL 优化或表设计时，优先使用 `clickhouse-best-practices` skill。
