# Strategy 模块

策略引擎核心模块，8000+ 行代码，5 个子模块。

## 结构

```
strategy/
├── __init__.py          # 惰性导出（__getattr__）
├── preflop_parse/       # GTOWizard 风格策略解析
├── preflop_engine/      # 翻前推理内核
├── runtime/             # 策略运行时执行
├── opponent_range/      # 对手范围预测
└── range/               # 范围模型与映射
```

## 子模块

> 每个子模块有独立 AGENTS.md

| 子模块 | AGENTS.md | 核心功能 |
|--------|-----------|----------|
| preflop_parse | ✅ | 策略 JSON 解析、节点查询 |
| preflop_engine | ✅ | HeroEngine、Calibrator、Mapper |
| runtime | ✅ | 策略运行时（36k 行） |
| opponent_range | ✅ | 对手范围预测（58k 行） |
| range | ✅ | 范围模型与映射 |

## 导出 API（__init__.py）

```python
# runtime
StrategyHandler, PreflopLayer, PreflopRuntimeConfig
create_preflop_strategy, create_preflop_strategy_from_directory
create_postflop_strategy, infer_preflop_layer
load_preflop_strategy_from_directory

# preflop_parse
STRATEGY_VECTOR_LENGTH, PreflopStrategy
StrategyAction, StrategyNode
normalize_token, parse_all_strategies
parse_bet_size_from_code, parse_file_meta
parse_strategy_directory, parse_strategy_file
parse_strategy_node, split_history_tokens

# opponent_range
OpponentRangePredictor, create_opponent_range_predictor
```

## 约定

- 策略文件: JSON 格式（GTOWizard 风格）
- 范围: `list[float]` 向量，长度 `STRATEGY_VECTOR_LENGTH`
- bet size 编码: `parse_bet_size_from_code()`
- 测试数据: `tests/fixtures/Cash6m50zGeneral/`

## 测试

- `test_preflop_*.py` - 翻前解析/引擎测试
- `test_opponent_range*.py` - 对手范围测试
- `test_preflop_runtime*.py` - 运行时测试
- 需 `parse_strategy_directory(Path("tests/fixtures/Cash6m50zGeneral"))`
