---
name: refactor-clean
description: "安全地识别并删除死代码, 每一步都有测试验证。适用于清理未使用的函数、模块、依赖和重复代码。当用户提到'清理代码'、'删除无用代码'、'dead code'、'重构清理'时触发。"
argument-hint: "要清理的目录或模块路径, 例如 src/bayes_poker/strategy/"
agent: agent
---

# Refactor Clean

安全地识别并删除死代码, 每一步都有测试验证。

## Step 1: 检测死代码

根据项目类型运行分析工具:

| 工具 | 检测内容 | 命令 |
|------|----------|------|
| vulture | 未使用的 Python 代码 | `uv run vulture src/ --min-confidence 80` |
| ruff | 未使用的 import、变量 | `uv run ruff check --select F401,F841 src/` |
| pylance | 未引用的符号 | 检查 Pylance 诊断 |
| grep | 导出零引用的符号 | 手动搜索 |

如果 vulture 不可用, 用 Grep 进行手动检测:

```bash
# 找到所有 def/class 定义, 检查是否被引用
grep -rn "def \|class " src/bayes_poker/$ARGS --include="*.py" | while read line; do
    func=$(echo "$line" | grep -oP '(?<=def |class )\w+')
    count=$(grep -rn "$func" src/ --include="*.py" | wc -l)
    if [ "$count" -le 1 ]; then
        echo "UNUSED: $line"
    fi
done
```

## Step 2: 按安全等级分类

将发现的死代码按风险分级:

| 等级 | 示例 | 处理方式 |
|------|------|----------|
| **SAFE** | 未使用的内部工具函数、测试辅助函数、私有方法 (`_` 前缀) | 果断删除 |
| **CAUTION** | 公开 API 函数、被 `__init__.py` 导出的符号、WebSocket handler | 验证无动态导入或外部调用方 |
| **DANGER** | 配置文件、入口点 (`main.py`)、类型定义、Rust FFI 接口 (`rust_api.py`) | 深入调查后再决定 |

## Step 3: 安全删除循环

对每个 **SAFE** 项目:

1. **运行完整测试** — 建立基线 (全部通过)
   ```bash
   uv run pytest -q
   ```
2. **删除死代码** — 使用编辑工具精确删除
3. **重新运行测试** — 验证未破坏任何功能
   ```bash
   uv run pytest -q
   ```
4. **测试失败** — 立即回退 `git checkout -- <file>`, 跳过此项
5. **测试通过** — 进入下一项

> **关键**: 每次只删除一处, 原子操作便于回滚。

## Step 4: 处理 CAUTION 项目

删除 CAUTION 项目前必须检查:

- 搜索动态导入: `__import__`, `importlib.import_module`, `getattr`
- 搜索字符串引用: 路由名、handler 名、配置中的模块路径
- 检查是否在 `__init__.py` 或 `__all__` 中导出
- 检查 Rust 扩展 (`poker_stats_rs`) 是否通过 FFI 调用
- 检查 WebSocket 协议消息类型是否依赖该代码
- 验证无外部调用方 (如 scripts/ 目录下的脚本)

## Step 5: 合并重复代码

删除死代码后, 检查:

- 近似重复函数 (>80% 相似) — 合并为一个
- 冗余类型定义 — 整合
- 无附加价值的包装函数 — 内联
- 无意义的 re-export — 移除间接层
- 重复的常量定义 — 集中到 `config/` 或 `domain/`

## Step 6: 输出报告

```
Dead Code 清理报告
──────────────────────────────
删除:   X 个未使用的函数
        X 个未使用的文件
        X 个未使用的依赖
跳过:   X 项 (测试失败)
节省:   ~N 行代码
──────────────────────────────
测试全部通过 ✅
```

## 规则

- **删除前必须先跑测试** — 建立通过基线
- **一次只删一处** — 原子操作, 便于回滚
- **不确定就跳过** — 保留死代码好过破坏生产环境
- **清理和重构分开** — 先清理, 后重构, 不要混在一起
- **不要在清理时顺手改格式** — 单一职责, 变更最小化
- **Rust 扩展相关代码格外小心** — `poker_stats_rs` 的 Python 绑定可能有隐式依赖
