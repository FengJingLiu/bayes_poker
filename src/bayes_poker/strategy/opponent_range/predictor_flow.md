## 对手范围预测器流程总结

本文总结 `predictor.py` 的核心执行路径, 用于快速理解当前实现。

### 1. 入口函数

入口为 `OpponentRangePredictor.update_range_on_action(...)`。

1. 若 `action.street == Street.PREFLOP`, 进入 `_update_preflop_range(...)`。
2. 否则进入 `_update_postflop_range(...)`。
3. 当前翻后主逻辑未实现, `_update_postflop_range(...)` 仅记录 debug 日志。

### 2. 翻前主流程

`_update_preflop_range(...)` 是当前核心。

1. 若动作是 `FOLD`, 直接将该座位翻前和翻后范围置零并返回。
2. 构建并清洗动作前缀:
   - `preflop_prefix`: 仅保留翻前动作。
   - `previous_prefix`: 去掉可能重复的“当前动作”尾项。
   - `current_prefix`: 在 `previous_prefix` 基础上补上当前动作。
3. 判断是否为玩家首次翻前动作:
   - 首次动作: `_handle_preflop_first_action(...)`。
   - 非首次动作: `_handle_preflop_non_first_action(...)`。

### 3. 首次翻前动作分支

在进入旧场景分类前, 当前实现会先尝试共享 preflop 内核:

1. 调用 `_try_update_with_shared_preflop_engine(...)`。
2. 仅当共享状态层能表达当前 `decision_prefix` 时继续:
   - UTG first-in open
   - 单次 open 面前且无前置 caller 的 cold call
3. 首次 3bet、squeeze、overcall 仍显式回退到旧逻辑。
4. 共享链路依次经过:
   - `build_preflop_decision_state(...)`
   - `PreflopNodeMapper`
   - `ActionPolicy` + 最小玩家画像校准
   - `RangeEngine.observe_action(...)`
5. 若共享链路任一步失败, 则继续走下面的旧场景分类与回退逻辑。

先通过 `_classify_first_preflop_scenario(...)` 分类场景:

1. `FIRST_LIMP`
2. `FOLLOW_LIMP`
3. `RFI_NO_LIMPER`
4. `RFI_HAVE_LIMPER`
5. `THREE_BET`
6. `FOUR_BET`
7. `UNKNOWN`

分类规则依赖前缀中的 `raise_count` 与 `limp_count`, 并用
`_is_raise_like_action(...)` / `_is_call_like_action(...)` 判断动作类型。

当前处理策略:

1. 大多数分支最终调用 `_apply_preflop_action_scale(...)`。
2. `FOLLOW_LIMP` 会先尝试 `_build_preflop_range_from_prefix(...)`。
3. `RFI_NO_LIMPER` 与 `RFI_HAVE_LIMPER` 会走
   `_build_rfi_preflop_range_from_prefix(...)`:
   - `current_prefix` 用于构建 `PreFlopParams` 并查询 RFI 频率。
   - `decision_prefix` 用于查询当前决策节点。
   - 按节点 raise EV 排序并按目标频率裁剪范围。
4. 若共享链路已经成功, 则不会再进入上述旧 RFI 路径。
5. RFI 场景若旧路径构建成功, 直接覆盖该 seat 的翻前范围并返回; 失败时回退缩放。

### 4. 非首次翻前动作分支

`_handle_preflop_non_first_action(...)` 逻辑:

1. 先找到玩家首次翻前动作 `_get_player_first_preflop_action(...)`。
2. 若找不到首次动作, 直接缩放。
3. 若首次动作是 call/check, 进入
   `_handle_non_first_after_first_call(...)`。
4. 若首次动作是 raise/bet/all-in, 进入
   `_handle_non_first_after_first_raise(...)`。
5. 以上分支当前都落到 `_apply_preflop_action_scale(...)`。

当前 Task 9 只把共享 adapter 接在“首次翻前动作”的范围构建点上,
不改变 non-first 分发壳, 以保持 server 增量 action queue 和现有测试契约。

