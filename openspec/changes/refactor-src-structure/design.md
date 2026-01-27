## Context

本变更涉及多模块目录结构调整与重复类型抽取，属于跨模块的代码组织优化，需要明确边界与兼容策略。

## Goals / Non-Goals

- Goals:
  - 减少 `src/bayes_poker` 内的空包与构建产物
  - 统一公共类型与序列化逻辑，降低重复
  - 保持对外导出路径兼容（尽量不破坏现有导入）
- Non-Goals:
  - 不引入新业务功能
  - 不修改现有策略/解析逻辑行为
  - 不做大范围风格化重构

## Decisions

- Decision: 引入 `bayes_poker/domain/poker.py` 作为共享扑克基础类型的归一位置。
  - Why: `ActionType`/`Street` 在多个模块重复，且语义一致；集中后可避免重复维护。

- Decision: `comm/messages.py` 使用统一 payload 基类实现 `to_dict/from_dict`。
  - Why: 避免重复序列化代码，保持 KISS/DRY。

- Decision: `screen/` 内 `WindowInfo` 抽取到独立模块并在原模块中再导出。
  - Why: 保留兼容导入路径，同时消除重复定义。

- Decision: 删除空包与占位文件，开发笔记移出 `src/`。
  - Why: `src/` 仅保留可导入运行代码，减少噪声与发布包体积。

## Risks / Trade-offs

- 风险：外部代码若直接依赖被删除的空包/模块路径，将出现导入失败。
  - Mitigation: 仅删除确认为空且无引用的模块，并在改动前确认。

- 风险：重复类型合并可能造成隐性导入路径变化。
  - Mitigation: 在原模块中保留同名导出，确保 import 兼容。

## Migration Plan

1. 新增共享类型与 payload 基类模块。
2. 逐步替换内部引用并保持旧路径导出兼容。
3. 移除空包与 `src` 内的 notebooks/构建产物。
4. 运行 `compileall` / `pytest` 验证。

## Open Questions

- notebooks/analysis 是否统一迁移到 `notebooks/` 目录，还是使用 `analysis/` 作为顶层目录？
统一迁移到 `notebooks/` 目录