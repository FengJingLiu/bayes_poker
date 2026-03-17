# poker_stats_rs — Rust 扩展 CLAUDE.md

> Crate 路径：`crates/poker_stats_rs/`
> 类型：PyO3 cdylib（Python 扩展模块）
> 职责：高性能手牌统计计算 + SQLite 持久化

---

## 构建

```bash
cd crates/poker_stats_rs

# 开发构建（Debug）
cargo build

# 生产构建（Release，用于 Python 调用）
cargo build --release

# 测试
cargo test

# 生成聚合玩家（须先有 player_stats.db）
cargo run --example aggregate_sixmax
```

生成的 `.so` 文件需在 Python 的 `sys.path` 可发现路径中，`player_metrics/rust_api.py` 会自动尝试项目根目录。

---

## 依赖

| Crate | 用途 |
|-------|------|
| `pyo3 0.22` | Python 扩展绑定 |
| `rayon 1.10` | 并行统计计算 |
| `rusqlite 0.32` (bundled) | SQLite（内嵌 sqlite3，无需系统依赖） |
| `serde + serde_json 1.0` | PHHS 文件 JSON 解析 |
| `sha2 0.10` | 手牌去重 hash |
| `toml 0.8` | 配置文件解析 |
| `walkdir 2.5` | 目录遍历 |
| `byteorder 1.5` | 二进制序列化 |
| `thiserror 2.0` | 错误类型 |

开发依赖：`tempfile 3.10`（测试用临时目录）

---

## 模块结构

| 文件 | 职责 |
|------|------|
| `lib.rs` | PyO3 模块入口，暴露 `py_*` 函数和 `PyPlayerStats`/`PyPlayerStatsFull` 类 |
| `enums.rs` | `TableType`, `Street`, `Position`, `ActionType`, `BetSizingCategory`, `PreflopPotType` |
| `hand.rs` | `Hand`（完整手牌），`Action`（单个动作） |
| `hand_hash.rs` | `compute_hand_hash(players, raw_actions) -> String`（SHA-2 去重 hash） |
| `phhs_parser.rs` | `parse_phhs_file(path)` / `load_phhs_directory(dir)` |
| `player_stats.rs` | `PlayerStats`（含 preflop/postflop 统计数组） |
| `action_stats.rs` | `ActionStats`（7 维计数：fold/call/check/bet×4/raise） |
| `preflop_params.rs` | `PreFlopParams::to_index()` → 54 桶索引 |
| `postflop_params.rs` | `PostFlopParams::to_index()` |
| `builder.rs` | `build_player_stats_parallel(hands, table_type)` → rayon 并行计算 |
| `storage.rs` | `PlayerStatsRepository`（rusqlite 读写：upsert_batch / get / load / aggregate_and_upsert） |

---

## 暴露给 Python 的 API

### 类型

```python
class PyPlayerStats:
    player_name: str
    table_type: int          # 2=HU, 6=6max
    vpip_positive: int
    vpip_total: int

class PyPlayerStatsFull(PyPlayerStats):
    preflop_stats: list[tuple[int,int,int,int,int,int,int]]  # 按桶索引
    postflop_stats: list[tuple[int,int,int,int,int,int,int]]
    # 每个 tuple: (bet_0_40, bet_40_80, bet_80_120, bet_over_120,
    #              raise_samples, check_call_samples, fold_samples)
```

### 函数

```python
# 批量处理 PHHS 文件目录 → SQLite（核心批处理接口）
poker_stats_rs.py_batch_process_phhs(
    phhs_dir: str,
    db_path: str,
    max_files_in_memory: int | None,
) -> tuple[int, int, int]   # (new_hands, distinct_players, skipped_hands)

# 内存计算统计（不持久化）
poker_stats_rs.py_build_stats(
    hands_json: list[str],
    table_type: int,
) -> list[PyPlayerStats]

# 计算并写入 SQLite
poker_stats_rs.py_build_and_save_stats(
    hands_json: list[str],
    table_type: int,
    db_path: str,
) -> int   # 写入记录数

# 从 SQLite 读取（简单视图）
poker_stats_rs.py_load_player_stats(
    db_path: str,
    player_names: list[str],
) -> list[PyPlayerStats]

# 从 SQLite 读取完整统计
poker_stats_rs.py_load_player_stats_full(
    db_path: str,
    player_names: list[str],
    table_type: int | None,
) -> list[PyPlayerStatsFull]
```

---

## 核心算法

### 手牌去重（`hand_hash.rs`）

对 `(players, raw_actions)` 拼接后 SHA-2 散列，相同内容的重复文件自动跳过。

### 并行统计构建（`builder.rs`）

使用 `rayon::par_iter()` 对所有玩家并行计算统计，无锁聚合后写入。

### 翻前参数索引（`preflop_params.rs`）

**6-Max 54 桶布局**：

- **0~29**（前 30 桶）：`previous_action == Fold` 的场景
  - 6 个位置（SB/BB/UTG/HJ/CO/BTN） × 5 个 spot
- **30~53**（后 24 桶）：存在主动行动后的场景

**押注尺度分类**（`enums.rs::BetSizingCategory`）：

| 类别 | 底池百分比 |
|------|-----------|
| Bet0To40 | < 40% |
| Bet40To80 | 40%~80% |
| Bet80To120 | 80%~120% |
| BetOver120 | > 120% |

### 聚合玩家（`storage.rs::aggregate_and_upsert`）

从所有满足条件的玩家（`vpip_total > 100`，指定桌型）聚合出一个代表性玩家 `aggregated_sixmax_100`，作为贝叶斯先验池。

---

## PHHS 文件格式

PHHS（Poker Hand History Simplified）是项目内部格式：

```toml
[hand]
players = ["Alice", "Bob", "Charlie"]
blinds_or_straddles = [50, 100, 0]
antes = [0, 0, 0]
actions = ["p1 f", "p2 cc 100", "p3 b 300"]
```

---

## SQLite Schema

```sql
CREATE TABLE player_stats (
    player_name TEXT NOT NULL,
    table_type INTEGER NOT NULL,
    vpip_positive INTEGER NOT NULL,
    vpip_total INTEGER NOT NULL,
    stats_binary BLOB NOT NULL,       -- byteorder 序列化的统计数组
    PRIMARY KEY(player_name, table_type)
);

CREATE TABLE processed_hands (
    hand_hash TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
```

---

## 重要约束

- `TableType::from_u8`：输入 `2` → HeadsUp，其余均为 SixMax
- `ActionType::from_str`：未知动作默认为 Fold（需注意）
- `Position::from_index` 仅支持 2人桌 和 6+人桌，不支持 3~5人桌
- `cdylib` 构建产物命名依赖平台：Linux 为 `libpoker_stats_rs.so`，macOS 为 `.dylib`，Windows 为 `.pyd`
