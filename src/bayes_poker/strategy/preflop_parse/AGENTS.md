# Preflop Parse 子模块

策略文件解析，GTOWizard 风格 JSON。

## 文件

| 文件 | 行数 | 功能 |
|------|------|------|
| parser.py | 599 | 核心解析器 |
| query.py | 289 | 节点查询 |
| models.py | 178 | 数据模型 |
| importer.py | 101 | 导入器 |
| records.py | 73 | 记录处理 |
| loader.py | 46 | 文件加载 |
| serialization.py | 91 | 序列化 |

## 核心类型

- `PreflopStrategy`: 策略对象
- `StrategyNode`: 策略树节点
- `StrategyAction`: 动作枚举

## 导出

```python
STRATEGY_VECTOR_LENGTH, PreflopStrategy, StrategyAction, StrategyNode
normalize_token, parse_all_strategies, parse_bet_size_from_code
parse_file_meta, parse_strategy_directory, parse_strategy_file
parse_strategy_node, split_history_tokens
```
