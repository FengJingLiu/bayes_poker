# Strategy 模块

策略模块以 `strategy_engine/` 为唯一运行时主链路, `preflop_parse/` 负责离线策略导入, `range/` 提供范围模型。

## 结构

```
strategy/
├── __init__.py              # 惰性导出
├── strategy_engine/         # v2 主链路: context -> sqlite -> mapper -> posterior -> hero resolver
├── preflop_parse/           # GTOWizard 风格策略解析与 SQLite ingest/build
└── range/                   # 范围模型与映射
```

> 旧模块 `preflop_engine/`、`runtime/`、`opponent_range/` 已废弃删除。
> `ActionFamily` 唯一定义位于 `strategy_engine/core_types.py`, `preflop_parse` 也从此处导入。

## strategy_engine v2 主链路

### v1 支持矩阵

- 仅支持 `6-max`
- 仅支持 `Street.PREFLOP`
- 支持 **首次行动** 的 `OPEN / CALL_VS_OPEN / LIMP`
- 支持 **actor reentry** 的翻前决策, 当前重点覆盖 `Hero open -> facing 3-bet`
- 对手 posterior 使用 **当前决策点前仍存活对手的最近一次翻前动作**
- 明确不支持: `limp-after-raise`、HU、9-max、postflop、完整 hero posterior

### 关键模块

| 模块 | 职责 |
|------|------|
| `core_types.py` | `ActionFamily`、`NodeContext`、`PlayerNodeContext` |
| `context_builder.py` | `ObservedTableState -> NodeContext + PreFlopParams` |
| `repository_adapter.py` | 封装 `PreflopStrategyRepository` 的 v2 中性读接口 |
| `stats_adapter.py` | `PlayerStatsRepository.get(...)` 节点概率适配 |
| `node_mapper.py` | 最近节点匹配、距离评分、价格修正 |
| `gto_policy.py` | 读取最近节点动作先验, 同名动作编码视为数据异常并抛错 |
| `calibrator.py` | binary / multinomial 校准与尺寸质量再分配 |
| `posterior.py` | `prior * likelihood` 后验更新与低质量回退 |
| `session_context.py` | hero-turn 会话内存与幂等/新手牌重置 |
| `opponent_pipeline.py` | 已行动对手 posterior, 未行动对手 prior_only |
| `hero_resolver.py` | hero 当前节点的 GTO 推荐（v1 不做 hero posterior） |
| `engine.py` / `handler.py` | facade 与 `create_strategy_handler()` |
| `utg_open_ev_validation.py` | UTG open 节点 EV 调整验证、玩家筛选与 GTO+ 导出 |

### 核心调用链 (Call Logic)

`StrategyEngine.__call__(session_id, observed_state)` 为顶层入口, 调用流程如下:

1. **前置拦截（Hero Turn Validations）**
   - 若 `actor_seat != hero_seat`, 直接返回 `NoResponseDecision`。

2. **对手范围更新阶段 (`OpponentPipeline.process_hero_snapshot`)**
   - **会话与缓存管理**: 从 `StrategySessionStore` 取出会话级缓存。若当前 Action Fingerprint 未变, 直接返回缓存上下文, 避免重复计算。
   - **已行动对手 (Posterior 更新)**:
     - `ObservedTableState` 负责提供当前决策点视图, 包括完整翻前前缀、指定动作索引之前的前缀、当前仍存活对手的最近一次动作索引。
     - `build_player_node_context`: 构建对手历史的 NodeContext。
     - `PlayerNodeStatsAdapter.load`: 加载玩家历史群体统计概率。
     - `StrategyNodeMapper.map_node_context`: 把上下文映射到策略库中的最近 GTO 节点。
     - `GtoPriorBuilder.build_policy`: 计算该节点的 GTO 策略先验（Prior）。
     - `_select_matching_prior_action`: 按真实动作类型严格匹配, 并在同类型中按尺度选择最近动作。
     - `_adjust_belief_with_stats_and_ev`: 根据玩家平滑 stats 频率与 GTO 频率差异, 按 EV 排序做约束式信念重分配。
     - 仅为当前决策点前仍存活且已行动的对手保留 posterior。
   - **未行动对手 (暂缓建模)**:
     - 当前版本不对未行动玩家构建精细 `player_range`, 并在代码中保留 TODO 后续恢复。
     - `player_summaries` 仅记录 `status=prior_only_deferred`。
   - 返回 `StrategySessionContext`（已行动对手保留 posterior range; 未行动对手暂不提供先验统计摘要）。

3. **Hero 推荐生成阶段 (`HeroGtoResolver.resolve`)**
   - 构建 Hero 当前状态的 NodeContext。
   - `StrategyNodeMapper.map_node_context` -> `GtoPriorBuilder.build_policy` 获取当前 Hero 节点的 GTO 策略环境。
   - 通过 `_adjust_hero_policy` 根据对手激进度统计做贝叶斯调整, 产出调整后策略。
   - `_extract_adjusted_belief_ranges` 从调整后策略中提取 `action_code -> PreflopRange` 映射, 填充到 `RecommendationDecision.adjusted_belief_ranges` 字段。
   - TODO: 后续恢复未行动玩家 `stats vs gto` 启发式调节链路。
   - `range_breakdown` 仅包含已计算 posterior 的对手范围。

## 顶层导出 API

```python
# strategy_engine 主链路
StrategyHandler
StrategyDecision
RecommendationDecision
NoResponseDecision
UnsupportedScenarioDecision
SafeFallbackDecision
StrategyEngine
StrategyEngineConfig
create_strategy_handler

# preflop_parse 解析/构建
STRATEGY_VECTOR_LENGTH, PreflopStrategy, StrategyAction, StrategyNode
normalize_token, parse_all_strategies, parse_bet_size_from_code
parse_file_meta, parse_strategy_directory, parse_strategy_file
parse_strategy_node, split_history_tokens
```

## 约定

- `preflop_parse` 仅保留 SQLite ingest/build 路径, 不再是运行时主查询路径
- `ActionFamily` 唯一定义在 `strategy_engine/core_types.py`
- `table context` 只保存在 `strategy_engine` 会话内存中
- `PlayerStatsRepository` 节点概率统一通过 `PreFlopParams.to_index()` 映射
- `_build_prior_range_from_policy` 与 `_resolve_action_prior_range` 为强校验路径: 缺动作/缺 belief_range 时直接抛错, 不做隐式兜底
- **对手数据要求**: 当玩家总手数不足 10 手或 VPIP 与 PFR 均为 0 时, `stats_adapter` 自动回退到预聚合玩家池数据 (`aggregated_sixmax_100`), 避免极端统计导致贝叶斯后验坍缩为零。判断逻辑位于 `stats_adapter._should_fallback_to_population()`。

## 测试

- `test_strategy_engine_v2_import_boundaries.py`
- `test_strategy_engine_v2_context_builder.py`
- `test_strategy_engine_v2_repository_adapter.py`
- `test_strategy_engine_v2_stats_adapter.py`
- `test_strategy_engine_v2_mapper.py`
- `test_strategy_engine_v2_posterior.py`
- `test_strategy_engine_v2_opponent_pipeline.py`
- `test_strategy_engine_v2_hero_resolver.py`
- `test_strategy_engine_v2_server_integration.py`
- `test_preflop_parse_records.py`
- `test_preflop_strategy_repository.py`
