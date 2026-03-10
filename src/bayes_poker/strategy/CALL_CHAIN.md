# Strategy 模块调用链

本文档描述 strategy 模块的完整调用链。

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        外部调用层 (comm 模块)                           │
│  ┌─────────────────────┐    ┌─────────────────────┐                   │
│  │   comm/server.py    │    │   comm/session.py   │                   │
│  │  WebSocket 服务端   │    │   会话管理           │                   │
│  │  set_range_predictor│    │  持 OpponentRange   │                   │
│  │  predictor.update   │    │   Predictor 实例    │                   │
│  └──────────┬──────────┘    └──────────┬──────────┘                   │
└─────────────┼──────────────────────────┼────────────────────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    strategy 模块入口 (__init__.py)                      │
│         惰性导出: OpponentRangePredictor, PreflopStrategy, etc.        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐
│ preflop_engine/predictor │  │   runtime/       │  │    preflop_engine/          │
│                 │  │                  │  │                             │
│ OpponentRange   │  │ PreflopLayer     │  │ PreflopHeroEngine          │
│ Predictor       │  │ PreflopRuntime   │  │ PreflopNodeMapper          │
│ (核心预测器)    │  │ Config           │  │ RangeEngine                │
│                 │  │ StrategyHandler  │  │ PolicyCalibrator           │
└────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘
         │                     │                          │
         │         ┌──────────┴──────────┐                │
         │         ▼                    ▼                │
         │  ┌───────────────┐  ┌──────────────┐         │
         │  │preflop_parse/ │  │    range/     │         │
         │  │               │  │              │         │
         │  │ PreflopStrategy│  │ PreflopRange │         │
         │  │ StrategyNode  │  │ PostflopRange│         │
         │  └───────────────┘  └──────────────┘         │
         │                                                   │
         └───────────────────────────────────────────────────┘
```

## 调用链详解

### 1. 入口：外部调用 → `strategy` 模块

**comm/server.py** - WebSocket 服务端：

```python
# 第 34 行
from bayes_poker.strategy.opponent_range.predictor import OpponentRangePredictor

# 第 73 行 - 初始化时设置
range_predictor: "OpponentRangePredictor | None" = None

# 第 108 行
def set_range_predictor(self, predictor: "OpponentRangePredictor") -> None:
    self.range_predictor = predictor

# 第 481 行 - 核心调用
predictor.update_range_on_action(player, action, table_state, action_prefix)
```

**comm/session.py** - 会话管理：

```python
# 第 17 行
from bayes_poker.strategy.opponent_range.predictor import OpponentRangePredictor

# 第 63 行
range_predictor: "OpponentRangePredictor | None" = None
```

### 2. `OpponentRangePredictor` 核心方法调用链

```
update_range_on_action(player, action, table_state, action_prefix)
│
├──► _update_preflop_range()  [翻前]
│    │
│    ├──► _handle_preflop_first_action()
│    │    │
│    │    ├──► _try_update_with_shared_preflop_engine()
│    │    │    │   # 核心：使用 preflop_engine 更新范围
│    │    │    │
│    │    │    ├──► build_preflop_decision_state()     # preflop_engine.state
│    │    │    ├──► PreflopNodeMapper.map_state()      # preflop_engine.mapper
│    │    │    ├──► RangeEngine.observe_action()       # preflop_engine.range_engine
│    │    │    └──► PolicyCalibrator (校准)
│    │    │
│    │    ├──► _handle_first_limp()
│    │    ├──► _handle_follow_limp()
│    │    ├──► _handle_rfi_no_limper() / _handle_rfi_have_limper()
│    │    │    │   # 使用 preflop_strategy 查询策略节点
│    │    │    │
│    │    │    ├──► _query_preflop_decision_node()
│    │    │    │    └──► preflop_strategy.query(stack_bb, history)
│    │    │    │
│    │    │    └──► _build_ev_ranked_rfi_range()       # 按 EV 排序裁剪范围
│    │    │
│    │    └──► _apply_preflop_action_scale()           # 默认使用缩放因子
│    │
│    └──► _handle_preflop_non_first_action()
│
└──► _update_postflop_range()  [翻后 - 暂未实现]
```

### 3. preflop_engine 依赖链

`OpponentRangePredictor` 依赖以下 preflop_engine 组件：

| 组件 | 文件 | 用途 |
|------|------|------|
| `RangeEngine` | `range_engine.py` | 贝叶斯更新后验范围 |
| `PreflopNodeMapper` | `mapper.py` | 策略节点映射 |
| `PolicyCalibrator` | `policy_calibrator.py` | 策略频率校准 |
| `PlayerTendencyProfile` | `tendency.py` | 玩家倾向画像 |
| `build_preflop_decision_state` | `state.py` | 构建决策状态 |

### 4. preflop_parse 依赖链

`OpponentRangePredictor` 使用：

| 组件 | 用途 |
|------|------|
| `PreflopStrategy` | 策略数据结构（内存） |
| `preflop_strategy.query()` | 查询匹配节点 |
| `StrategyNode` | 策略节点（含频率/EV） |

### 5. range 模块依赖

| 组件 | 维度 | 用途 |
|------|------|------|
| `PreflopRange` | 169 | 翻前范围 |
| `PostflopRange` | 1326 | 翻后范围 |
| `RANGE_169_ORDER` | - | 169 维手牌顺序 |

## 数据流总结

```
1. comm 层创建 OpponentRangePredictor
      ↓
2. 每次对手行动时调用 update_range_on_action()
      ↓
3. 翻前分支:
   ├─ 优先尝试 shared preflop_engine (RangeEngine + PolicyCalibrator)
   │   → 从 sqlite 策略库获取节点
   │   → 校准后贝叶斯更新
   │
   └─ 回退: 使用 preflop_strategy (内存) 查询 + 统计频率
      → 匹配策略节点
      → 按 EV 排序构建范围
```

## 关键重构点

重构后的 `opponent_range` 现在：

1. **双重策略源**：
   - `preflop_strategy_repository` (SQLite) + `preflop_strategy` (内存)
   - 优先使用 SQLite（`_try_update_with_shared_preflop_engine`）
   - 备选使用内存策略

2. **共享 preflop_engine**：
   - `RangeEngine` - 贝叶斯后验更新
   - `PolicyCalibrator` - 根据玩家统计校准策略频率

3. **预测器工厂**：
   ```python
   create_opponent_range_predictor(
       preflop_strategy=None,              # 内存策略（可选）
       preflop_strategy_repository=None,   # SQLite 仓库（可选）
       preflop_strategy_source_id=None,    # 策略源 ID
       stats_repo=None,                    # 玩家统计仓库
       table_type=TableType.SIX_MAX,
   )
   ```

## 相关文档

- [preflop_engine/predictorpredictor_flow.md](./preflop_engine/predictorpredictor_flow.md) - 预测器流程详述
- [各子模块 AGENTS.md](./preflop_engine/predictorAGENTS.md) - 子模块详细说明
