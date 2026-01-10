# Agent Guide（供自动化编码代理使用）

> 约定：在本仓库内一律使用**简体中文**沟通/输出（包括 PR/commit message 建议、注释、日志文案）。

## 项目概览
- 语言/版本：Python `>=3.12`（见 `pyproject.toml`）。
- 包管理/运行：使用 `uv`。
- 代码布局：`src/` 下为可导入包；测试在 `tests/`；脚本在 `scripts/`。
- 主要依赖：`pokerkit`（文档：https://pokerkit.readthedocs.io/）。

## 快速开始（环境）
- 创建并同步虚拟环境：
  - `uv sync`
- 在 uv 环境中运行任意命令：
  - `uv run <command ...>`
- 新增依赖：
  - 运行时依赖：`uv add <package>`
  - 开发依赖（例如测试/工具）：`uv add --dev <package>`
- 修改依赖后更新锁文件：
  - `uv sync`

## 运行（run）
当前仓库根目录未提供 `main.py` 入口文件；可用入口主要来自模块或脚本：

- 直接运行解析模块的 main（推荐用于快速验证解析逻辑）：
  - `uv run python -m bayes_poker.hand_history.parse_gg_poker`
- 批量解析脚本（支持目录、多进程、输出目录）：
  - `uv run python scripts/batch_parse_handhistory.py <input_path> -o data/outputs -w 4`

提示：脚本 `scripts/batch_parse_handhistory.py` 会把 `src/` 加入 `sys.path`，因此即使未安装为 editable 也可运行。

## 构建（build）
本项目是标准 PEP 621 `pyproject.toml` 结构，可使用 uv 构建包（如需）：
- `uv build`

如果只想做“语法/导入”级别的快速检查（不运行测试）：
- `uv run python -m compileall src`

## 测试（test）
测试框架：`pytest`（见 `pyproject.toml` 的 dev 依赖）。

### 运行全部测试
- `uv run pytest`
- 快速安静模式：`uv run pytest -q`

### 运行单个文件
- `uv run pytest tests/test_parse_failed_hands.py`

### 运行单个测试（最重要）
- 通过 nodeid：
  - `uv run pytest tests/test_parse_failed_hands.py::test_extract_cash_drop_total_cents_invalid_amount_logs_warning`

### 只跑匹配的用例
- 通过关键字筛选：
  - `uv run pytest -k cash_drop`

### 大样本测试（默认跳过）
仓库定义了 marker：`large_sample`（见 `pyproject.toml`）。
- 默认行为：大样本测试会 `pytest.skip`，避免 CI / 日常测试依赖外部数据、避免过慢。
- 运行方式：
  - `BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample`
- 可指定数据目录（本地手牌数据集不在仓库内）：
  - `GG_HANDHISTORY_DIR=/path/to/handhistory BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1 uv run pytest -q -k large_sample`

### 常用 pytest 调试参数
- 失败即停：`-x` 或 `--maxfail=1`
- 打印 stdout：`-s`
- 详细输出：`-vv`

## Lint / Format / Type Check（现状与建议）
现状：仓库当前**未配置** ruff/black/mypy/pyright 等工具（未发现 `.pre-commit-config.yaml`、`ruff.toml`、`mypy.ini` 等）。

如果你要引入静态检查（建议先征求维护者同意）：
- 首选 ruff（lint + format 一体化）：
  - 安装：`uv add --dev ruff`
  - 格式化：`uv run ruff format .`
  - 检查：`uv run ruff check .`
- 类型检查可选 mypy：
  - 安装：`uv add --dev mypy`
  - 运行：`uv run mypy src`

注意：不要在“修 bug/加小功能”时顺手引入全项目格式化或大范围 lint 修复，除非需求明确要求。

## 代码风格（以现有代码为准）
本仓库当前有效代码主要集中在 `src/bayes_poker/hand_history/parse_gg_poker.py`、`scripts/batch_parse_handhistory.py` 与 `tests/`。

