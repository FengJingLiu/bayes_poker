# Coding Style Guide

> 此文件定义团队编码规范，所有 LLM 工具在修改代码时必须遵守。
> 提交到 Git，团队共享。

## General
- Prefer small, reviewable changes; avoid unrelated refactors.
- Keep functions short (<50 lines); avoid deep nesting (≤3 levels).
- Name things explicitly; no single-letter variables except loop counters.
- Handle errors explicitly; never swallow errors silently.

## Language-Specific

### Python
- Python 3.12+，类型注解必须完整（`from __future__ import annotations` 可选）。
- 优先使用 dataclass / dataclass_with_slots；不可变数据用 `frozen=True`。
- 禁止原地修改传入参数，始终返回新对象（参见 coding-style.md 不可变性原则）。
- 异步场景使用 `asyncio`；禁止 `threading` 混用。

### Rust
- 遵循 clippy 无 warning 标准（`cargo clippy -- -D warnings`）。
- 公开 API 必须有文档注释（`///`）。
- 错误处理用 `thiserror`；跨边界用 `anyhow`。
- 禁止 `unwrap()`（测试除外），使用 `?` 或显式 `expect("<reason>")`。

## Git Commits
- Conventional Commits，祈使句语气。
- Atomic commits：每次提交只包含一个逻辑变更。

## Testing
- 每个 feat/fix 必须附带对应测试。
- 覆盖率不得下降。
- 修复流程：先写失败测试，再修复代码。
- Python：pytest；Rust：cargo test。

## Security
- 禁止记录 secrets（token/key/cookie/JWT）到日志。
- 在信任边界处验证所有输入。
- 所有外部数据（API 响应、用户输入、文件内容）不可信任。
