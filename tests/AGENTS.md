# tests/ AGENTS 指南

> 作用域: `tests/**`。
> 目标: 约束测试实现方式, 并沉淀可复用工具函数说明, 便于 AI Agent 在新增测试时直接复用。

## 通用约束

- 统一使用中文说明与断言语义。
- 新增 Python 测试代码必须带类型标注。
- 新增函数需包含中文 Google 风格 docstring。
- 涉及真实数据/大样本测试时, 默认跳过, 必须使用环境变量显式启用。

## 真实场景测试复用工具

来源文件: `tests/real_scenario/helpers.py`（公共 helper 模块）

### 常量

- `REPO_ROOT` / `STRATEGY_DB_PATH` / `PLAYER_STATS_DB_PATH` / `PLAYER_CORE_STATS_CSV_PATH`: 项目路径常量。
- `RUN_REAL_SCENARIO_ENV`: 环境变量名 (`BAYES_POKER_RUN_REAL_SCENARIO_TESTS`)。
- `PREFLOP_ACTION_ORDER_6MAX`: 翻前行动顺序 `[UTG, MP, CO, BTN, SB, BB]`。
- `ALL_RFI_COMBINATIONS_6MAX`: 全部 15 种合法 RFI 位置组合 `(opener, hero)`。
- `ALL_3BET_COMBINATIONS_6MAX`: 全部 20 种合法 3-Bet 位置组合 `(opener, 3bettor, hero)`。
- `ALL_4BET_COMBINATIONS_6MAX`: 全部 15 种合法 4-Bet 位置组合 `(opener, 3bettor, 4bettor, hero)`。
- `ALL_FACING_3BET_COMBINATIONS_6MAX`: 全部 15 种合法 Facing 3-Bet 位置组合 `(hero_opener, 3bettor)`。

### 数据结构

1. `PlayerPfrRow`
   - 用途: 承载从 `player_core_stats.csv` 读取的玩家最小统计视图。
   - 字段: `player_name`, `total_hands`, `pfr_pct`。

2. `HeroStrategySnapshot`
   - 用途: 承载单个玩家在真实场景下的 Hero 策略结果快照。
   - 字段: `player_name`, `total_hands`, `pfr_pct`, `selected_node_id`, `selected_source_id`, `action_distribution`, `prior_action_distribution`, `opponent_aggression_details`, `sampling_random`, `sampled_action_code`, `gtoplus_by_action`。

### 工具函数清单

1. `load_players_with_large_pfr_spread(csv_path, min_hands, sample_count) -> list[PlayerPfrRow]`
   - 功能: 从 `player_core_stats.csv` 过滤 `SIX_MAX` 且 `total_hands > min_hands` 玩家, 按 `pfr_pct` 排序后做等距采样。
   - 适用场景: 需要构造「玩家风格差异明显」的真实样本集。

2. `build_even_spread_indexes(total_count, sample_count) -> list[int]`
   - 功能: 在有序样本中生成等距索引并去重。
   - 适用场景: 任意指标排序后的均匀抽样。

 3. `build_rfi_state(hero_position, opener_position, opener_player_name, ...) -> ObservedTableState`
    - 功能: 构造任意 RFI 场景的 6-max preflop 观察状态 (opener open raise, 中间玩家 fold, 轮到 hero)。
    - 适用场景: 覆盖全位置 RFI 场景, 替代硬编码的单一位置构造函数。

 4. `build_3bet_state(hero_position, opener_position, bettor_3bet_position, ...) -> ObservedTableState`
    - 功能: 构造任意 3-Bet 场景的 6-max preflop 观察状态 (opener open → folds → 3bettor 3bet → folds → hero 决策)。
    - 约束: opener < 3bettor < hero (按 `PREFLOP_ACTION_ORDER_6MAX` 顺序)。
    - 默认尺寸: open_size=2.5bb, three_bet_size=8.0bb。
    - 适用场景: 覆盖全位置 3-Bet 场景测试。

 5. `build_4bet_state(hero_position, opener_position, bettor_3bet_position, bettor_4bet_position, ...) -> ObservedTableState`
    - 功能: 构造任意 4-Bet 场景的 6-max preflop 观察状态 (opener open → folds → 3bettor 3bet → folds → 4bettor 4bet → folds → hero 决策)。
    - 约束: opener < 3bettor < 4bettor < hero (按 `PREFLOP_ACTION_ORDER_6MAX` 顺序)。
    - 默认尺寸: open_size=2.5bb, three_bet_size=8.0bb, four_bet_size=20.0bb。
    - 适用场景: 覆盖全位置 4-Bet 场景测试。

 6. `_should_fold_in_multibet(pos, opener_idx, hero_idx, raiser_positions) -> bool`
    - 功能: 判断在多次加注场景中, 给定位置的玩家是否应该 fold (非加注者且在 opener 到 hero 之间)。
    - 适用场景: `build_3bet_state` / `build_4bet_state` 内部使用。

 7. `build_facing_3bet_state(hero_opener_position, three_bettor_position, three_bettor_player_name, ...) -> ObservedTableState`
    - 功能: 构造 Hero 作为 opener 遭遇 3-Bet 的 6-max preflop 观察状态 (Hero open → folds → 3bettor 3bet → 剩余 fold → 回到 Hero 决策)。
    - 约束: hero_opener < 3bettor (按 `PREFLOP_ACTION_ORDER_6MAX` 顺序)。
    - 与 `build_3bet_state` 的区别: Hero 就是 opener, 已有 RAISE 记录和投注额。
    - 默认尺寸: open_size=2.5bb, three_bet_size=8.0bb。
    - 适用场景: 覆盖 Hero RFI 后遭遇 3-Bet 的全位置场景测试。

 8. `_should_fold_in_facing_3bet(pos, hero_opener_position, three_bettor_position) -> bool`
    - 功能: 判断在 Hero 作为 opener 遭遇 3bet 场景中, 给定位置是否已 fold。
    - fold 区间: hero_opener 之后到 3bettor 之前 + 3bettor 之后到行动序列末尾。
    - 适用场景: `build_facing_3bet_state` 内部使用。

 9. `load_gtoplus_ranges_for_decision(engine, decision, min_strategy) -> dict[str, str]`
   - 功能: 导出 `action_code -> GTO+` 文本。优先使用 `decision.adjusted_belief_ranges` 中经贝叶斯调整后的 belief_range; 仅当该字段为空时回退到通过 `selected_node_id` 回查数据库原始范围。
   - 适用场景: 对比不同玩家画像下的动作范围差异（调整后范围会随对手统计数据变化）。

