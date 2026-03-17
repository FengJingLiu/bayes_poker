# storage/ — 持久化仓库 CLAUDE.md

> 模块路径：`src/bayes_poker/storage/`
> 职责：SQLite 读写封装，分离数据访问逻辑

---

## 模块清单

| 文件 | 职责 |
|------|------|
| `player_stats_repository.py` | `PlayerStatsRepository`：玩家统计只读仓库 + 贝叶斯平滑 |
| `preflop_strategy_repository.py` | `PreflopStrategyRepository`：GTO 策略读写仓库 |

---

## PlayerStatsRepository

**只读**（写入由 Rust `poker_stats_rs` 负责）。

```python
with PlayerStatsRepository("data/database/player_stats.db") as repo:
    # 原始查询
    stats = repo.get("PlayerName", TableType.SIX_MAX)

    # 贝叶斯平滑（pool_prior_strength=20 相当于 20 个虚拟样本）
    smoothed = repo.get("PlayerName", TableType.SIX_MAX,
                        smooth_with_pool=True, pool_prior_strength=20.0)

    # 一次读取同时返回原始和平滑（性能优化）
    raw, smoothed = repo.get_with_raw("PlayerName", TableType.SIX_MAX)
```

### 贝叶斯平滑逻辑

**聚合先验玩家**：`aggregated_sixmax_100`（由 `cargo run --example aggregate_sixmax` 生成）

**平滑模型**（`player_metrics/posterior.py`）：

| 场景 | 模型 |
|------|------|
| 非盲位首动（fold/raise） | Binary（Beta 后验） |
| BB check/raise | Binary（Beta 后验） |
| 其余情况 | Multinomial（Dirichlet 后验） |

**PreFlop 桶布局**（54 桶，对应 `PreFlopParams.to_index()`）：
- `0..29`：`previous_action==Fold` 的 6 个位置 × 5 个 spot
- `30..53`：已投入/已行动后再次决策的 24 个 spot

### 手牌去重接口

```python
repo.is_hand_processed(hand_hash: str) -> bool
repo.get_processed_hand_hashes(hand_hashes: Sequence[str]) -> set[str]
repo.mark_hand_processed(hand_hash: str)
repo.mark_hands_processed(hand_hashes: Sequence[str])
```

### Schema

```sql
CREATE TABLE player_stats (
    player_name TEXT,
    table_type INTEGER,   -- 2=HU, 6=6max
    stats_binary BLOB,    -- 二进制序列化的 PlayerStats
    PRIMARY KEY(player_name, table_type)
);

CREATE TABLE processed_hands (
    hand_hash TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
```

---

## PreflopStrategyRepository

读写仓库，存储从 GTOWizard JSON 导入的翻前策略。

```python
with PreflopStrategyRepository("data/database/strategy.db") as repo:
    source_id = repo.upsert_source(
        strategy_name="gtow_6max",
        source_dir="/path/to/json",
        format_version=1,
    )
    node_id = repo.insert_node(source_id=source_id, node_record=...)
    repo.insert_actions(node_id=node_id, action_records=[...])

    # 查询候选节点（最接近 pot_size 排序）
    candidates = repo.list_candidates(
        source_ids=[1, 2, 3],
        stack_bb=100,
        actor_position=Position.BTN,
        raise_time=1,
        is_in_position=True,
        pot_size=3.5,
    )

    # 批量读取动作
    actions_map = repo.get_actions_for_nodes([node_id1, node_id2])
```

### Schema

```sql
CREATE TABLE strategy_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    source_dir TEXT NOT NULL,
    format_version INTEGER NOT NULL,
    imported_at TEXT NOT NULL,
    UNIQUE(strategy_name, source_dir)
);

CREATE TABLE solver_nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    stack_bb INTEGER NOT NULL,
    history_full TEXT NOT NULL,      -- 含动作尺度的完整历史
    history_actions TEXT NOT NULL,   -- 去量后的历史（用于模糊匹配）
    actor_position TEXT,             -- SB/BB/UTG/HJ/CO/BTN
    aggressor_position TEXT,
    call_count INTEGER NOT NULL,
    limp_count INTEGER NOT NULL,
    raise_time INTEGER NOT NULL,
    pot_size REAL NOT NULL,
    raise_size_bb REAL,
    is_in_position INTEGER,
    UNIQUE(source_id, stack_bb, history_full)
);

CREATE TABLE solver_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    action_code TEXT NOT NULL,       -- "F"/"C"/"R2.5"/"RAI" 等
    action_type TEXT NOT NULL,
    bet_size_bb REAL,
    total_frequency REAL NOT NULL,
    strategy_blob BLOB NOT NULL,     -- 169 维 float32 策略向量
    ev_blob BLOB NOT NULL,           -- 169 维 float32 EV 向量
    total_ev REAL NOT NULL,
    total_combos REAL NOT NULL
);
```

### 节点匹配策略

`list_candidates()` 精确匹配以下字段：
- `raise_time`（加注次数）
- `actor_position`（当前行动位置）
- `aggressor_position`（最后激进者位置）
- `is_in_position`（位置优势）

在满足上述约束的候选中，按 `|pot_size - target|` 最近邻排序，取最接近的节点。

---

## 重要约束

- `PlayerStatsRepository` 不提供写入接口，**所有写入通过 Rust API** 进行
- `PreflopStrategyRepository` 启用外键约束（`PRAGMA foreign_keys = ON`）
- 两个仓库均支持上下文管理器（`with ... as repo:`）
- 连接使用 `sqlite3.Row` 工厂，字段可按名访问
