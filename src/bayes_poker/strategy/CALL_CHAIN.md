# Strategy 模块调用链

本文档描述 strategy 模块 v2 的完整调用链。

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        外部调用层 (comm 模块)                           │
│  ┌─────────────────────┐                                               │
│  │   comm/server.py    │                                               │
│  │  WebSocket 服务端   │                                               │
│  │  StrategyHandler    │                                               │
│  └──────────┬──────────┘                                               │
└─────────────┼──────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    strategy 模块入口 (__init__.py)                      │
│         惰性导出: StrategyHandler, StrategyEngine, etc.                │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
    │ strategy_engine/ │ │preflop_parse/│ │    range/     │
    │                  │ │              │ │              │
    │ StrategyEngine   │ │ PreflopStrat │ │ PreflopRange │
    │ OpponentPipeline │ │ 解析/SQLite  │ │ PostflopRange│
    │ HeroGtoResolver  │ │ ingest/build │ │              │
    │ NodeMapper       │ │              │ │              │
    │ Calibrator       │ │              │ │              │
    │ Posterior        │ │              │ │              │
    └────────┬─────────┘ └──────────────┘ └──────────────┘
             │
             ▼
    ┌─────────────────┐
    │ player_metrics/  │
    │ storage/         │
    │ (外部依赖)       │
    └─────────────────┘
```

## v2 调用链详解

### 1. 入口: 外部调用 → strategy_engine

**comm/server.py** - WebSocket 服务端:

```python
from bayes_poker.strategy.strategy_engine.contracts import StrategyHandler

# 每次 Hero 轮到行动时调用
decision = strategy_handler(session_id, observed_state)
```

### 2. StrategyEngine 核心方法调用链

```
StrategyEngine.__call__(session_id, observed_state)
│
├──► 前置拦截: actor_seat != hero_seat → NoResponseDecision
│
├──► OpponentPipeline.process_hero_snapshot()
│    │
│    ├──► 会话缓存检查 (StrategySessionStore)
│    │
│    ├──► 已行动对手 (Posterior 更新):
│    │    ├──► context_builder.build_player_node_context()
│    │    ├──► PlayerNodeStatsAdapter.load()
│    │    ├──► StrategyNodeMapper.map_node_context()
│    │    ├──► GtoPriorBuilder.build_policy()
│    │    ├──► _select_matching_prior_action()
│    │    └──► _adjust_belief_with_stats_and_ev()
│    │
│    └──► 未行动对手: status=prior_only_deferred
│
└──► HeroGtoResolver.resolve()
     ├──► context_builder.build_hero_node_context()
     ├──► StrategyNodeMapper.map_node_context()
     ├──► GtoPriorBuilder.build_policy()
     └──► RecommendationDecision
```

### 3. strategy_engine 内部依赖

| 组件 | 文件 | 用途 |
|------|------|------|
| `StrategyEngine` | `engine.py` | 顶层 facade |
| `StrategyHandler` | `handler.py` / `contracts.py` | 外部契约与工厂 |
| `ContextBuilder` | `context_builder.py` | ObservedTableState → NodeContext |
| `StrategyNodeMapper` | `node_mapper.py` | 最近节点匹配 |
| `GtoPriorBuilder` | `gto_policy.py` | GTO 策略先验 |
| `Calibrator` | `calibrator.py` | 策略频率校准 |
| `Posterior` | `posterior.py` | 贝叶斯后验更新 |
| `OpponentPipeline` | `opponent_pipeline.py` | 对手范围处理 |
| `HeroGtoResolver` | `hero_resolver.py` | Hero GTO 推荐 |
| `SessionStore` | `session_context.py` | 会话状态管理 |

### 4. 外部模块依赖

| 组件 | 用途 |
|------|------|
| `preflop_parse` | SQLite 策略库构建与解析 |
| `range/PreflopRange` | 169 维翻前范围 |
| `range/PostflopRange` | 1326 维翻后范围 |
| `player_metrics` | 玩家统计数据 |
| `storage/PreflopStrategyRepository` | SQLite 策略库读取 |

## 数据流总结

```
1. comm 层通过 StrategyHandler 调用 StrategyEngine
      ↓
2. 每次 Hero 轮到行动时:
   ├─ OpponentPipeline: 已行动对手做 posterior 更新
   │   → 从 SQLite 策略库获取最近 GTO 节点
   │   → 结合玩家统计做校准后贝叶斯更新
   │
   └─ HeroGtoResolver: 生成 Hero 推荐
       → 映射 Hero 节点到策略库
       → 基于 GTO 先验输出 RecommendationDecision
```