10. `write_gtoplus_exports(output_dir, snapshot) -> None`
    - 功能: 将单个快照中的各动作范围写出为 GTO+ 文本文件。
    - 适用场景: 保留离线分析产物、人工审阅策略范围。

11. `print_snapshot(snapshot) -> None`
    - 功能: 打印单玩家快照（节点/源/随机数/动作分布/GTO+ 文本）。
    - 适用场景: 调试与肉眼比对策略输出。

12. `print_pairwise_range_comparison(snapshots) -> None`
    - 功能: 打印与基准玩家的动作范围差异集合 `changed_actions`。
    - 适用场景: 快速判断玩家画像变化是否影响 Hero 范围。

13. `build_snapshot_from_decision(player_row, decision, gtoplus_by_action) -> HeroStrategySnapshot`
    - 功能: 从 engine 推荐结果构造快照对象。
    - 适用场景: 批量测试中统一封装推荐结果。

14. `assert_valid_recommendation(decision, label) -> RecommendationDecision`
    - 功能: 校验 StrategyEngine 返回结果是合法的 RecommendationDecision 并做类型收窄。
    - 适用场景: 所有真实场景测试的通用断言。

### 共享 Fixtures (conftest.py)

来源文件: `tests/real_scenario/conftest.py`

1. `real_scenario_engine` (module-scoped): 构建 `StrategyEngine` 实例。
2. `selected_players` (module-scoped): 加载 3 名 PFR 差异明显的玩家。
3. 自动跳过: 未设置 `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1` 时跳过整个包。

### 场景专用函数 (各测试文件私有)

- `test_hero_strategy_engine_btn_utg_open.py::_build_btn_vs_utg_open_state()`: BTN vs UTG open 硬编码场景。

## 复用建议（给 AI Agent）

1. 优先复用 `tests/real_scenario/helpers.py` 中的工具函数, 避免重复实现 CSV 解析、场景构造、GTO+ 导出逻辑。
2. 新增 RFI 场景测试时, 使用 `build_rfi_state()` 构造观察状态, 不要硬编码玩家列表。
3. 新增 3-Bet 场景测试时, 使用 `build_3bet_state()` 构造观察状态, 传入 opener/3bettor/hero 位置。
4. 新增 4-Bet 场景测试时, 使用 `build_4bet_state()` 构造观察状态, 传入 opener/3bettor/4bettor/hero 位置。
5. 新增 Hero 作为 opener 遭遇 3-Bet 场景测试时, 使用 `build_facing_3bet_state()` 构造观察状态, 传入 hero_opener/3bettor 位置。
6. 使用 `assert_valid_recommendation()` 做推荐结果的通用断言。
7. 使用 `conftest.py` 中的共享 fixtures (`real_scenario_engine`, `selected_players`)。
8. 真实场景测试统一使用环境变量门控:
    - `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1`
9. 推荐执行命令:
    - `BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 uv run pytest -q -s tests/real_scenario/`
