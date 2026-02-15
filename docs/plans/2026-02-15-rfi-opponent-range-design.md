# RFI 对手范围重建设计

## 背景

当前 `OpponentRangePredictor` 的 `RFI_NO_LIMPER` 与 `RFI_HAVE_LIMPER` 分支仅走统一缩放, 未使用 prefix 维度的玩家统计与策略节点 EV 信息, 无法体现不同 open 频率下的范围差异。

## 目标

在首次翻前加注场景下:
1. 先根据当前动作 prefix 解析 `PreFlopParams`, 获取该 prefix 的 `bet_raise_probability` 作为 RFI 频率。
2. 再根据当前决策节点(玩家行动前的 prefix)查询 preflop strategy。
3. 基于该节点加注动作的 EV 排序, 生成按 RFI 频率裁剪的 169 维范围。

## 方案对比

### 方案 A: 继续复用通用 `_build_preflop_range_from_prefix`
- 优点: 改动小。
- 缺点: 当前通用函数只处理 limp 场景, 且 prefix 语义不适配 RFI 决策前节点。

### 方案 B: 新增 RFI 专用构建函数（推荐）
- 优点: 语义清晰, 能同时满足「当前 prefix 取统计」和「决策节点取 EV」。
- 缺点: 需要新增几个私有辅助函数。

### 方案 C: 仅在现有 `_apply_preflop_action_scale` 上叠加系数
- 优点: 实现最快。
- 缺点: 无法体现 EV 排序与 top-range 裁剪, 不满足需求。

## 推荐设计

采用方案 B:
1. `RFI` 分支传入两个 prefix:
   - `decision_prefix`: 玩家当前动作之前的翻前前缀(用于策略节点查询)。
   - `current_prefix`: 包含当前动作的翻前前缀(用于 params 构建和统计查询)。
2. `stats_repo` 查询策略:
   - 优先玩家自身 `player_id`。
   - 无命中则回退聚合玩家统计。
3. 从 `PreFlopParams` 对应的 `ActionStats` 取 `bet_raise_probability` 作为目标频率。
4. 从策略节点收集 raise/bet/all-in 动作, 以 `total_frequency` 为权重聚合 EV, 得到 169 手牌 EV 排序。
5. 按目标频率(折算到 1326 组合数)从高 EV 到低 EV 填充 `strategy`。
6. 成功构建时直接覆盖 seat 范围; 失败时回退旧逻辑 `_apply_preflop_action_scale`。

## 边界与回退

- 缺 `preflop_strategy` / `stats_repo` / `params` / `策略节点` / `raise 动作` 时, 全部回退旧缩放路径。
- 概率使用 `[0.0, 1.0]` clamp。
- 组合裁剪按 `combos_per_hand` 计算, 支持最后一个手牌分数填充。

## 测试策略

新增 2 个单元测试:
1. `RFI_NO_LIMPER`: 验证使用当前 prefix 的统计频率, 并按 EV 保留高 EV 手牌。
2. `RFI_HAVE_LIMPER`: 验证有 limper 前缀也按对应 params 读取频率并执行 EV 裁剪。

两者均使用 stub repo + 构造策略节点, 避免依赖真实数据库。
