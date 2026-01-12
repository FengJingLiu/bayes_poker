# Project Context

## Purpose
bayes-poker 是一个 GGPoker Rush & Cash 手牌历史解析器，将 GGPoker 导出的手牌历史文件转换为 [pokerkit](https://pokerkit.readthedocs.io/) PHHS 格式。

长期目标包括：
- 手牌数据持久化存储（SQLite）
- 扑克分析引擎
- 策略引擎
- OCR 识别
- 自动化执行

## Tech Stack
- **语言**：Python >= 3.12
- **包管理**：uv
- **核心依赖**：pokerkit（扑克工具库）
- **测试框架**：pytest
- **数据存储**：SQLite

## Project Conventions

### Code Style
- **语言**：代码注释、文档、commit message 一律使用简体中文
- **缩进**：4 空格
- **类型注解**：使用 Python 3.12 风格（`int | None`、`list[T]`、`dict[K, V]`）
- **Imports**：
  - 分组顺序：标准库 → 第三方 → 本地包
  - 使用 `from __future__ import annotations`
  - ABC 使用 `from collections.abc import Sequence`
- **命名**：
  - 常量：`UPPER_SNAKE_CASE`（如 `FAILED_HANDS_LOG_PATH`）
  - 正则：`*_PATTERN` 或语义化全大写
  - 私有函数：`_foo`
  - 类：`CapWords`；函数/变量：`snake_case`
- **日志**：
  - 模块级 `LOGGER = logging.getLogger(__name__)`
  - 使用 `%s` 参数化（不用 f-string）
  - 日志级别通过 `BAYES_POKER_LOG_LEVEL` 环境变量控制

### Architecture Patterns
- **目录结构**：`src/` 下为可导入包；`tests/` 为测试；`scripts/` 为脚本
- **数据模型**：使用 `dataclasses`
- **文件操作**：统一使用 `pathlib.Path`，显式 `encoding="utf-8"`
- **错误处理**：
  - 捕获具体异常，避免裸 `except:`
  - 使用异常链 `raise ... from exc`
  - 解析失败：可恢复的记录 warning 返回 `None`；不可恢复的集中捕获并记录失败样本

### Testing Strategy
- 使用 pytest fixture/parametrize
- **大样本测试**：默认跳过，需设置环境变量 `BAYES_POKER_RUN_LARGE_HANDHISTORY_TESTS=1`
- 可通过 `GG_HANDHISTORY_DIR` 指定本地手牌数据目录
- 常用参数：`-x`（失败即停）、`-s`（打印 stdout）、`-vv`（详细输出）

### Git Workflow
- **Commit 风格**：Conventional Commits（中文描述）
  - 格式：`<type>(<scope>): <description>`
  - 类型：`feat`、`fix`、`docs`、`chore`、`test`、`refactor`
  - 示例：`feat(parser): 支持 Cash Drop 金额提取`
- **分支**：主分支为 `main`

## Domain Context
- **GGPoker 特有格式**：
  - EV Cashout：提前兑现 EV 值
  - Run It Twice/Three：多次发牌，需合并为单一结果
  - Cash Drop：彩池投注，需提取金额
  - Uncalled Bet Returned：未被跟注的加注返还
- **PHHS**：Poker Hand History Standard，pokerkit 定义的手牌历史标准格式
- **金额单位**：内部使用分（cents）避免浮点精度问题

## Important Constraints
- 不要在"修 bug/加小功能"时顺手引入全项目格式化或大范围 lint 修复
- 改动保持最小化、聚焦问题本身
- 不要混合：功能变更 + 全项目风格迁移
- 避免滥用 `Any`；禁止使用 `as any`、`@ts-ignore` 等类型逃逸

## External Dependencies
- **pokerkit**：扑克工具库，提供底层解析能力
  - 文档：https://pokerkit.readthedocs.io/
  - 核心类：`HandHistory`、`PokerStarsParser`
