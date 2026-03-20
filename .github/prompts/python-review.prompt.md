---
name: python-review
description: "全面的 Python 代码审查: PEP 8 合规、类型标注、安全扫描、Pythonic 惯用法。调用 python-reviewer agent 对变更文件进行静态分析与人工审查。当用户提到'review Python'、'代码审查'、'检查代码质量'时触发。"
argument-hint: "要审查的文件或目录路径, 例如 src/bayes_poker/strategy/; 留空则自动检测 git diff 中的 .py 文件"
agent: python-reviewer
---

# Python Code Review

对 Python 代码执行全面审查, 涵盖静态分析、安全扫描、类型检查和 Pythonic 惯用法。

## Step 1: 识别变更文件

确定审查范围:

```bash
# 优先使用 git diff 检测变更的 .py 文件
git diff --name-only --diff-filter=ACMR HEAD~1 -- '*.py'

# 如果指定了 $ARGS, 直接审查该路径下的 .py 文件
find $ARGS -name "*.py" -type f
```

如果没有变更文件也没有指定路径, 提示用户指定范围。

## Step 2: 运行静态分析

按顺序执行以下检查, 记录每项结果:

| 工具 | 检查内容 | 命令 |
|------|----------|------|
| ruff check | Lint + 未使用 import/变量 | `uv run ruff check $FILES` |
| ruff format | 格式一致性 | `uv run ruff format --check $FILES` |
| pyright/pylance | 类型检查 | 检查 Pylance 诊断或 `uv run pyright $FILES` |

> 注意: 项目未配置 mypy/black/isort, 使用 ruff 统一处理 lint + format。

## Step 3: 安全扫描

逐文件扫描以下安全风险:

### 必检项目
- **SQL 注入**: 字符串拼接 SQL 查询 (`f"SELECT ... {var}"`)
- **命令注入**: `os.system()`, `subprocess` 拼接用户输入
- **不安全反序列化**: `pickle.loads()`, `yaml.unsafe_load()`
- **硬编码凭据**: API key、密码、token 出现在源码中
- **裸异常捕获**: `except:` 或 `except Exception:` 不带日志
- **eval/exec 使用**: 动态代码执行

### 项目特定检查
- **Rust FFI 边界**: `poker_stats_rs` 调用参数类型是否匹配
- **WebSocket 协议**: `MessageEnvelope` 序列化/反序列化是否安全
- **SQLite 查询**: 是否使用参数化查询 (`?` 占位符)
- **Path 操作**: 是否有路径遍历风险 (`..` 拼接)

## Step 4: 代码质量审查

### CRITICAL (必须修复 — 阻止合并)
- SQL/命令注入漏洞
- 不安全的 eval/exec/pickle 使用
- 硬编码凭据或密钥
- YAML unsafe load
- 裸 `except:` 隐藏错误
- 数据竞争 (无锁的共享可变状态)

### HIGH (应当修复)
- 公开函数缺少类型标注 (Python 3.12 风格)
- 可变默认参数 (`def f(items=[])`)
- 静默吞没异常
- 未使用 context manager 管理资源
- C 风格循环代替列表推导
- `type()` 代替 `isinstance()`
- 缺少 `raise ... from exc` 丢失异常链

### MEDIUM (建议改进)
- PEP 8 格式偏差
- 公开函数缺少 docstring (Google 风格中文注释)
- `print()` 代替 `logging`
- 魔法数字未提取为常量
- 未使用 f-string
- 不必要的 `list()` 包装
- 类/函数超过 800/50 行

### LOW (酌情处理)
- 可简化的条件表达式
- 未使用的局部变量 (ruff F841)
- import 顺序不规范 (标准库 → 第三方 → 本地)

## Step 5: 项目惯例检查

对照项目 AGENTS.md 约定:

- [ ] Google 风格中文注释, 标点用英文符号
- [ ] Python 3.12 类型标注 (不用 `Optional`, 用 `X | None`)
- [ ] `pathlib.Path` 代替字符串路径
- [ ] 文件 I/O 显式 `encoding="utf-8"`
- [ ] 写文件前 `path.parent.mkdir(parents=True, exist_ok=True)`
- [ ] 日志使用 `logging.getLogger(__name__)` + `%s` 参数化
- [ ] 异常使用 `LOGGER.exception(...)` 输出堆栈
- [ ] 捕获具体异常, 避免裸 `except:`
- [ ] 常量全大写下划线, 私有函数 `_` 前缀
- [ ] 不可变优先: `@dataclass(frozen=True)` / `NamedTuple`

## Step 6: 生成报告

输出格式:

```markdown
# Python Code Review Report

## 审查范围
- file1.py (modified)
- file2.py (new)

## 静态分析结果
| 工具 | 状态 | 详情 |
|------|------|------|
| ruff check | ✓/⚠️/✗ | N issues |
| ruff format | ✓/⚠️/✗ | N files |
| pyright | ✓/⚠️/✗ | N errors |

## 发现问题

### [CRITICAL] 问题标题
**文件**: path/to/file.py:L42
**问题**: 描述
**修复**: 建议方案 + 代码示例

### [HIGH] 问题标题
...

## 统计
| 等级 | 数量 |
|------|------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |

## 结论
✅ 批准合并 / ⚠️ 修复 MEDIUM 后可合并 / ❌ 阻止合并 (存在 CRITICAL/HIGH)
```

## 审批标准

| 状态 | 条件 |
|------|------|
| ✅ 批准 | 无 CRITICAL 或 HIGH 问题 |
| ⚠️ 警告 | 仅 MEDIUM 问题 (谨慎合并) |
| ❌ 阻止 | 存在 CRITICAL 或 HIGH 问题 |

## 常见修复模式

### 添加类型标注 (Python 3.12)
```python
# Before
def calculate(x, y):
    return x + y

# After
def calculate(x: int | float, y: int | float) -> int | float:
    return x + y
```

### 修复可变默认参数
```python
# Before
def process(items=[]):
    items.append("new")
    return items

# After
def process(items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append("new")
    return items
```

### 使用 Context Manager
```python
# Before
f = open("config.json")
data = f.read()
f.close()

# After
with open("config.json", encoding="utf-8") as f:
    data = f.read()
```

### 参数化 SQL 查询
```python
# Before
query = f"SELECT * FROM players WHERE name = '{name}'"

# After
query = "SELECT * FROM players WHERE name = ?"
cursor.execute(query, (name,))
```

### 列表推导代替循环
```python
# Before
result = []
for item in items:
    if item.active:
        result.append(item.name)

# After
result = [item.name for item in items if item.active]
```

### 保留异常链
```python
# Before
try:
    parse(data)
except ValueError:
    raise RuntimeError("parse failed")

# After
try:
    parse(data)
except ValueError as exc:
    raise RuntimeError("parse failed") from exc
```
