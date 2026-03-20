# strategy_engine/ — 策略引擎 CLAUDE.md

> 模块路径：`src/bayes_poker/strategy/strategy_engine/`
> 职责：贝叶斯对手建模 + GTO Hero 决策的核心引擎

---

## 架构概览

```
StrategyEngine (engine.py)
    │
    ├── OpponentPipeline (opponent_pipeline.py)
    │     ├── StrategyNodeMapper      → 匹配 GTO 节点
    │     ├── GtoPriorBuilder         → 构建 169 维先验策略
    │     ├── PlayerNodeStatsAdapter  → 加载玩家节点统计
    │     └── _adjust_belief_with_stats_and_ev → 后验更新
    │
    └── HeroGtoResolver (hero_resolver.py)
          ├── StrategyNodeMapper      → 匹配 Hero 节点
          └── 采样 GTO 动作
```

---

## 模块清单

| 文件 | 职责 |
|------|------|
| `contracts.py` | 强类型决策结果 + `StrategyHandler` Protocol |
| `engine.py` | `StrategyEngine` facade + `build_strategy_engine()` 工厂 |
| `opponent_pipeline.py` | 对手范围贝叶斯更新管线 |
| `hero_resolver.py` | Hero GTO 动作解析 |
| `calibrator.py` | 行动策略校准（multinomial/binary） |
| `gto_policy.py` | `GtoPriorPolicy` / `GtoPriorBuilder` |
| `node_mapper.py` | 节点上下文 → 数据库节点匹配 |
| `context_builder.py` | `ObservedTableState` → 节点查询上下文 |
| `repository_adapter.py` | `PreflopStrategyRepository` 适配层 |
| `stats_adapter.py` | `PlayerStatsRepository` 适配层 |
| `session_context.py` | 会话内对手范围状态存储（带超时清理） |
| `core_types.py` | `ActionFamily` 等基础枚举 |
| `posterior.py` | 策略后验 |
| `handler.py` | 顶层处理器 |
| `utg_open_ev_validation.py` | UTG open EV 验证工具 |

---

## 决策类型（`contracts.py`）

```python
StrategyDecision = (
    RecommendationDecision      # 有推荐动作（含 EV、置信度、范围分解）
    | NoResponseDecision        # 非 Hero 回合
    | UnsupportedScenarioDecision # 超出支持矩阵
    | SafeFallbackDecision      # 可降级错误
)
```

`StrategyHandler` Protocol：
```python
async def __call__(session_id: str, observed_state: ObservedTableState) -> StrategyDecision
```
`StrategyEngine` 实现此 Protocol，可直接注入 `WebSocketServer`。

---

## 引擎构建（`engine.py`）

```python
engine = build_strategy_engine(StrategyEngineConfig(
    strategy_db_path=Path("data/database/strategy.db"),
    player_stats_db_path=Path("data/database/player_stats.db"),
    table_type=TableType.SIX_MAX,
    source_ids=(1, 2, 3),           # 可指定多个策略源
    enable_global_raise_blending=True,
))
```

---

## 对手管线（`opponent_pipeline.py`）

### `OpponentPipeline.process_hero_snapshot()`

在每次 Hero 回合触发，执行：

1. **指纹去重**：`get_action_history_string()` 生成 `F-C-R8` 格式指纹，避免重复计算
2. **区分对手**：
   - `acted_opponents`：已行动过的对手 → 全流程贝叶斯更新
   - `prior_only_opponents`：尚未行动的对手 → 暂存 prior_only_deferred
3. 对每个已行动对手：
   - `_build_initial_prior_range()` → GTO 先验（169 维策略向量）
   - `_build_posterior_range()` → 贝叶斯后验更新
   - 结果存入 `StrategySessionContext.player_ranges[seat]`

### `_adjust_belief_with_stats_and_ev()`

核心算法：
```
prior_range（169 维） + 玩家统计频率 → posterior_range
```
- **增质量**：高 EV 手牌优先增加概率，直到达到目标频率
- **减质量**：低 EV 手牌优先减少概率，直到达到目标频率
- **激进混合**（当 `enable_global_raise_blending=True`）：
  ```
  target = node_confidence × stats_raise_freq + (1-node_confidence) × global_pfr
  ```

---

## 会话上下文（`session_context.py`）

`StrategySessionStore` 管理多桌会话：
- `get_or_create(session_id, hand_id, ...)` → 自动检测新手牌（`hand_id` 变化时重置）
- `cleanup_expired()` → 清理超时会话（默认 30 分钟）
- `StrategySessionContext.player_ranges`：`dict[seat_index, PreflopRange]`

---

## 重要约束与限制

1. **仅支持翻前（Preflop）贝叶斯更新**：`opponent_pipeline` 当前仅处理 `Street.PREFLOP` 动作
2. **筹码深度写死**：`stack_bb=100`（TODO 注释，后续需动态解析）
3. **Hero 解析器 source_id**：`HeroGtoResolver` 写死使用 `source_id=5`
4. **EV 向量维度**：169（按 RANGE_169_ORDER 排列的手牌类型）
5. **置信度计算**：`stats_adapter` 根据样本量计算节点置信度，低样本时自动降权

---

## 调试建议

- 设置 `BAYES_POKER_LOG_LEVEL=DEBUG` 可观察策略匹配、信念更新过程
- `StrategySessionContext.player_summaries[seat]` 包含 `source_kind`（prior/pool/actual）和 `prior_frequency`
- `RecommendationDecision.opponent_aggression_details` 含各对手激进度细节
- `RecommendationDecision.adjusted_belief_ranges` 含调整后的 169 维范围（测试用）
