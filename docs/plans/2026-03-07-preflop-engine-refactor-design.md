# Preflop 统一推理内核重构设计

## 背景

当前 preflop 相关能力分散在以下链路中:

- `strategy/preflop_parse/query.py`: 基于 `history` 字符串的多级回退查询。
- `strategy/runtime/preflop.py`: Hero 决策 runtime, 包含少量 open/iso 启发式。
- `strategy/opponent_range/predictor.py`: 对手范围估计, 仅在局部场景使用频率驱动重建。

现状的核心问题不是单个分支不够多, 而是系统主键仍然偏向 `history` 字符串。遇到以下真实牌局时, 现有结构会越来越脆:

- limp、overlimp、多 limp。
- open + cold call。
- 非标准 raise size。
- 玩家动作倾向和 solver 基准明显偏离。

本次重构的目标不是继续补 `if/else`, 而是把项目改造成一套共享的 preflop 推理内核:

> GTOWizard 数据作为先验分布库。真实牌局 = 状态抽象 + 节点映射 + 玩家倾向校准 + 贝叶斯范围更新。

## 目标

第一阶段只覆盖 preflop, 但必须同时打通以下三条主线:

1. 节点映射: 真实动作前缀映射到最近 solver 公共状态。
2. 对手范围: 基于玩家倾向和观测动作做后验范围更新。
3. Hero 决策: 基于共享推理内核和对手后验范围输出 exploit 建议。

同时满足以下业务要求:

- 不再把标准行动线字符串作为核心推理主键。
- 支持动作偏离和尺度偏离。
- 按 action family 建模玩家倾向, 而不是按整局粗略统计。
- open、call、3bet、4bet、limp、iso 使用各自独立的动作排序。
- 决策链路输出结构化解释, 便于调试、回放和后续维护。

## 非目标

第一阶段明确不纳入以下内容:

- postflop 范围更新。
- showdown 反推组合学习。
- 跨街联合求解。
- 自动训练距离权重或 exploit 参数。
- UI 级回放展示。

## 当前落地范围（2026-03-07）

当前代码已经把 preflop 共享内核落地为可测试模块, 但 adapter 接入范围仍按第一阶段最小边界收紧:

- `src/bayes_poker/strategy/preflop_engine/` 已落地 `state`、`mapper`、`solver_prior`、`tendency`、`policy_calibrator`、`range_engine`、`hero_engine`、`explain` 八个模块。
- `state.py` 与 `mapper.py` 当前最小模型主要覆盖 `OPEN`、`CALL_VS_OPEN`、`LIMP` 三类共享状态, 并对 limp、多次加注、open jam 等复杂前缀保持显式拒绝或模板回退。
- `strategy/runtime/preflop.py` 当前仅把共享 adapter 接到 `CALL_VS_OPEN` 主链, 且只在 `table_state` 信息完整时启用; postflop 或缺字段场景继续回退 legacy 逻辑。
- `strategy/opponent_range/predictor.py` 当前仅把共享 adapter 接到两类首次翻前动作:
  - `UTG first-in open`
  - 非盲位在单次 open 面前且无前置 caller 的 `cold call vs open`
- `limp`、`3bet/squeeze/overcall`、`SB/BB defend`、`open jam`、空策略树/无可用 stack 等场景, 当前都显式回退到旧的 prefix 或 scale fallback。
- `hero_engine.py` 与 `range_engine.py` 已可独立通过单测验证, 但对外 adapter 仍按第一阶段最小接入范围启用。
- postflop 更新仍是占位状态, 不属于本轮实现范围。

## 总体方案

采用统一的 preflop 推理内核, 让 Hero 决策与对手范围共享同一组状态抽象、映射器、玩家画像和策略校准器。

```text
真实动作前缀
  -> PreflopDecisionState
  -> NodeMapper
  -> SolverPrior
  -> PlayerTendencyProfile
  -> PolicyCalibrator
  -> 分叉:
     -> RangeEngine 更新对手后验范围
     -> HeroDecisionEngine 输出 Hero 决策与解释
```

