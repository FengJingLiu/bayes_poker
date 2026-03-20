---
name: commit
description: "智能 Git 提交: 分析暂存区改动, 自动生成 Conventional Commits 风格提交信息并执行提交。支持拆分建议、scope/type 指定。当用户说'提交'、'commit'、'git commit'时触发。"
argument-hint: "[--all] [--emoji] [--amend] [--no-verify] [--scope <scope>] [--type <type>] — 留空则自动暂存已追踪文件并生成提交信息"
mode: agent
---

# Commit - 智能 Git 提交

分析当前改动, 生成 Conventional Commits 风格提交信息并执行提交。

## 选项

| 选项 | 说明 |
|------|------|
| `--all` | 暂存所有改动 (`git add -A`) |
| `--amend` | 修补上次提交 |
| `--no-verify` | 跳过 Git 钩子 |
| `--emoji` | 在类型前加 emoji 前缀 |
| `--scope <scope>` | 指定作用域 |
| `--type <type>` | 强制指定提交类型 |

---

## 执行工作流

### 阶段 1: 仓库校验

1. 确认当前目录是 Git 仓库: `git rev-parse --is-inside-work-tree`
2. 检测 rebase/merge/cherry-pick 是否进行中
3. 读取当前分支: `git branch --show-current`

若校验失败, 立即停止并告知用户原因。

### 阶段 2: 改动检测

```bash
# 查看暂存区
git diff --cached --stat
git diff --stat  # 未暂存
```

- 若暂存区为空且传了 `--all` → 执行 `git add -A`
- 若暂存区为空且无 `--all` → 提示用户选择要暂存的文件, 不自动操作
- 列出待提交文件清单供用户确认

### 阶段 3: 拆分建议

分析改动的聚类特征:

- 关注点分离 (业务逻辑 vs 测试 vs 文档)
- 文件路径模式 (不同顶级目录/包)
- 改动类型混合 (新增功能 + 缺陷修复)

**触发建议的条件** (满足任一):
- 改动超过 300 行
- 跨越 3 个及以上顶级目录
- 混合了 feat + fix 两种类型

若触发, 输出建议的拆分方案, 询问用户是否继续合并提交或拆分。用户确认后继续。

### 阶段 4: 生成提交信息

**格式**:
```
[emoji ]<type>(<scope>): <subject>

<body>
```

**规则**:
- 首行 ≤ 72 字符, 祈使语气 (中文: 动词+宾语)
- Body 说明: 动机、实现要点、影响范围 (每项 1 行)
- 语言: 参考最近 5 次提交判断中英文 (`git log --oneline -5`)
- 本项目最近提交为**中文**, 使用中文生成

Type 与 Emoji 映射:

| Emoji | Type | 说明 |
|-------|------|------|
| ✨ | feat | 新增功能 |
| 🐛 | fix | 缺陷修复 |
| 📝 | docs | 文档更新 |
| 🎨 | style | 代码格式 |
| ♻️ | refactor | 重构 |
| ⚡️ | perf | 性能优化 |
| ✅ | test | 测试相关 |
| 🔧 | chore | 构建/工具 |
| 👷 | ci | CI/CD |
| ⏪️ | revert | 回滚 |

**推断 type 的优先级**:
1. `--type` 参数指定 → 直接使用
2. 仅有测试文件变更 → `test`
3. 仅有文档变更 → `docs`
4. 含新增函数/类 → `feat`
5. 含 bug 修复关键词 (fix, patch, hotfix) → `fix`
6. 其他 → `refactor` 或 `chore`

**scope 推断**:
- `--scope` 参数指定 → 直接使用
- 改动集中在单个包 (`strategy_engine`, `storage` 等) → 使用包名
- 跨多包 → 省略 scope

生成后**展示给用户确认**, 等待用户回复 (y/n/修改)。

### 阶段 5: 执行提交

用户确认后执行:

```bash
# 写入提交信息
git commit [--no-verify] [--amend] [--signoff] -m "<message>"
```

输出提交结果 (commit hash + 首行信息)。

---

## 关键规则

1. **仅操作 Git** — 不运行测试、不格式化代码、不安装依赖
2. **尊重钩子** — 默认执行 pre-commit 钩子, `--no-verify` 可跳过
3. **不改源码** — 只读 diff, 只写提交信息
4. **原子提交** — 一次提交只做一件事; 若混合不同关注点, 优先建议拆分
5. **用户确认** — 提交信息生成后必须展示并等待确认, 不自动执行

---

## 示例

```
# 基本提交（自动生成信息）
/commit

# 暂存所有并带 emoji
/commit --all --emoji

# 指定类型和作用域
/commit --scope strategy_engine --type refactor

# 修补上次提交
/commit --amend

# 跳过 pre-commit 钩子
/commit --no-verify
```

---

## 典型输出格式

```
## 待提交文件
- src/bayes_poker/strategy/strategy_engine/hero_resolver.py (modified)
- src/bayes_poker/strategy/preflop_parse/models.py (modified)

## 建议提交信息
refactor(strategy_engine): 修复异常链缺失与 QueryResult 未定义名称

- hero_resolver: except Exception 补 LOGGER.exception() 日志
- context_builder: raise 补 from exc 保留异常链
- preflop_parse/models: 添加 QueryResult TYPE_CHECKING 导入

确认提交? (y/n)
```
