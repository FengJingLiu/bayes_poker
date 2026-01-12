# Design: 玩家指标构建模块

## Context

G5.Logic 是一个成熟的 C# 扑克机器人核心库，其玩家指标系统通过多维情境参数（位置、加注次数、跟注人数等）构建精细化的行为统计。本次移植目标是将其核心逻辑转换为 Python，同时适配 `pokerkit` 生态。

### 约束
- 必须基于 PHHS 格式数据（`pokerkit.HandHistory`）
- 不使用 `src/bayes_poker/storage/` 模块
- 遵循项目现有代码风格（中文注释、类型注解、dataclasses）

## Goals / Non-Goals

### Goals
- 完整移植 G5.Logic 的玩家统计数据模型
- 支持从 PHHS 手牌数据增量构建统计
- 计算 VPIP、PFR、Aggression、WTP 四大核心指标
- 支持按情境维度查询动作分布

### Non-Goals
- **不移植** 贝叶斯估计（`OpponentModeling.cs`）——后续独立变更
- **不移植** 决策引擎（`BotGameState.cs`、`DecisionMakingDll.cs`）
- **不移植** 牌力评估（`HandStrength.cs`、`PreFlopEquity.cs`）
- **不支持** HeadsUp 桌型（初期仅 6-max）
- **不持久化** 统计数据到数据库

## Decisions

### 1. 数据模型映射

| G5.Logic (C#) | bayes_poker (Python) | 说明 |
|---------------|----------------------|------|
| `StatValue` | `StatValue` (dataclass) | positive/total 计数器 |
| `ActionStats` | `ActionStats` (dataclass) | bet_raise/check_call/fold 样本 |
| `PlayerStats` | `PlayerStats` (dataclass) | VPIP + PreFlop/PostFlop 数组 |
| `PreFlopParams` | `PreFlopParams` (dataclass) | 翻前情境维度 |
| `PostFlopParams` | `PostFlopParams` (dataclass) | 翻后情境维度 |

### 2. 情境参数索引化

G5.Logic 使用 `ToIndex()` 方法将多维参数映射到一维数组索引。Python 实现将：
- 保留相同的索引计算逻辑
- 使用 `@functools.cached_property` 缓存 `all_params` 列表
- 提供 `from_index()` 反向查找方法

### 3. 手牌重放与动作提取

从 `pokerkit.HandHistory` 提取动作流：

```python
def extract_actions(hh: HandHistory) -> Iterator[tuple[Street, str, ActionType, int]]:
    """从 HandHistory 提取动作序列。
    
    Yields:
        (街, 玩家名, 动作类型, 金额)
    """
    for state in hh:
        # 遍历状态变化，识别动作类型
        ...
```

### 4. 枚举映射

| G5.Logic | pokerkit 对应 | Python 实现 |
|----------|---------------|-------------|
| `Street.PreFlop` | 未发公共牌 | `Street.PREFLOP` |
| `Street.Flop` | 3 张公共牌 | `Street.FLOP` |
| `Position.Button` | 相对位置计算 | `Position.BUTTON` |
| `ActionType.Raise` | `state.actor_index` 变化 | `ActionType.RAISE` |

### 5. 位置计算

G5.Logic 使用玩家列表索引确定位置（SB=0, BB=1, ...）。Python 实现：

```python
def get_position(player_index: int, num_players: int) -> Position:
    """根据玩家索引和人数计算位置。"""
    if player_index == 0:
        return Position.SMALL_BLIND
    elif player_index == 1:
        return Position.BIG_BLIND
    elif player_index == num_players - 1:
        return Position.BUTTON
    # ...
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| pokerkit API 变更 | 锁定 pokerkit 版本，添加适配层 |
| 索引计算逻辑复杂 | 添加详尽的单元测试覆盖边界情况 |
| 初期仅支持 6-max | 设计时预留 TableType 扩展点 |

## Migration Plan

1. 新增模块，不修改现有代码
2. 添加测试用例验证与 G5.Logic 行为一致性
3. 后续变更可添加贝叶斯估计和持久化

## Open Questions

1. **是否需要支持 Omaha？** —— 初期仅 Hold'em，后续可扩展
2. **金额单位是否统一为分（cents）？** —— 是，与项目现有约定一致
3. **是否需要多进程并行构建？** —— 初期单线程，后续按需优化