系统必须满足一个硬约束:

> Hero 决策不能绕过对手范围系统单独查表。两条链路必须共享同一推理内核, 否则 exploit 会互相冲突。

## 核心对象

### PreflopDecisionState

用于表达某个玩家当前面对的公共决策状态, 是系统真正的核心主键。建议字段包括:

- `table_format`
- `effective_stack_bb`
- `actor_position`
- `players_remaining`
- `pot_bb`
- `to_call_bb`
- `bet_count`
- `call_count`
- `limp_count`
- `aggressor_position`
- `is_ip`
- `action_family`
- `raise_size_bb`
- `raise_size_ratio`
- `prefix_actions`

### ObservedAction

用于保存真实牌局中的单步动作事实, 不夹带策略解释:

- `player_id`
- `position`
- `action_type`
- `amount_bb`

### MappedSolverContext

用于表达状态映射结果, 至少包括:

- `matched_level`
- `matched_history`
- `fallback_reason`
- `distance_score`
- `candidate_nodes`
- `price_adjustment_applied`
- `range_signal_adjustment_applied`

### PlayerTendencyProfile

用于表达玩家在某类节点上的平滑后画像, 包括:

- `open_freq`
- `call_freq`
- `three_bet_freq`
- `four_bet_freq`
- `fold_to_open`
- `fold_to_three_bet`
- `limp_fold`
- `limp_reraise`
- `size_buckets`
- `confidence`
- `sample_size`

### ActionPolicy

用于表达某状态下每手牌对每个动作的条件概率, 本质是:

```text
P(action | hand, state)
```

### RangeBelief

用于表达某玩家在给定观测历史下的当前后验范围, 本质是:

```text
P(hand | observed history)
```

## 模块边界

建议新增共享目录:

```text
src/bayes_poker/strategy/preflop_engine/
├── __init__.py
├── state.py
├── mapper.py
├── solver_prior.py
├── tendency.py
├── policy_calibrator.py
├── range_engine.py
├── hero_engine.py
└── explain.py
```

各模块职责如下:

- `state.py`
  - 从真实动作序列构造 `PreflopDecisionState`。
  - 派生 `action_family`、`is_ip`、`players_remaining` 等字段。

- `mapper.py`
  - 负责 `真实状态 -> 最近 solver 节点`。
  - 处理 limp、open + cold call、非标准 size、多人池 fallback。
  - 不负责 exploit。

- `solver_prior.py`
  - 从本地 GTOWizard 数据读取候选节点。
  - 输出基准 `ActionPolicy`。
  - 支持多节点加权合成。

- `tendency.py`
  - 从玩家统计读取节点族画像。
  - 负责平滑、bucket 化和置信度计算。

- `policy_calibrator.py`
  - 将 solver 基准策略校准为玩家版策略。
  - 支持二元动作 `logit shift` 和多动作 `softmax bias`。

- `range_engine.py`
  - 使用校准后的策略做贝叶斯范围更新。
  - 只负责对手范围。

- `hero_engine.py`
  - 基于当前映射结果、对手后验范围和玩家倾向输出 Hero 建议。

- `explain.py`
  - 统一生成结构化解释。

现有模块的未来角色:

- `strategy/runtime/preflop.py`: 退化为 adapter。
- `strategy/opponent_range/predictor.py`: 退化为 facade 或兼容壳。
- `strategy/preflop_parse/*`: 继续作为 solver 数据读取层。

## 节点映射设计

### 动作族

在进入映射前, 所有真实动作必须先归一到 `ActionFamily`。第一阶段建议支持:

- `FOLD`
- `LIMP`
- `OVERLIMP`
- `OPEN`
- `ISO_RAISE`
- `CALL_VS_OPEN`
- `CALL_VS_3BET`
- `THREE_BET`
- `SQUEEZE`
- `FOUR_BET`
- `JAM`

这一步必须按语义划分, 不能继续把所有 raise 都当成同一类。