### 5. 前缀驱动的范围构建(当前聚焦 limp)

`_build_preflop_range_from_prefix(...)`:

1. 使用 `build_opponent_preflop_context(...)` 构建上下文。
2. 仅当 `context.scenario == PreflopScenario.RFI_FACE_LIMPER` 时继续。
3. 其余场景记录 debug 日志并返回 `None`。

`_build_limp_preflop_range_from_prefix(...)`:

1. 前置依赖检查:
   - `preflop_strategy` 存在。
   - `stats_repo` 存在。
2. 上下文检查:
   - 场景必须是 `RFI_FACE_LIMPER`。
   - `context.params` 非空。
3. 数据有效性检查:
   - `stack_bb > 0`。
   - `preflop_strategy.query(100, history)` 命中策略节点。
   - 聚合统计 `get_aggregated_player_stats(...)` 可用。
4. 读取统计频率:
   - `raise_frequency = bet_raise_probability()`。
   - `call_frequency = check_call_probability()`。
5. 调用 `build_limp_calling_range(...)` 生成并返回 `PreflopRange`。

`_build_rfi_preflop_range_from_prefix(...)`:

1. 前置依赖检查:
   - `preflop_strategy` 与 `stats_repo` 可用。
2. 统计频率:
   - 通过 `build_opponent_preflop_context(...)` + `current_prefix` 获取 `PreFlopParams`。
   - 先查玩家自身统计, 无命中再回退聚合统计。
   - 读取 `bet_raise_probability()` 作为目标 RFI 频率。
3. 策略节点:
   - 用 `decision_prefix` 生成 history 查询当前决策节点。
4. EV 裁剪:
   - 收集节点内 raise/bet/all-in 动作。
   - 按 `total_frequency` 聚合 169 维 EV。
   - 按 EV 降序并依据目标频率(折算 1326 组合数)裁剪范围。

### 6. 范围初始化与缩放

`_apply_preflop_action_scale(...)`:

1. 先 ` _ensure_preflop_range_initialized(...)` 确保 seat 有初始范围。
2. 计算缩放因子 `scale = _get_preflop_action_scale(...)`。
3. 对 169 维翻前策略逐项乘以 `scale`。
4. 调用 `normalize()` 归一化。

`_ensure_preflop_range_initialized(...)`:

1. 若 seat 尚无范围, 则调用 `_get_initial_preflop_range(...)` 初始化。

`_get_initial_preflop_range(...)`:

1. 若可读取玩家统计且有 preflop 数据:
   - 使用 `vpip` 生成 `_range_from_vpip(...)`。
   - 生成成功则直接返回。
2. 否则回退到位置默认范围 `_get_position_default_range(...)`。

`_get_preflop_action_scale(...)`:

1. 基础缩放来自 `_ACTION_SCALE_FACTORS`。
2. 若有玩家统计, 且动作为 `RAISE/BET`, 且 `pfr > 0`:
   - 放大系数为 `min(1.0, base_scale * (1 + pfr / 100))`。

### 7. 翻后相关辅助逻辑

目前翻后预测主链未打通, 但包含可复用辅助函数:

1. `_get_postflop_action_scale(...)`: 按街位与下注比例调整缩放。
2. `_apply_board_blockers(...)`: 移除被公共牌阻挡的手牌组合。

### 8. 生命周期管理

1. `reset_player_ranges(...)`: 重置单个玩家的翻前/翻后范围缓存。
2. `reset_all_ranges(...)`: 重置所有玩家缓存。

### 9. 当前实现特征

1. 翻前已形成“共享 adapter + 旧回退”双层主链路。
2. `UTG` 首次 open / cold call vs open 会优先尝试共享 preflop 内核。
3. limp 与多数非首次动作仍通过旧分支或统一缩放模型收敛范围。
4. 翻后主流程仍是占位状态。
5. 后续可继续把更多 preflop 分支替换为
   更细化的策略节点映射。