### Imports
- 分组顺序：标准库 → 第三方 → 本地包（`bayes_poker...`）。
- 标准库 typing/ABC 优先使用：
  - `from collections.abc import Sequence`
  - `from __future__ import annotations`（当文件内大量用到 `|`、`list[...]` 等注解时）
- 避免循环导入；仅类型用途可使用：
  - `from typing import TYPE_CHECKING` + `if TYPE_CHECKING: ...`

### 格式化/排版
- 缩进：4 空格。
- 多行调用/字典/列表：使用尾逗号与垂直排列（参考 `parse_gg_poker.py` 中 regex、日志调用风格）。
- Docstring：建议用三引号，中文描述清晰；对外函数保持 `Args/Returns/Raises`。

### 类型（typing）
- 尽量为公开函数提供类型注解，使用 Python 3.12 风格：`int | None`、`list[T]`、`dict[K, V]`。
- 避免滥用 `Any`；若确实需要，优先缩小范围并加注释说明原因。
- 返回 `None` 的语义必须在 docstring 中写清楚（例如 `extract_cash_drop_total_cents`）。

### 命名（naming）
- 常量：全大写 + 下划线（例如 `FAILED_HANDS_LOG_PATH`）。
- 正则：`*_PATTERN` 或与语义一致的全大写变量名。
- 私有辅助函数：前缀 `_`（测试内 helper 也可以 `_foo`）。
- 类：`CapWords`；函数/变量：`snake_case`。

### 错误处理（error handling）
- 优先捕获具体异常（例如 `InvalidOperation`、`ValueError`、`KeyError`），避免裸 `except:`。
- 需要保留上下文时使用异常链：`raise ... from exc`。
- 解析类逻辑：
  - “可恢复”的解析失败：记录 warning/debug 后返回 `None` 或尝试修复器（参考 `repair_uncalled_bet_returned_for_raise_over_all_in`）。
  - “不可恢复”的失败：在调用方集中捕获并记录失败样本（参考 `parse_hand_histories`）。

## 日志（logging）
仓库要求：关键路径必须加日志。

- 日志等级由 `src/bayes_poker/config/settings.py` 控制：
  - 环境变量：`BAYES_POKER_LOG_LEVEL`
  - 支持：`DEBUG/INFO/WARNING/ERROR/CRITICAL` 或数字 `10/20/30/40/50`
- 模块内使用：
  - `LOGGER = logging.getLogger(__name__)`
  - 使用 `%s` 参数化日志（不要用 f-string 拼日志，避免无谓格式化开销）
- 在 `except` 中需要堆栈时使用：
  - `LOGGER.exception("...")`
- 对数据/解析失败的落盘：
  - 失败手牌会保存到 `logs/hand_history_failures/` 并写入 `logs/hand_history_failures.log`

## 文件与数据（I/O 约定）
- 统一使用 `pathlib.Path`。
- 读文本：显式 `encoding="utf-8"`，并统一换行（参考 `.replace("\r\n", "\n")`）。
- 写文件前确保目录存在：`path.parent.mkdir(parents=True, exist_ok=True)`。

## 测试风格（pytest）
- 使用 `pytest` 的 fixture/parametrize（见 `tests/test_parse_failed_hands.py`）。
- 对日志行为的断言可使用 `caplog`。
- “大样本/依赖外部数据”测试必须默认跳过，并提供环境变量开关（已存在模式可沿用）。

## 开发者工具（编辑器配置）
- VSCode：`.vscode/settings.json` 已配置 `python.analysis.extraPaths = ["./src"]` 与 pytest。

## Cursor / Copilot 规则
- 未发现 Cursor 规则：`.cursorrules` 或 `.cursor/rules/**`。
- 未发现 Copilot 规则：`.github/copilot-instructions.md`。

## 变更原则（KISS/YAGNI）
- 改动保持最小化、聚焦问题本身；避免“顺手重构”。
- 不要在同一个 PR 里混合：功能变更 + 全项目格式化/风格迁移。
- 若需要新增工具/依赖，优先复用现有依赖，并先解释引入价值与维护成本。