### 四层 fallback

映射过程统一使用 4 层回退:

1. `Level 0: Exact Node`
   - 存在完全匹配节点时直接使用。
2. `Level 1: Exact Family Match`
   - exact history 不存在, 但存在同一 action family 和相同位置结构。
3. `Level 2: Nearest Neighbor Match`
   - 从同类公共状态里按距离函数选取多个候选节点并加权平均。
4. `Level 3: Synthetic Template`
   - solver 中找不到足够近的节点时, 使用默认模板先验。

### 距离函数

距离不能按字符串 token 计算, 必须按公共决策状态计算。第一阶段先使用可解释的加权距离:

```text
d(state, candidate)
= w1 * family_mismatch
+ w2 * position_distance
+ w3 * aggressor_distance
+ w4 * caller_count_gap
+ w5 * limp_count_gap
+ w6 * ip_oop_mismatch
+ w7 * log_size_gap
+ w8 * stack_gap
+ w9 * remaining_players_gap
```

硬规则:

- `action_family` 不同要重罚分。
- `IP/OOP` 不同要重罚分。
- `open` 与 `open + cold call` 不能视为轻微偏差。
- `raise size` 用 `log(size)` 差异, 不用线性差值。
- `caller_count` 和 `limp_count` 需要保留数量信息。

候选节点按下式归一化加权:

```text
weight_i = exp(-d_i / tau)
```

### 尺度偏离

尺度偏离必须拆为两层:

1. `价格效应`
   - 默认总是启用。
   - 大 size 先缩紧边缘 continue。
   - 小 size 先放宽边缘 continue。

2. `范围信号效应`
   - 默认关闭。
   - 只有玩家历史证明 `size bucket -> strength` 相关时才启用。

价格修正不是整体平移, 而是从边界向中心收缩或放宽。顶端 value 基本保持不动。

### 模板先验

`Level 3` 的模板先验至少包含以下结构:

- `LIMP`: 弱且 capped, 保留少量 trap。
- `OPEN + COLD CALL`: opener 相对 uncapped, caller 为 condensed + capped。
- `MULTI-LIMP`: 多个弱进入范围, Hero 的 iso 更偏线性价值。

## 玩家倾向与策略校准

### 三层画像

玩家画像由三层信息合成:

- `PopulationPrior`
- `PlayerObservedStats`
- `ProfileBlend`

这样可以在小样本时回落到群体, 在样本充分时释放 exploit 强度。

### 统计维度

第一阶段 preflop 的统计至少按以下维度组织:

- `table_format`
- `effective_stack_bucket`
- `actor_position`
- `action_family`
- `aggressor_position`
- `ip_oop`
- `caller_count_bucket`
- `limp_count_bucket`
- `size_bucket`

### 平滑公式

所有动作频率统一使用:

```text
p_hat = (n_act + k * mu) / (N + k)
confidence = N / (N + k_conf)
```

其中:

- `mu`: 群体先验均值。
- `n_act`: 当前动作样本数。
- `N`: 当前节点族总样本数。
- `k`: 先验强度。
- `k_conf`: 置信度衰减参数。

### 动作独立排序

系统必须保留每个动作自己的排序:

- `open_rank`
- `call_rank`
- `three_bet_rank`
- `four_bet_rank`
- `limp_rank`
- `iso_rank`

排序优先来自 solver 的 action EV / action frequency, 不足时才回退模板。

### 校准公式

二元动作使用:

```text
p_new(h, act) = sigmoid(logit(p_gto(h, act)) + lambda)
```

多动作使用:

```text
p_new(h, a) ∝ exp(log(p_gto(h, a)) + lambda_a)
```

目标是让动作总体频率与 `p_hat` 对齐, 同时保留 solver 的相对顺序。

尺寸信号作为可选层接入:

```text
lambda_total = lambda_freq + confidence * lambda_size_signal
```

默认只启用价格效应, 不自动把更大 size 解释成更强范围。

## 范围更新设计

`RangeEngine` 的核心更新公式固定为:

