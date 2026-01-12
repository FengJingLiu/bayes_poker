# Change: Preflop 指标统计系统

## Why

当前项目已完成手牌历史解析（PHHS格式），但缺乏玩家行为分析能力。我们需要：
1. 从历史手牌中提取精细化的 preflop 指标（RFI、3Bet、4Bet 等）
2. 实时游戏时快速匹配当前状态对应的指标
3. 支持玩家分类和贝叶斯更新

## What Changes

### 新增核心模块
- `src/bayes_poker/analysis/preflop_stats.py`：指标数据结构与统计类
- `src/bayes_poker/analysis/preflop_extractor.py`：从手牌历史提取指标
- `src/bayes_poker/analysis/player_stats.py`：玩家统计聚合

### 数据结构设计
- `StatCounter`：分子/分母统计器（类似 G5.Logic/StatValue）
- `PreflopIndicator`：单个指标的完整定义（条件 + 统计）
- `PreflopStats`：玩家 preflop 指标集合
- `PreflopContext`：preflop 行动状态上下文

### 支持的指标类型
| 指标类别 | 维度 | 说明 |
|---------|------|------|
| RFI | 位置 (6) | Raise First In |
| Open vs Limp | 位置 × limp数 (6×2) | 面对1个/2+个limp后open |
| First Limp | 位置 (6) | 第一个limp |
| Limp vs Limp | 位置 × limp数 (6×2) | 面对limp后再limp |
| 3Bet | 位置×位置 (6×6) + limp后3B (6) | 对各位置的3bet |
| Cold 4Bet | 位置×IP (6×2) | 未行动过的4bet |
| Non-cold 4Bet | 位置×IP (6×2) | open后被3bet再4bet |

### 聚合指标
- VPIP、PFR、ATS、WTP 等可由细分指标计算得出
- 支持按玩家类型聚合求和
- 预留协方差矩阵接口供贝叶斯更新

## Impact

- 受影响 specs：新增 `preflop-stats` 能力
- 受影响代码：
  - `src/bayes_poker/analysis/` 目录（新增）
  - `src/bayes_poker/storage/actions.py`（可能需要扩展 ActionType）
  - `src/bayes_poker/storage/position.py`（可能需要位置枚举）
- 依赖：无新外部依赖，复用现有 dataclasses 和 pokerkit

## Open Questions

1. **位置定义**：是否需要支持 9-max 或其他桌型？当前设计以 6-max 为主。
2. **持久化**：指标是否需要存入 SQLite？本阶段先内存计算，后续可扩展。
3. **协方差矩阵**：具体实现留待后续 proposal，本阶段仅预留接口。
