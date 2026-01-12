# Capability: player-metrics

玩家行为指标构建模块，从 PHHS 手牌数据中提取玩家动作并构建统计指标。

## ADDED Requirements

### Requirement: 动作统计数据模型

系统 SHALL 提供 `ActionStats` 数据结构，用于记录特定情境下玩家的动作分布。

#### Scenario: 记录动作样本

- **GIVEN** 一个空的 `ActionStats` 实例
- **WHEN** 调用 `add_sample(ActionType.RAISE)`
- **THEN** `bet_raise_samples` 增加 1

#### Scenario: 计算动作概率

- **GIVEN** 一个 `ActionStats` 实例，包含 10 次 fold、5 次 call、5 次 raise
- **WHEN** 调用 `fold_probability()`
- **THEN** 返回 0.5

---

### Requirement: 玩家统计容器

系统 SHALL 提供 `PlayerStats` 数据结构，用于存储单个玩家的完整统计信息。

#### Scenario: 初始化玩家统计

- **GIVEN** 玩家名 "Hero" 和桌型 `TableType.SIX_MAX`
- **WHEN** 创建 `PlayerStats` 实例
- **THEN** 应包含：
  - VPIP 统计（`StatValue`）
  - 翻前统计数组（`list[ActionStats]`），长度等于 `PreFlopParams.get_all_params()` 数量
  - 翻后统计数组（`list[ActionStats]`），长度等于 `PostFlopParams.get_all_params()` 数量

#### Scenario: 增量更新统计

- **GIVEN** 一个已初始化的 `PlayerStats` 实例
- **WHEN** 调用 `increment(hand_history)` 传入包含该玩家的手牌
- **THEN** 对应情境的 `ActionStats` 样本计数应增加

---

### Requirement: 翻前情境参数

系统 SHALL 提供 `PreFlopParams` 数据结构，定义翻前阶段的情境维度。

#### Scenario: 情境维度定义

- **GIVEN** 需要描述翻前情境
- **WHEN** 创建 `PreFlopParams` 实例
- **THEN** 应包含以下维度：
  - `table_type`: 桌型（6-max）
  - `position`: 玩家位置（SB/BB/UTG/HJ/CO/BTN）
  - `num_callers`: 跟注人数
  - `num_raises`: 加注次数
  - `num_active_players`: 活跃玩家数
  - `previous_action`: 该玩家上一个动作类型
  - `in_position_on_flop`: 是否在 flop 时处于有利位置

#### Scenario: 索引计算

- **GIVEN** 一个 `PreFlopParams` 实例
- **WHEN** 调用 `to_index()`
- **THEN** 返回唯一的整数索引，用于定位 `PreFlopStats` 数组

#### Scenario: 枚举所有情境

- **WHEN** 调用 `PreFlopParams.get_all_params(TableType.SIX_MAX)`
- **THEN** 返回所有有效情境组合的列表

---

### Requirement: 翻后情境参数

系统 SHALL 提供 `PostFlopParams` 数据结构，定义翻后阶段的情境维度。

#### Scenario: 情境维度定义

- **GIVEN** 需要描述翻后情境
- **WHEN** 创建 `PostFlopParams` 实例
- **THEN** 应包含以下维度：
  - `table_type`: 桌型
  - `street`: 当前街（Flop/Turn/River）
  - `round`: 该街的第几轮行动
  - `prev_action`: 该玩家上一个动作类型
  - `num_bets`: 当前下注次数
  - `in_position`: 是否处于有利位置
  - `num_players`: 剩余玩家数

#### Scenario: 索引计算

- **GIVEN** 一个 `PostFlopParams` 实例
- **WHEN** 调用 `to_index()`
- **THEN** 返回唯一的整数索引，用于定位 `PostFlopStats` 数组

---

### Requirement: 从 PHHS 提取动作

系统 SHALL 提供函数从 `pokerkit.HandHistory` 对象中提取动作序列。

#### Scenario: 提取完整动作流

- **GIVEN** 一个包含完整手牌的 `HandHistory` 对象
- **WHEN** 调用 `extract_actions(hand_history)`
- **THEN** 返回 `(street, player_name, action_type, amount)` 元组的迭代器

#### Scenario: 识别动作类型

- **GIVEN** 一个 `HandHistory` 中的加注动作
- **WHEN** 提取该动作
- **THEN** `action_type` 应为 `ActionType.RAISE` 或 `ActionType.BET`

---

### Requirement: 批量构建玩家统计

系统 SHALL 提供函数从手牌列表批量构建所有玩家的统计数据。

#### Scenario: 批量处理

- **GIVEN** 包含 100 手牌的 `list[HandHistory]`
- **WHEN** 调用 `build_player_stats_from_hands(hands, TableType.SIX_MAX)`
- **THEN** 返回 `dict[str, PlayerStats]`，键为玩家名

#### Scenario: 同一玩家多手牌聚合

- **GIVEN** 玩家 "Hero" 在 10 手牌中出现
- **WHEN** 批量构建统计
- **THEN** "Hero" 的 `PlayerStats` 应包含所有 10 手牌的累计数据

---

### Requirement: 顶层指标计算

系统 SHALL 提供以下顶层指标的计算方法。

#### Scenario: 计算 VPIP

- **GIVEN** 一个 `PlayerStats` 实例
- **WHEN** 访问 `vpip` 属性
- **THEN** 返回 `StatValue`，表示自愿入池率（positive=主动入池次数, total=总手牌数）

#### Scenario: 计算 PFR

- **GIVEN** 一个 `PlayerStats` 实例
- **WHEN** 调用 `calculate_pfr()`
- **THEN** 返回 `(positive, total)` 元组
- **AND** positive 为"作为第一个加注者"的次数
- **AND** total 为"有机会第一个加注"的次数

#### Scenario: 计算 Aggression

- **GIVEN** 一个 `PlayerStats` 实例
- **WHEN** 调用 `calculate_aggression()`
- **THEN** 返回 `(positive, total)` 元组
- **AND** positive 为 bet + raise 次数
- **AND** total 为 bet + raise + call 次数（不含 fold）

#### Scenario: 计算 WTP

- **GIVEN** 一个 `PlayerStats` 实例
- **WHEN** 调用 `calculate_wtp()`
- **THEN** 返回 `(positive, total)` 元组
- **AND** positive 为"面对下注时不弃牌"的次数
- **AND** total 为"面对下注"的次数

---

### Requirement: 位置计算

系统 SHALL 提供函数根据玩家索引和总人数计算标准位置。

#### Scenario: 6-max 位置映射

- **GIVEN** 6 人桌，玩家列表按座位顺序（SB 在索引 0）
- **WHEN** 调用 `get_player_position(index, num_players=6)`
- **THEN** 返回对应的 `Position` 枚举值：
  - index 0 → `Position.SMALL_BLIND`
  - index 1 → `Position.BIG_BLIND`
  - index 2 → `Position.UTG`
  - index 3 → `Position.HJ`
  - index 4 → `Position.CO`
  - index 5 → `Position.BUTTON`
