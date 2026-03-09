# Opponent Range 子模块

对手范围预测。

## 文件

| 文件 | 行数 | 功能 |
|------|------|------|
| predictor.py | 1,749 | 预测器核心 |
| preflop_context.py | 228 | 翻前上下文 |
| frequency_fill.py | 215 | 频率填充 |
| stats_source.py | 47 | 统计源 |

## 核心类

- `OpponentRangePredictor`: 对手范围预测器

## 导出

```python
OpponentRangePredictor, create_opponent_range_predictor
```

## 测试

- `test_opponent_range*.py`
- 需 `parse_strategy_directory()` + `PlayerStatsRepository`
