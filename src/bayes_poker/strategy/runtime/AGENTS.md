# Runtime 子模块

策略运行时执行。

## 文件

| 文件 | 行数 | 功能 |
|------|------|------|
| preflop.py | 1,135 | 翻前运行时核心 |
| base.py | 35 | 基类 |
| postflop.py | 24 | 河牌后逻辑 |
| preflop_history.py | 118 | 历史处理 |

## 核心类

- `StrategyHandler`: 策略执行处理器
- `PreflopLayer`: 翻前策略层
- `PreflopRuntimeConfig`: 运行时配置

## 导出

```python
StrategyHandler, PreflopLayer, PreflopRuntimeConfig
create_preflop_strategy, create_preflop_strategy_from_directory
create_postflop_strategy, infer_preflop_layer
load_preflop_strategy_from_directory
```