```text
R_after(h) ∝ R_before(h) * P_calibrated(a* | h, state)
```

其中:

- `R_before(h)`: 当前玩家行动前的先验范围。
- `a*`: 当前观测到的真实动作。
- `P_calibrated(a* | h, state)`: 校准后的玩家版动作策略。

这要求范围更新必须使用校准后的策略, 而不是原始 solver 策略。

几个关键后验形状:

- `UTG tight open`: open 范围更线性, 边界 open 先被删掉。
- `MP cold call vs UTG open`: call 范围为 condensed, 顶端和底端同时变薄。
- `limp-call 玩家`: 范围偏中低强度且强调可实现率, 保留极少量 trap。

## Hero 决策设计

### 决策链路

Hero 决策固定走以下步骤:

1. 构造 Hero 当前的 `PreflopDecisionState`。
2. 通过 `NodeMapper` 获取 `MappedSolverContext`。
3. 读取 Hero 视角的 solver 基准策略。
4. 收集相关对手的 `PlayerTendencyProfile + RangeBelief`。
5. 通过 `PolicyCalibrator` 生成 exploit 后的 Hero 策略。
6. 输出建议动作、建议尺度、动作分布、置信度和解释。

### exploit 信号

Hero 的 exploit 偏移主要来自三类信号:

- `range_pressure`: 对手后验范围比标准更紧还是更宽。
- `price_pressure`: 实际 size 导致的价格变化。
- `behind_pressure`: 身后玩家的 squeeze、defend、overcall 倾向。

内部应保留完整动作分布, 第一阶段由外层使用 `argmax` 输出最终建议。

### 结构化解释

解释输出至少包括:

- `state_summary`
- `mapped_node_summary`
- `population_baseline`
- `player_adjustments`
- `range_adjustments`
- `price_adjustments`
- `behind_player_adjustments`
- `final_action_ranking`
- `fallback_notes`

## 第一阶段实施切分原则

第一阶段必须同时打通三条主线:

1. `Node Mapping`
2. `Villain Range`
3. `Hero Decision`

但严格限制在 preflop 范围内, 不额外引入 postflop 或训练系统。

## 第一阶段验收标准

第一阶段至少满足:

- limp、open + cold call、非标准 size 不再依赖字符串替换兜底。
- 对手范围会因玩家频率不同而产生不同的后验形状。
- call range 不再被当成简单 top-x%, 而能形成 condensed range。
- Hero 建议能显式响应:
  - 对手过紧。
  - 对手过松。
  - 盲位防守不足。
  - limp-fold / limp-call 差异。
  - open size 价格变化。
- 所有决策链路都能输出结构化解释。
- `runtime` 与 `opponent_range` 共用同一套 preflop 内核。

## 测试策略

### 单元测试

新增单元测试覆盖:

- 状态抽象。
- 映射距离。
- 频率平滑。
- `logit/softmax` 校准。
- 贝叶斯更新。

### 集成测试

新增集成测试覆盖:

- `UTG tight open`
- `MP cold call condensed`
- `BTN steal vs under-defending blinds`
- `ISO vs different limp profiles`
- `non-standard size` 的价格收缩/放宽

### 回归测试

保留并补充回归:

- 标准行动线的精确命中不退化。
- fallback 输出的解释字段稳定存在。
- 现有 runtime 与 opponent_range adapter 仍能对接共享内核。

## 风险与取舍

- 第一阶段的距离权重和 exploit 强度先采用可解释规则, 不做自动训练。
- 共享内核会增大初次重构体量, 但能显著降低后续 limp/cold call/size 偏离的维护成本。
- 不承诺第一阶段内部接口兼容, 但会优先保留外层 adapter 以降低接入成本。

## 结论

本次重构的核心不是新增更多 fallback, 而是确立统一的 preflop 推理内核:

> 状态抽象是主键, 节点映射是入口, 玩家倾向校准是 exploit 核心, 贝叶斯更新与 Hero 决策共享同一策略骨架。
