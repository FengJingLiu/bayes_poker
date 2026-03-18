# Hero 决策链路完整文档

> 本文档面向 AI Agent, 完整描述 `bayes_poker` 项目中 **hero 决策** 的端到端数据流、存储格式、算法细节,
> 以便回答核心问题: **"hero 如何根据已行动对手的后验范围和加注尺度来调整自己的策略?"**

---

## 目录

1. [系统总览](#1-系统总览)
2. [入口与调用链](#2-入口与调用链)
3. [数据模型层](#3-数据模型层)
4. [存储层: Player Stats 数据库](#4-存储层-player-stats-数据库)
5. [存储层: Preflop Strategy 数据库](#5-存储层-preflop-strategy-数据库)
6. [Step 1 -- 构建决策上下文 (Context Builder)](#6-step-1----构建决策上下文-context-builder)
7. [Step 2 -- 节点映射 (Node Mapper)](#7-step-2----节点映射-node-mapper)
8. [Step 3 -- GTO 先验策略 (GTO Prior Builder)](#8-step-3----gto-先验策略-gto-prior-builder)
9. [Step 4 -- 对手管线: 后验范围计算 (Opponent Pipeline)](#9-step-4----对手管线-后验范围计算-opponent-pipeline)
10. [Step 5 -- Hero 决策 (Hero Resolver)](#10-step-5----hero-决策-hero-resolver)
11. [范围模型 (Range Model)](#11-范围模型-range-model)
12. [当前局限与待解决问题](#12-当前局限与待解决问题)
13. [附录: 关键枚举与常量](#13-附录-关键枚举与常量)

---

## 1. 系统总览

### 架构一句话

```
ObservedTableState -> StrategyEngine -> (对手后验范围, hero GTO 策略) -> RecommendationDecision
```

### 核心模块路径

```
src/bayes_poker/
├── strategy/strategy_engine/   # v2 主链路 (本文档焦点)
│   ├── engine.py               # StrategyEngine 门面
│   ├── handler.py              # StrategyHandler 工厂
│   ├── context_builder.py      # 构建 PlayerNodeContext
│   ├── node_mapper.py          # solver 节点匹配
│   ├── gto_policy.py           # GTO 先验策略构建
│   ├── opponent_pipeline.py    # 对手后验范围管线
│   ├── hero_resolver.py        # hero 最终决策
│   ├── calibrator.py           # 概率校准
│   ├── posterior.py            # 贝叶斯后验更新
│   ├── stats_adapter.py        # 玩家统计适配
│   ├── repository_adapter.py   # 策略仓储适配
│   ├── session_context.py      # 会话状态管理
│   ├── core_types.py           # 核心数据类型
│   └── contracts.py            # 返回值协议
├── strategy/range/             # 169/1326 维范围模型
├── storage/                    # SQLite 仓储
├── player_metrics/             # 玩家统计模型 (Rust 反序列化)
├── domain/                     # 领域模型
└── table/observed_state.py     # 牌桌观察状态
```

### 硬约束 (v2)

| 约束 | 说明 |
|---|---|
| 仅 6-max | 不支持 HU / 9-max |
| 仅 Preflop | 不支持 Postflop |
| 支持首次行动 + 部分 reentry | 已支持 OPEN / CALL_VS_OPEN / LIMP, 以及 `Hero open -> facing 3-bet` 的再次决策 |
| 仍未支持的边界 | `limp-after-raise`, postflop, HU, 9-max, 完整 hero posterior |
| 运行时禁止 import | `preflop_engine`, `runtime`, `preflop_parse.query` 不可在新链路中使用 |

---

## 2. 入口与调用链

### 完整调用链 (伪代码)

```python
# ━━━ 入口 ━━━
StrategyEngine.__call__(session_id, observed_state: ObservedTableState)
│
├── Guard: actor_seat == hero_seat?  (不是 hero 行动 -> NoResponseDecision)
│
├── ━━━ 对手管线: 逐个处理已行动对手 ━━━
│   OpponentPipeline.process_hero_snapshot(session_ctx, state)
│   │
│   │  # 从 ObservedTableState 派生当前决策点视图
│   │  state.get_preflop_prefix_before_current_turn()
│   │  state.get_live_opponent_last_action_indices_before_current_turn()
│   │
│   │  for each acted_live_opponent in latest_live_actions:
│   │  │
│   │  ├── [A] build_player_node_context(state, opponent) -> PlayerNodeContext
│   │  │       # 包含: position, stack, history, player_name, action 等
│   │  │
│   │  ├── [B] StrategyNodeMapper.map_node_context(ctx) -> MappedNodeContext
│   │  │       # 在 solver_nodes 中找最近匹配节点 (距离评分)
│   │  │
│   │  ├── [C] GtoPriorBuilder.build_policy(mapped_ctx) -> GtoPriorPolicy
│   │  │       # 从 solver_actions 读取策略, 构建 169 维先验范围
│   │  │       # 每个 GTO 动作 -> GtoPriorAction(action_code, frequency, range_169, ev_169)
│   │  │
│   │  ├── [D] _select_matching_prior_action(policy, real_action) -> GtoPriorAction
│   │  │       # 按 action_type 匹配, 同类型多个则按 bet_size 最近匹配
│   │  │
│   │  ├── [E] PlayerNodeStatsAdapter.load(player_name, node_ctx) -> PlayerNodeStats
│   │  │       # 从 player_stats DB 读取 -> Beta/Dirichlet 平滑 -> fold/call/raise 概率
│   │  │
│   │  └── [F] _adjust_belief_with_stats_and_ev(prior_policy, matched_action, stats)
│   │          -> PreflopRange (对手后验范围)
│   │          # 核心: 用 stats 目标频率 + EV 排序重新分配 belief
│   │
│   └── 写入 session_context: opponent_ranges[seat] = posterior_range
│
├── ━━━ Hero 决策 ━━━
│   HeroGtoResolver.resolve(session_ctx, state)
│   │
│   ├── build_player_node_context(state, hero) -> PlayerNodeContext
│   ├── StrategyNodeMapper.map_node_context(ctx) -> MappedNodeContext
│   ├── GtoPriorBuilder.build_policy(mapped_ctx) -> GtoPriorPolicy
│   ├── 构建动作分布 (action_distribution)
│   ├── 采样动作 (基于 GTO 频率)
│   └── return RecommendationDecision
│
└── 返回 Decision 给调用方
```

---

## 3. 数据模型层

### 3.1 ObservedTableState (输入)

文件: `table/observed_state.py`

牌桌的**实时观察快照**, 是整个决策链路的唯一输入:

```python
@dataclass
class ObservedTableState:
    table_id: str                    # 牌桌唯一 ID
    hand_id: str                     # 手牌 ID
    table_type: TableType            # 桌型 (CASH_6MAX 等)
    street: Street                   # 当前街 (PREFLOP / FLOP / TURN / RIVER)
    hero_seat: int                   # hero 座位号 (0-based)
    actor_seat: int                  # 当前行动者座位号
    players: list[Player]            # 所有玩家信息
    community_cards: list[str]       # 公共牌
    pot_total_cents: int             # 底池总额 (分)
    action_history: list[PlayerAction]  # 已发生的动作序列

    # Player 结构
    @dataclass
    class Player:
        name: str
        seat: int                    # 0-based
        stack_cents: int             # 当前筹码 (分)
        hole_cards: list[str] | None # hero 可见自己的底牌
        is_active: bool
        position: Position           # SB/BB/UTG/MP/HJ/CO/BTN

    # PlayerAction 结构
    @dataclass
    class PlayerAction:
        seat: int
        action_type: ActionType      # fold/check/call/bet/raise/all_in
        amount_cents: int            # 动作金额 (分)
        street: Street
```

当前运行时不会再额外构造一个独立的 preflop slice 对象。
所有“当前决策点之前”的切片都由 `ObservedTableState` 即时推导, 典型接口包括:

- `get_preflop_prefix_before_current_turn()`
- `get_preflop_prefix_before_action_index(action_index)`
- `get_preflop_previous_action_for_seat(seat)`
- `get_preflop_history_tokens_before_current_turn(include_size: bool = False)`
- `get_live_opponent_last_action_indices_before_current_turn()`
- `get_active_player_count_before_current_turn()`

其中 `previous_action=FOLD` 在 `PreFlopParams` 索引语义里表示“该玩家此前尚未行动”, 不是“真实上一动作就是 fold”。

### 3.2 PlayerNodeContext (内部上下文)

文件: `strategy_engine/core_types.py`

由 `context_builder.py` 从 `ObservedTableState` 构建, 是 **solver 节点查询的标准化输入**:

```python
@dataclass
class PlayerNodeContext:
    player_name: str
    position: Position               # 玩家位置 (枚举)
    stack_bb: float                   # 筹码 (大盲数)
    history_actions: str             # 标准化动作序列 (如 "F-F-R2.5")
    history_full: str                # 完整历史字符串
    action_type: ActionType          # 该玩家的实际动作类型
    bet_size_bb: float               # 该玩家的实际下注尺度 (大盲数)
    pot_size_bb: float               # 行动前底池 (大盲数)
    raise_time: int                  # 加注次数 (0=open, 1=3bet, 2=4bet...)
    call_count: int                  # 溜入人数
    limp_count: int                  # limp 人数
    aggressor_position: Position | None  # 最后加注者位置
    is_in_position: bool             # 是否有位置优势
```

### 3.3 核心类型枚举

```python
# domain/poker.py
class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"

class Street(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"

# player_metrics/enums.py
class Position(IntEnum):
    SB = 0; BB = 1; UTG = 2; MP = 3; HJ = 4; CO = 5; BTN = 6
    # 注意: domain/table.py 也有一个 Position 枚举 (str 类型), 用于业务层
    # player_metrics 层用 IntEnum, 用于数据库索引

class TableType(IntEnum):
    CASH_6MAX = 0  # 当前唯一支持类型

class PreflopPotType(IntEnum):
    OPEN = 0          # 首次加注
    CALL_VS_OPEN = 1  # 对 open 的跟注
    LIMP = 2          # limp
    # 3-bet+ 等暂不支持
```

### 3.4 Decision 返回值

文件: `strategy_engine/contracts.py`

```python
@dataclass
class RecommendationDecision:
    """hero 推荐决策结果."""
    action: ActionType               # 推荐动作
    amount_bb: float                 # 推荐金额 (大盲数)
    action_evs: dict[str, float]     # 各动作的 EV
    action_distribution: dict[str, float]  # 各动作的频率分布
    range_breakdown: dict[str, PreflopRange] | None  # 各动作对应的范围

@dataclass
class NoResponseDecision:
    """非 hero 行动, 无需决策."""
    reason: str

@dataclass
class UnsupportedScenarioDecision:
    """不支持的场景 (如 postflop)."""
    reason: str

@dataclass
class SafeFallbackDecision:
    """安全降级 (查询失败等)."""
    reason: str
    fallback_action: ActionType
```

---

## 4. 存储层: Player Stats 数据库

### 4.1 SQLite 表结构

文件: `storage/player_stats_repository.py`

```sql
CREATE TABLE IF NOT EXISTS player_stats (
    player_name TEXT NOT NULL,
    table_type  INTEGER NOT NULL,       -- TableType 枚举值 (0=CASH_6MAX)
    stats_binary BLOB NOT NULL,         -- Rust 序列化的二进制数据
    PRIMARY KEY (player_name, table_type)
);
```

### 4.2 反序列化后的数据结构

文件: `player_metrics/models.py`

```python
@dataclass
class PlayerStats:
    vpip: float                          # 自愿投入底池比例
    preflop_stats: list[ActionStats]     # 长度 = 54 (6-max), 按 PreFlopParams.to_index() 索引
    postflop_stats: list[ActionStats]    # postflop 统计 (当前不使用)

@dataclass
class ActionStats:
    """单个决策节点的统计计数."""
    bet_0_40: int       # 下注 0-40% pot 的次数
    bet_40_80: int      # 下注 40-80% pot 的次数
    bet_80_120: int     # 下注 80-120% pot 的次数
    bet_over_120: int   # 下注 >120% pot 的次数
    raise_samples: int  # 总加注样本数 (= bet_0_40 + bet_40_80 + bet_80_120 + bet_over_120)
    check_call_samples: int  # check/call 样本数
    fold_samples: int        # fold 样本数

    # 派生概率:
    # total = raise_samples + check_call_samples + fold_samples
    # p_raise = raise_samples / total
    # p_call  = check_call_samples / total
    # p_fold  = fold_samples / total
    #
    # 下注尺度分布 (仅在 raise_samples > 0 时有意义):
    # p_bet_small  = bet_0_40 / raise_samples       # 小注
    # p_bet_medium = bet_40_80 / raise_samples      # 中注
    # p_bet_large  = bet_80_120 / raise_samples     # 大注
    # p_bet_xlarge = bet_over_120 / raise_samples   # 超大注
```

### 4.3 PreFlopParams 索引映射 (54 桶)

文件: `player_metrics/params.py`

核心方法 `PreFlopParams.to_index()` 将 (position, pot_type, num_raises, num_callers, previous_action) 映射为 0-53 的索引:

```python
@dataclass
class PreFlopParams:
    table_type: TableType
    position: Position           # SB=0 .. BTN=5 (6个位置, 但 SB 和 BTN 共享索引逻辑)
    pot_type: PreflopPotType     # OPEN / CALL_VS_OPEN / LIMP
    num_raises: int              # 加注次数
    num_callers: int             # 跟注人数
    previous_action: ActionType  # 之前的动作类型

    def to_index(self) -> int:
        """
        6-max 编码规则:
        ┌─────────────────────────────────────────────────┐
        │ Index 0-29: previous_action == FOLD (首次行动)   │
        │   6 positions x 5 spots                         │
        │   spot = _get_spot_index(num_raises, num_callers)│
        │   index = position * 5 + spot                   │
        ├─────────────────────────────────────────────────┤
        │ Index 30-53: Re-action 桶                       │
        │   previous_action in {CHECK/CALL, BET/RAISE}    │
        │   更复杂的映射, 基于 (position, callers, raises) │
        └─────────────────────────────────────────────────┘
        """
```

**spot 计算逻辑 (`_get_spot_index`):**

| num_raises | num_callers | spot |
|---|---|---|
| 0 | 0 | 0 (= limped/unopened) |
| 0 | 1 | 1 |
| 0 | 2+ | 2 |
| 1 | 0 | 3 (= facing open) |
| 1 | 1+ | 4 (= facing open + callers) |

### 4.4 Pool 平滑 (贝叶斯先验)

文件: `storage/player_stats_repository.py` -- `_smooth_action_stats()`

当玩家某节点样本量不足时, 用 **Beta/Dirichlet** 先验平滑:

```python
def _smooth_action_stats(
    self,
    raw: ActionStats,
    action_space: str,       # "binary" 或 "ternary"
    prior_strength: float = 10.0,  # 先验等效样本数
) -> PlayerNodeStats:
    """
    平滑逻辑:
    - binary (只有 fold/call, 无 raise 选项):
      Beta 平滑 -> p_fold, p_call = 1 - p_fold, p_raise = 0
    - ternary (fold/call/raise 均可):
      Dirichlet 平滑 -> (p_fold, p_call, p_raise) 三元组

    公式 (Dirichlet):
      alpha_i = prior_strength * pool_avg_i + observed_count_i
      p_i = alpha_i / sum(alpha_j)

    其中 pool_avg 是全局平均概率 (硬编码或从大样本估计).
    """
```

**action_space 分类逻辑:**

| 场景 | action_space |
|---|---|
| BB facing open (无人 limp) | ternary (可 fold/call/raise) |
| SB facing open | ternary |
| 首次行动 open (limpers=0) | binary (open 或 fold, 无 call) |
| 其他首次行动 | 按位置和场景判断 |

### 4.5 PlayerNodeStats (平滑后的输出)

文件: `strategy_engine/stats_adapter.py`

```python
@dataclass
class PlayerNodeStats:
    fold_probability: float      # 平滑后的 fold 概率
    call_probability: float      # 平滑后的 call 概率
    raise_probability: float     # 平滑后的 raise 概率
    bet_size_distribution: dict[str, float] | None  # 下注尺度分布 (4 档)
    sample_count: int            # 原始总样本数
    is_smoothed: bool            # 是否经过平滑

    # bet_size_distribution 示例:
    # {"0_40": 0.25, "40_80": 0.35, "80_120": 0.30, "over_120": 0.10}
```

---

## 5. 存储层: Preflop Strategy 数据库

### 5.1 SQLite 表结构

文件: `storage/preflop_strategy_repository.py`

#### strategy_sources 表 (策略来源)

```sql
CREATE TABLE strategy_sources (
    source_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name   TEXT NOT NULL,          -- 策略名称 (如 "Cash6m50zSimple25Open_SimpleIP")
    source_dir      TEXT NOT NULL,          -- 原始文件目录路径
    format_version  TEXT NOT NULL DEFAULT '1.0',
    imported_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### solver_nodes 表 (solver 决策节点)

```sql
CREATE TABLE solver_nodes (
    node_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER NOT NULL REFERENCES strategy_sources(source_id),
    stack_bb            REAL NOT NULL,          -- 有效筹码 (大盲数)
    history_full        TEXT NOT NULL,          -- 完整历史 (如 "UTG:F-MP:F-HJ:F-CO:R2.5")
    history_actions     TEXT NOT NULL,          -- 仅动作部分 (如 "F-F-F-R2.5")
    actor_position      TEXT NOT NULL,          -- 行动者位置 (如 "BTN")
    aggressor_position  TEXT,                   -- 最后加注者位置
    call_count          INTEGER NOT NULL DEFAULT 0,
    limp_count          INTEGER NOT NULL DEFAULT 0,
    raise_time          INTEGER NOT NULL DEFAULT 0,   -- 加注次数 (0=open 机会)
    pot_size            REAL NOT NULL DEFAULT 1.5,     -- 行动前底池 (大盲数)
    raise_size_bb       REAL,                          -- 面对的加注尺度
    is_in_position      INTEGER NOT NULL DEFAULT 0     -- 0/1 布尔
);

-- 核心索引: 用于节点匹配查询
CREATE INDEX idx_nodes_match ON solver_nodes(
    source_id, actor_position, raise_time, call_count, limp_count, stack_bb
);
```

#### solver_actions 表 (节点下的可选动作)

```sql
CREATE TABLE solver_actions (
    action_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id         INTEGER NOT NULL REFERENCES solver_nodes(node_id),
    order_index     INTEGER NOT NULL,           -- 动作排序 (0-based)
    action_code     TEXT NOT NULL,               -- 编码 (如 "R2.5", "C", "F")
    action_type     TEXT NOT NULL,               -- "fold" / "call" / "raise" / "all_in"
    bet_size_bb     REAL,                        -- 下注大小 (大盲数), fold/call 为 NULL
    is_all_in       INTEGER NOT NULL DEFAULT 0,  -- 是否全下
    total_frequency REAL NOT NULL,               -- 该动作的总频率 (0.0-1.0)
    next_position   TEXT,                        -- 下一个行动者位置
    strategy_blob   BLOB,                        -- 169 维频率向量 (double[], 8字节x169=1352字节)
    ev_blob         BLOB,                        -- 169 维 EV 向量 (double[], 同上)
    total_ev        REAL,                        -- 该动作加权平均 EV
    total_combos    REAL                         -- 该动作的总组合数
);

CREATE INDEX idx_actions_node ON solver_actions(node_id);
```

### 5.2 strategy_blob / ev_blob 格式

```python
# 每个 blob 是 169 个 float64 (little-endian) 的二进制序列
# 索引顺序: RANGE_169_ORDER (GTOWizard 标准顺序)
# 见 strategy/range/mappings.py

import struct
strategy_values: list[float] = list(struct.unpack('<169d', strategy_blob))
# strategy_values[i] = 手牌 RANGE_169_ORDER[i] 执行该动作的频率

ev_values: list[float] = list(struct.unpack('<169d', ev_blob))
# ev_values[i] = 手牌 RANGE_169_ORDER[i] 执行该动作的 EV (大盲数)
```

### 5.3 节点查询流程

```python
# StrategyRepositoryAdapter.find_candidates(ctx: PlayerNodeContext)
# -> list[StrategyNodeCandidate]

# 查询条件 (SQL WHERE):
#   source_id = ?
#   actor_position = ctx.position
#   raise_time = ctx.raise_time
#   call_count = ctx.call_count
#   limp_count = ctx.limp_count
#   stack_bb BETWEEN ctx.stack_bb * 0.8 AND ctx.stack_bb * 1.2  (+-20% 容差)
#
# 如果完全匹配 (history_actions == ctx.history_actions) -> 直接返回
# 否则 -> 按距离评分排序, 取最近节点
```

---

## 6. Step 1 -- 构建决策上下文 (Context Builder)

文件: `strategy_engine/context_builder.py`

```python
def build_player_node_context(
    state: ObservedTableState,
    target_seat: int,          # 要构建上下文的玩家座位
) -> PlayerNodeContext:
    """
    从 ObservedTableState 提取目标玩家的标准化上下文.

    处理逻辑:
    1. 从 action_history 中提取 target_seat 之前的所有动作
    2. 标准化为 history_actions 字符串 (如 "F-F-R2.5")
    3. 计算 raise_time, call_count, limp_count
    4. 确定 aggressor_position
    5. 计算 pot_size_bb (行动前底池)
    6. 确定 is_in_position (相对于 aggressor)
    7. 金额从 cents 转换为 bb
    """
```

**history_actions 编码规则:**

| 动作 | 编码 | 示例 |
|---|---|---|
| Fold | `F` | `F` |
| Call (vs raise) | `C` | `C` |
| Limp (call BB preflop, no raise) | `L` | `L` |
| Raise/Bet/All-in | `R{size_bb}` | `R2.5`, `R6.0`, `R50.0` |

完整示例: `"F-F-R2.5-F-C"` = UTG fold, MP fold, HJ raise 2.5bb, CO fold, BTN call

---

## 7. Step 2 -- 节点映射 (Node Mapper)

文件: `strategy_engine/node_mapper.py`

```python
class StrategyNodeMapper:
    def map_node_context(
        self, ctx: PlayerNodeContext
    ) -> MappedNodeContext | None:
        """
        在 solver 数据库中找到最匹配 ctx 的节点.

        匹配策略:
        1. 精确匹配: history_actions 完全一致 -> 直接采用
        2. 模糊匹配: 按距离评分, 取最小距离的候选节点
        """
```

### 距离评分公式

```python
def _compute_distance(ctx: PlayerNodeContext, candidate: StrategyNodeCandidate) -> float:
    """
    多维度加权距离:
    - stack_diff: |ctx.stack_bb - cand.stack_bb| / ctx.stack_bb  (权重高)
    - pot_diff: |ctx.pot_size_bb - cand.pot_size| / ctx.pot_size_bb
    - raise_size_diff: |ctx.bet_size_bb - cand.raise_size_bb| (如果有)
    - position_match: 位置是否一致 (布尔)
    - history_similarity: 动作序列相似度
    """
```

### MappedNodeContext

```python
@dataclass
class MappedNodeContext:
    player_ctx: PlayerNodeContext      # 原始上下文
    node_id: int                       # 匹配的 solver 节点 ID
    node_candidate: StrategyNodeCandidate  # 匹配节点信息
    distance: float                    # 匹配距离 (0 = 精确匹配)
    is_exact_match: bool               # 是否精确匹配
```

---

## 8. Step 3 -- GTO 先验策略 (GTO Prior Builder)

文件: `strategy_engine/gto_policy.py`

```python
class GtoPriorBuilder:
    def build_policy(
        self, mapped_ctx: MappedNodeContext
    ) -> GtoPriorPolicy:
        """
        从匹配的 solver 节点读取策略, 构建 GTO 先验.

        流程:
        1. 查询 solver_actions WHERE node_id = mapped_ctx.node_id
        2. 对每个 action:
           - 解码 strategy_blob -> 169 维频率向量
           - 解码 ev_blob -> 169 维 EV 向量
           - 构建 PreflopRange (strategy=频率向量, evs=EV向量)
           - 包装为 GtoPriorAction
        3. 返回 GtoPriorPolicy
        """
```

### GtoPriorAction

```python
@dataclass
class GtoPriorAction:
    action_code: str           # "R2.5", "C", "F" 等
    action_type: ActionType    # fold / call / raise / all_in
    bet_size_bb: float | None  # 下注尺度 (bb)
    frequency: float           # 总频率 (0-1)
    belief_range: PreflopRange # 169 维: strategy[i] = 手牌 i 执行此动作的频率
    ev_range: PreflopRange     # 169 维: ev[i] = 手牌 i 执行此动作的 EV
```

### GtoPriorPolicy

```python
@dataclass
class GtoPriorPolicy:
    node_id: int
    actions: list[GtoPriorAction]  # 所有可选动作 (通常 2-4 个)
    source_range: PreflopRange     # 到达此节点的总范围 (所有动作 belief 之和)

    # 示例: CO open 节点可能有:
    # actions = [
    #   GtoPriorAction("F", fold, None, 0.42, fold_range, fold_ev),
    #   GtoPriorAction("R2.5", raise, 2.5, 0.48, raise_range, raise_ev),
    #   GtoPriorAction("R6.0", raise, 6.0, 0.10, allin_range, allin_ev),
    # ]
```

---

## 9. Step 4 -- 对手管线: 后验范围计算 (Opponent Pipeline)

文件: `strategy_engine/opponent_pipeline.py`

这是**最核心的模块**, 将 GTO 先验 + 玩家统计 -> 对手后验范围.

### 9.1 总体流程

```python
class OpponentPipeline:
    def process_hero_snapshot(
        self,
        session_ctx: StrategySessionContext,
        state: ObservedTableState,
    ) -> None:
        """
        处理 hero 行动时的快照, 计算所有已行动对手的后验范围.

        结果写入 session_ctx.opponent_ranges[seat] = PreflopRange
        """
        latest_live_actions = (
            state.get_live_opponent_last_action_indices_before_current_turn()
        )

        for seat, action_index in latest_live_actions:
            decision_prefix = state.get_preflop_prefix_before_action_index(action_index)
            observed_action = state.action_history[action_index]
            # [A-F] 步骤见第 2 节调用链
            posterior_range = self._process_single_opponent(
                session_ctx, state, observed_action, decision_prefix
            )
            session_ctx.set_opponent_range(seat, posterior_range)
```

### 9.2 当前决策点视图

- `OpponentPipeline` 不再把“第一次动作”当作唯一事实来源。
- 当前版本只对 **当前决策点之前仍存活且已行动** 的对手保留 posterior。
- 若某对手在当前快照里已经不再 live, 其旧 posterior 会从 `session_context` 中清理。
- 多次行动的对手以 **最近一次动作** 作为 posterior 建模入口, 但对应的 `decision_prefix` 会保留该动作之前的完整翻前前缀。

### 9.3 `_select_matching_prior_action`

```python
def _select_matching_prior_action(
    self,
    policy: GtoPriorPolicy,
    real_action: ObservedAction,
) -> GtoPriorAction | None:
    """
    在 GTO 策略中找到与对手真实动作最匹配的先验动作.

    匹配逻辑:
    1. 按 action_type 筛选 (fold -> fold, call -> call, raise -> raise)
    2. 同类型有多个 (如多种 raise size): 按 bet_size_bb 最接近的匹配
    3. 无匹配 -> 返回 None (触发降级处理)
    """
```

### 9.4 `_adjust_belief_with_stats_and_ev` (核心算法)

```python
def _adjust_belief_with_stats_and_ev(
    self,
    prior_policy: GtoPriorPolicy,
    matched_action: GtoPriorAction,
    stats: PlayerNodeStats,
) -> PreflopRange:
    """
    用玩家真实统计调整 GTO 先验, 生成后验范围.

    核心思想:
    - GTO 先验给出每手牌的动作频率分布
    - 玩家统计给出 该玩家 的实际 fold/call/raise 频率
    - 如果玩家的 raise 频率 > GTO, 说明他 raise 的范围更宽
    - 反之说明更紧

    算法步骤:
    1. 获取 GTO 先验中该动作的总频率 (gto_freq)
    2. 获取 stats 中该动作的实际频率 (stats_freq)
    3. 计算调整比例: adjustment_ratio = stats_freq / gto_freq
    4. 对 169 维范围的每一手牌:
       a. 新频率 = min(原频率 * adjustment_ratio, 1.0)
       b. 但这可能导致总概率溢出, 需要重新归一化
    5. EV 引导重分配:
       - 如果需要 **扩大** 范围 (stats_freq > gto_freq):
         按 EV 从高到低排序, 优先加入 EV 高的手牌
       - 如果需要 **缩小** 范围 (stats_freq < gto_freq):
         按 EV 从低到高排序, 优先移除 EV 低的手牌
    6. 返回调整后的 PreflopRange (后验范围)
    """
```

### 9.5 校准器 (Calibrator)

文件: `strategy_engine/calibrator.py`

```python
def calibrate_binary_policy(
    prior_freq: float,
    stats_freq: float,
    belief_range: PreflopRange,
    ev_range: PreflopRange,
) -> PreflopRange:
    """二元决策的概率校准 (如 open/fold)."""

def calibrate_multinomial_policy(
    prior_policy: GtoPriorPolicy,
    stats: PlayerNodeStats,
    target_action: GtoPriorAction,
) -> PreflopRange:
    """多元决策的概率校准 (如 fold/call/raise)."""

def redistribute_aggressive_mass(
    range_169: PreflopRange,
    ev_range: PreflopRange,
    target_total: float,
    current_total: float,
) -> PreflopRange:
    """
    当需要调整总频率时, 按 EV 排序重新分配概率质量.
    - 扩大: EV 高的手牌优先获得额外频率
    - 缩小: EV 低的手牌优先被削减
    """
```

### 9.6 贝叶斯后验更新

文件: `strategy_engine/posterior.py`

```python
def update_posterior(
    prior: PreflopRange,
    likelihood: PreflopRange,
) -> PreflopRange:
    """
    标准贝叶斯更新: posterior = prior x likelihood (归一化)

    对 169 维的每一手牌:
      posterior[i] = prior[i] * likelihood[i]

    然后归一化使 sum(posterior) = sum(prior) (保持总组合数不变)
    """
```

---

## 10. Step 5 -- Hero 决策 (Hero Resolver)

文件: `strategy_engine/hero_resolver.py`

```python
class HeroGtoResolver:
    def resolve(
        self,
        session_ctx: StrategySessionContext,
        state: ObservedTableState,
    ) -> RecommendationDecision | SafeFallbackDecision:
        """
        为 hero 生成最终决策推荐.

        流程:
        1. build_player_node_context(state, hero_seat)
        2. 用当前决策点之前的完整翻前前缀构建 `preferred_history_actions`
        3. StrategyNodeMapper.map_node_context(hero_ctx)
        4. GtoPriorBuilder.build_policy(mapped_ctx)
        5. 基于已行动 live opponent 的 posterior / prior 比值构建 aggression_ratio
        6. 按 aggression_ratio 调整 hero 动作频率
        7. 构建 action_distribution:
           {action_code: frequency for action in policy.actions}
        8. 计算 action_evs:
           {action_code: total_ev for action in policy.actions}
        9. 按频率采样一个动作
        10. 返回 RecommendationDecision

        !! 当前局限:
        - Hero 当前只把对手 posterior 压缩成 aggression_ratio 标量信号
        - 未直接按对手 belief_range 的逐组合信息重算 hero range
        - 未利用对手的 bet_size_distribution 进一步修正 hero 决策
        """
```

---

## 11. 范围模型 (Range Model)

文件: `strategy/range/models.py`, `strategy/range/mappings.py`

### 11.1 PreflopRange (169 维)

```python
@dataclass
class PreflopRange:
    """169 维翻前范围, 对应 169 种非等价手牌."""
    strategy: list[float]   # 长度 169, strategy[i] = 手牌 i 的频率/权重 (0.0-1.0)
    evs: list[float]        # 长度 169, evs[i] = 手牌 i 的 EV (大盲数)

    # 用途:
    # - 作为 GTO 先验: strategy[i] = 该手牌执行某动作的 GTO 频率
    # - 作为后验范围: strategy[i] = 该手牌在对手范围中的权重
    # - evs 用于 EV 引导的概率重分配
```

### 11.2 RANGE_169_ORDER (索引顺序)

```python
# strategy/range/mappings.py
RANGE_169_ORDER: list[str] = [
    "AA", "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s",
    "A4s", "A3s", "A2s",
    "AKo", "KK", "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
    "K4s", "K3s", "K2s",
    "AQo", "KQo", "QQ", "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s",
    "Q4s", "Q3s", "Q2s",
    # ... 共 169 项, GTOWizard 标准顺序
    # 对角线上 = pocket pairs (AA, KK, QQ, ...)
    # 上三角 = suited (AKs, AQs, ...)
    # 下三角 = offsuit (AKo, AQo, ...)
]
```

### 11.3 组合数映射

```python
def combos_per_hand(hand: str) -> int:
    """
    每种手牌的组合数:
    - Pocket pair (如 AA): 6 种组合
    - Suited (如 AKs): 4 种组合
    - Offsuit (如 AKo): 12 种组合
    总计: 13x6 + 78x4 + 78x12 = 1326 种组合
    """
```

### 11.4 PostflopRange (1326 维)

```python
@dataclass
class PostflopRange:
    """1326 维翻后范围, 对应所有 C(52,2)=1326 种两张牌组合."""
    strategy: list[float]   # 长度 1326
    evs: list[float]        # 长度 1326
    # 当前 v2 不使用, 预留 postflop 扩展
```

---

## 12. 当前局限与待解决问题

### 12.1 Hero 仅部分使用对手后验范围

**现状:**
- `OpponentPipeline` 已经为每个已行动对手计算了后验范围
- 后验范围存储在 `session_ctx.opponent_ranges[seat]`
- `HeroGtoResolver.resolve()` 会读取 posterior 的总频率, 与 prior 频率形成 `aggression_ratio`
- Hero 已经不再是纯查表返回, 会按 `aggression_ratio` 调整激进行为频率

**期望:**
- Hero 应该进一步根据对手的完整后验范围调整自己的策略
- 例: 如果对手的 open 范围比 GTO 宽 -> hero 可以更频繁地 3-bet
- 例: 如果对手的 open 范围比 GTO 紧 -> hero 应该减少轻的 3-bet bluff

### 12.2 未利用对手的下注尺度信息

**现状:**
- `PlayerNodeStats.bet_size_distribution` 包含 4 档下注尺度概率
- 对手的真实 `bet_size_bb` 在 `ObservedAction` 中可用
- 但后验计算中只匹配最近的 GTO size, 未按尺度差异调整范围

**期望:**
- 对手选择的特定尺度可能蕴含范围信息
- 例: 选择超大注 (>120% pot) 的对手可能极化 (超强或 bluff)
- 应将 bet_size_distribution 纳入后验更新

### 12.3 Preflop Multi-Action 仍是部分支持

- 已支持 Hero 首次行动
- 已支持 `Hero open -> facing 3-bet` 的 reentry
- 已支持在 `three_bet+` 链路中, 用当前仍存活对手的最近一次动作做 posterior
- 仍不支持 `limp-after-raise`
- 仍不支持 postflop

### 12.4 会话状态未跨手牌

- 当前每手牌独立计算
- 不做跨手牌的对手模型持续更新

---

## 13. 附录: 关键枚举与常量

### Position 映射 (6-max)

```
座位 0 -> SB (Small Blind)
座位 1 -> BB (Big Blind)
座位 2 -> UTG (Under The Gun)
座位 3 -> MP (Middle Position)
座位 4 -> HJ (Hijack)
座位 5 -> CO (Cutoff)
座位 6 -> BTN (Button)  # 实际 6-max 只有 6 人, BTN = 座位 5 或动态分配
```

注意: `player_metrics/enums.py` 中 `Position(IntEnum)` 的 BTN=6, 但 6-max 桌最多 6 人 (0-5), BTN 对应座位 5.

### action_code 编码

| 编码 | 含义 |
|---|---|
| `F` | Fold |
| `C` | Call |
| `L` | Limp |
| `K` | Check |
| `R{size}` | Raise to {size} BB |
| `A` | All-in |

### history_actions 格式

- 以 `-` 分隔各动作
- 按行动顺序排列 (从 UTG 开始)
- 示例: `"F-F-R2.5-F-C"` = UTG fold, MP fold, HJ raise 2.5bb, CO fold, BTN call

---

## 附录: 文件路径速查

| 文件 | 职责 |
|---|---|
| `strategy/strategy_engine/engine.py` | 门面入口 |
| `strategy/strategy_engine/context_builder.py` | 状态 -> 上下文 |
| `strategy/strategy_engine/node_mapper.py` | 上下文 -> solver 节点 |
| `strategy/strategy_engine/gto_policy.py` | solver 节点 -> GTO 策略 |
| `strategy/strategy_engine/opponent_pipeline.py` | GTO + stats -> 对手后验 |
| `strategy/strategy_engine/hero_resolver.py` | GTO -> hero 决策 |
| `strategy/strategy_engine/calibrator.py` | 概率校准算法 |
| `strategy/strategy_engine/posterior.py` | 贝叶斯更新 |
| `strategy/strategy_engine/stats_adapter.py` | DB -> PlayerNodeStats |
| `strategy/strategy_engine/repository_adapter.py` | DB -> StrategyNodeCandidate |
| `strategy/strategy_engine/session_context.py` | 会话状态 |
| `strategy/strategy_engine/core_types.py` | 数据类型定义 |
| `strategy/strategy_engine/contracts.py` | 返回值协议 |
| `storage/player_stats_repository.py` | 玩家统计 SQLite |
| `storage/preflop_strategy_repository.py` | Preflop 策略 SQLite |
| `player_metrics/models.py` | PlayerStats / ActionStats |
| `player_metrics/params.py` | PreFlopParams 索引 |
| `player_metrics/enums.py` | 位置 / 桌型枚举 |
| `strategy/range/models.py` | PreflopRange / PostflopRange |
| `strategy/range/mappings.py` | 169 手牌顺序与组合数 |
| `table/observed_state.py` | 牌桌观察状态 |
