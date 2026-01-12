# Change: 添加玩家指标构建模块

## Why

当前 bayes_poker 项目仅具备手牌解析能力，缺乏对玩家行为的统计分析。需要从 G5.Logic（C#）项目中提取玩家指标构建逻辑，移植为 Python 实现，以支持后续的对手建模和策略引擎。

## What Changes

- **新增** `src/bayes_poker/player_metrics/` 模块
  - 核心数据模型：`ActionStats`、`StatValue`、`PlayerStats`
  - 情境参数：`PreFlopParams`、`PostFlopParams`
  - 批量处理：从 PHHS 数据构建玩家统计
- **新增** 基于 `pokerkit.HandHistory` 的手牌重放与动作提取逻辑
- **新增** 顶层指标计算：VPIP、PFR、Aggression、WTP
- **不使用** `src/bayes_poker/storage/` 模块（用户明确表示可能弃用）

## Impact

- **Affected specs**: 新增 `player-metrics` 能力规格
- **Affected code**:
  - 新增 `src/bayes_poker/player_metrics/__init__.py`
  - 新增 `src/bayes_poker/player_metrics/models.py`（数据模型）
  - 新增 `src/bayes_poker/player_metrics/params.py`（情境参数）
  - 新增 `src/bayes_poker/player_metrics/builder.py`（统计构建器）
  - 新增 `tests/test_player_metrics.py`

## Source Reference

移植自 `/home/autumn/project/g5-poker-bot/src/G5.Logic/`：
- `PlayerStats.cs` → `models.py`
- `ActionStats.cs` → `models.py`
- `StatValue.cs` → `models.py`
- `PreFlopParams.cs` → `params.py`
- `PostFlopParams.cs` → `params.py`
- `MakePlayerStats.cs` → `builder.py`

## Key Design Decisions

1. **数据源**：使用 `pokerkit.HandHistory` 而非自定义 Hand 模型
2. **不依赖 storage**：统计结果暂不持久化，后续可扩展
3. **简化情境维度**：初期仅移植 6-max 桌型的情境参数
4. **Python 风格**：使用 dataclasses、类型注解、生成器模式
