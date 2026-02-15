# 🎯 Agent 并行工作规范

> **核心原则**: 最大化并行, 最小化阻塞。将任务拆解为可独立执行且互不冲突的子任务, 并行调度后统一汇总。

## 📋 执行流程

### 1. 任务分析
- 识别任务依赖关系图。
- 区分可并行节点与必须串行节点。
- 评估子任务耗时与资源占用。

### 2. 并行调度
- 将无前置依赖的子任务打包并行下发。
- 确保子任务间不存在写冲突。
- 为每个子任务定义清晰输入边界与输出格式。

### 3. 结果汇总
- 等待本轮全部子任务完成。
- 校验输出一致性并处理冲突。
- 整合阶段性结果, 作为下一轮输入。

### 4. 递归迭代
- 基于阶段性结果继续拆分与并行。
- 直至所有子任务完成。

## ⚠️ 串行任务处理

对于强依赖链任务（A→B→C）, 按顺序执行, 不强行并行化。

## 💡 最佳实践

- 多文件独立处理: 优先并行。
- 同一文件多处修改: 先拆分不重叠区域, 否则串行。
- 有明确前后依赖: 串行。
- 信息收集 + 分析: 收集阶段并行, 分析阶段汇总后执行。

## 📋 核心不可变原则

### 🌏 语言规范（不可违反）

- 所有思考、分析、解释和回答必须使用简体中文。

### 🎯 基本原则

1. 质量第一: 代码质量和系统安全不可妥协。
2. 思考先行: 编码前必须先分析和规划。
3. Skills 优先: 优先使用 Skill 处理匹配任务。
4. 透明记录: 关键决策和变更必须可追溯。

## 📊 质量标准

### 🏗️ 工程原则

- 遵循 SOLID、DRY、关注点分离、YAGNI。
- 命名清晰、抽象合理。
- 关键流程和复杂逻辑补充简体中文注释。
- 删除无用代码, 修改功能时不保留旧兼容分支。

### ⚡ 性能标准

- 关注时间复杂度和空间复杂度。
- 优化内存使用与 IO。
- 明确处理异常场景与边界条件。

### 🧪 测试要求

- 采用可测试设计与单元测试覆盖。
- 执行单元测试时设置超时（上限 60s）, 避免任务卡死。
- 变更后执行必要的静态检查、格式化与回归验证。

## ⚠️ 危险操作确认机制

### 🚨 高风险操作清单

执行以下操作前必须获得明确确认:

- 文件系统: 删除文件/目录, 批量修改, 移动系统文件。
- 系统配置: 修改环境变量、系统设置、权限。
- 数据操作: 数据删除、结构变更、批量更新。
- 网络请求: 发送敏感数据, 调用生产环境 API。
- 包管理: 全局安装/卸载, 更新核心依赖。

### 📝 确认模板

```text
⚠️ 危险操作检测！

操作类型: [具体操作]
影响范围: [详细说明]
风险评估: [潜在后果]

请确认是否继续？[是/确认/继续]
```

## 🎨 终端输出风格指南

> 核心原则: 使用强视觉边界组织内容, 保持终端可读性。

### 语言与语气

- 友好自然, 句子简洁。
- 直击重点, 复杂问题先给一句话结论。

### 内容组织

- 使用 `**粗体标题**` 作为分组锚点。
- 长段落拆成短句或条目。
- 多步骤任务使用有序列表（1. 2. 3.）。

### 视觉与排版

- 控制单行长度（建议不超过 80 字符）。
- 合理留白, 避免信息拥挤。
- 使用 `**粗体**` 或 `*斜体*` 强调关键点。

### 技术内容规范

- 多行代码或日志必须使用带语言标识的代码块。
- 示例聚焦核心逻辑, 省略无关内容。
- 需要对比修改时使用 `+` / `-` 标记差异。

---

## 📋 项目硬约束

1. 用中文回答输出。
2. `pokerkit` 文档: https://pokerkit.readthedocs.io/
3. 每个类、方法、函数都要添加 Google 风格中文注释, 标点用英文符号。
4. implement 和 task 统一用中文输出。
5. Python 代码必须带类型标注（Typing）。
6. 新增功能必须补测试覆盖。

# Agent Guide（供自动化编码代理使用）

> 约定: 本仓库内统一使用简体中文沟通/输出（含 PR、commit message 建议、注释、日志文案）。

## 项目概览

- 语言/版本: Python `>=3.12`（见 `pyproject.toml`）。
- 包管理/运行: 使用 `uv`。
- 代码布局: `src/` 为可导入包, `tests/` 为测试, `scripts/` 为脚本。
- 主要依赖: `pokerkit`（文档: https://pokerkit.readthedocs.io/）。
- 可选依赖: `websockets`、`cnocr`、`opencv-python`、`pywin32`。

## 模块结构

```text
src/bayes_poker/
├── hand_history/            # 手牌历史解析（离线）
├── table/                   # 实时牌桌解析
│   ├── layout/              # 布局与动态缩放
│   ├── detector.py          # 阶段/动作检测
│   ├── manager.py           # 多牌桌管理器
│   ├── observed_state.py    # 观察状态模型
│   └── parser.py            # TableParser 多进程解析器
├── screen/                  # 截屏与牌桌区域识别
├── ocr/                     # OCR 引擎封装
├── comm/                    # WebSocket 通信
│   ├── client.py            # 客户端
│   ├── server.py            # 服务器
│   ├── session.py           # 会话管理与重放
│   └── agent.py             # TableParser 集成代理
├── strategy/                # 策略引擎（翻前解析/运行时/对手范围）
├── player_metrics/          # 玩家统计（Rust 加速接口）
├── storage/                 # SQLite 仓储
├── domain/                  # 领域模型
├── config/                  # 配置
└── main.py                  # 批量统计入口
```

## 快速开始（环境）

- 创建并同步虚拟环境: `uv sync`
- 在 uv 环境中运行命令: `uv run <command ...>`
- 新增依赖（运行时）: `uv add <package>`
- 新增依赖（开发）: `uv add --dev <package>`
- 修改依赖后更新锁文件: `uv sync`

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

### 对手范围测试初始化约定

- `tests/test_opponent_range.py` 中 `create_opponent_range_predictor(...)` 必须显式传入 `preflop_strategy` 与 `stats_repo`。
- `preflop_strategy` 使用:
  - `parse_strategy_directory(Path("/home/autumn/project/gg_handhistory/preflop_strategy/Cash6m50zSimple25Open_SimpleIP"))`
- `stats_repo` 使用:
  - `PlayerStatsRepository(Path("data/database/player_stats.db"))`
- 测试中正确执行 `connect()` 与 `close()`。

## 开发者工具（编辑器配置）

- VSCode: `.vscode/settings.json` 已配置 `python.analysis.extraPaths = ["./src"]` 与 pytest。

## Cursor / Copilot 规则

- 未发现 Cursor 规则: `.cursorrules` 或 `.cursor/rules/**`。
- 未发现 Copilot 规则: `.github/copilot-instructions.md`。

## 变更原则（KISS/YAGNI）

- 改动最小化, 聚焦问题本身。
- 不在同一 PR 混合功能变更和全项目风格迁移。
- 新增工具或依赖时, 先说明收益与维护成本。
