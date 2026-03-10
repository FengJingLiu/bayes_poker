# Strategy 模块

策略模块当前采用“双层结构”：

1. **`strategy_engine/`** 是新的 SQLite-driven v2 主链路。
2. **`preflop_parse/`、`preflop_engine/`、`runtime/`** 保留为导入链、参考实现与兼容层。

## 结构

```
strategy/
├── __init__.py              # 惰性导出（顶层 StrategyHandler 已切到 v2）
├── strategy_engine/         # v2 主链路：context -> sqlite -> mapper -> posterior -> hero resolver
├── preflop_parse/           # GTOWizard 风格策略解析与 SQLite ingest/build
├── preflop_engine/          # 旧翻前参考实现（mapper/calibrator/range/hero 逻辑参考）
├── runtime/                 # 旧运行时兼容层（不再是新主链路）
├── opponent_range/          # 旧对手范围实现（保留参考与现有工具）
└── range/                   # 范围模型与映射
```

## strategy_engine v2 主链路

### v1 支持矩阵

- 仅支持 `6-max`
- 仅支持 `Street.PREFLOP`
- 仅支持 **首次行动** 的 `OPEN / CALL_VS_OPEN / LIMP`
- 明确不支持：`three_bet+`、HU、9-max、postflop、hero posterior

### 关键模块

| 模块 | 职责 |
|------|------|
| `core_types.py` | `ActionFamily`、`NodeContext`、`PlayerNodeContext` |
| `context_builder.py` | `ObservedTableState -> query_history + NodeContext + PreFlopParams` |
| `repository_adapter.py` | 封装 `PreflopStrategyRepository` 的 v2 中性读接口 |
| `stats_adapter.py` | `PlayerStatsRepository.get(..., smooth_with_pool=True)` 节点概率适配 |
| `node_mapper.py` | 最近节点匹配、距离评分、价格修正 |
| `gto_policy.py` | 候选节点按距离衰减混合成 GTO 先验 |
| `calibrator.py` | binary / multinomial 校准与尺寸质量再分配 |
| `posterior.py` | `prior * likelihood` 后验更新与低质量回退 |
| `session_context.py` | hero-turn 会话内存与幂等/新手牌重置 |
| `opponent_pipeline.py` | 已行动对手 posterior, 未行动对手 prior_only |
| `hero_resolver.py` | hero 当前节点的 GTO 推荐（v1 不做 hero posterior） |
| `engine.py` / `handler.py` | facade 与 `create_strategy_handler()` |

### 核心调用链 (Call Logic)

`StrategyEngine.__call__(session_id, observed_state)` 为顶层入口，调用流程如下：

1. **前置拦截（Hero Turn Validations）**
   - 若 `actor_seat != hero_seat`，直接返回 `NoResponseDecision`。

2. **对手范围更新阶段 (`OpponentPipeline.process_hero_snapshot`)**
   - **会话与缓存管理**：从 `StrategySessionStore` 取出会话级缓存。若当前 Action Fingerprint 未变，直接返回缓存上下文，避免重复计算。
   - **已行动对手 (Posterior 更新)**：
     - `build_player_node_context`：构建对手历史的 NodeContext。
     - `PlayerNodeStatsAdapter.load`：加载玩家历史群体统计概率。
     - `StrategyNodeMapper.map_node_context`：把上下文映射到策略库中的最近 GTO 节点。
     - `GtoPriorBuilder.build_policy`：计算该节点的 GTO 策略先验（Prior）。
     - `_calibrate_policy`：利用玩家历史统计概率校准 GTO 先验分布。
     - `update_posterior`：结合实际 Action，执行贝叶斯更新得到对手 Posterior Range。
   - **未行动对手 (Prior 只有)**：
     - 使用根据位置设定的固化频率初始 Prior Range。
   - 返回 `StrategySessionContext` (包含各对手最新的 `player_ranges` 和分析摘要)。

3. **Hero 推荐生成阶段 (`HeroGtoResolver.resolve`)**
   - 构建 Hero 当前状态的 NodeContext。
   - `StrategyNodeMapper.map_node_context` -> `GtoPriorBuilder.build_policy` 获取当前 Hero 节点的 GTO 策略环境。
   - 选取最高频率（blended_frequency）的操作作为 `RecommendationDecision`。
   - 将上一步 `OpponentPipeline` 生成的对手 `range_breakdown` 合并入 Decision 中返回。

## 顶层导出 API

### 新主链路导出

```python
StrategyHandler
StrategyDecision
RecommendationDecision
NoResponseDecision
UnsupportedScenarioDecision
SafeFallbackDecision
StrategyEngine
StrategyEngineConfig
create_strategy_handler
```

### 旧兼容/参考导出

```python
PreflopLayer, PreflopRuntimeConfig
create_preflop_strategy, create_preflop_strategy_from_directory
create_postflop_strategy, infer_preflop_layer
load_preflop_strategy_from_directory
STRATEGY_VECTOR_LENGTH, PreflopStrategy, StrategyAction, StrategyNode
OpponentRangePredictor, create_opponent_range_predictor
```

## 约定

- 新主链路运行时 **不得** import `preflop_engine`、`runtime`、`preflop_parse.query`
- `preflop_parse` 仅保留 SQLite ingest/build 路径, 不再是运行时主查询路径
- `table context` 只保存在 `strategy_engine` 会话内存中
- `PlayerStatsRepository` 节点概率统一通过 `PreFlopParams.to_index()` 映射

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

旧测试仍保留, 用作参考实现与回归基线。
