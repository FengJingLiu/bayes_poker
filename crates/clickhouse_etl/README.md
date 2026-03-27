# ClickHouse ETL 模块说明与表字段映射文档

本模块 (`clickhouse_etl`) 负责从原始手牌历史文本中解析数据，通过 ETL 衍生出多维度的统计和行动指标，并将结构化的数据集批量写入 ClickHouse。本文档详细记录了核心表结构、**底层枚举数值的精准映射**以及**每张表的典型数据分析实战用法**。

---

## 核心底层枚举值字典 (Enum Mapping)

在 ClickHouse 表中，为了查询性能和压缩率，所有的状态、位置、动作均被编译为 `UInt8` 等数值类型。数据分析时，请严格参考下述底层的映射关系建立查询条件（均由 `poker_stats_rs/src/enums.rs` 强类型约束）：

### 1. 动作类型 (`action_type: UInt8`)
| 枚举值 | 英文释义 | 中文释义 |
| :---: | :--- | :--- |
| `0` | `Fold` | 弃牌 |
| `1` | `Check` | 过牌 |
| `2` | `Call` | 跟注 |
| `3` | `Bet` | 下注 (主动建池) |
| `4` | `Raise` | 加注 / 反加 |
| `5` | `AllIn` | 全下 |

> **提示**：业务逻辑中判定“这是一次具有攻击性的动作 (Is Raise Action)”的代码等效为 `action_type IN (3, 4, 5)`。

### 2. 行动轮次/接位 (`street: UInt8`)
| 枚举值 | 英文释义 | 中文释义 |
| :---: | :--- | :--- |
| `1` | `PreFlop` | 翻牌前 |
| `2` | `Flop` | 翻牌圈 |
| `3` | `Turn` | 转牌圈 |
| `4` | `River` | 河牌圈 |

> **提示**：注意此处并非从 0 开始。

### 3. 玩家相对位置 (`position: UInt8`)
该位置是基于人数及 Button 座位动态推演出的标准化位置枚举。
| 枚举值 | 英文释义 | 中文释义 |
| :---: | :--- | :--- |
| `0` | `SmallBlind` (SB) | 小盲位 |
| `1` | `BigBlind` (BB) | 大盲位 |
| `2` | `UTG` | 枪口位 (大盲的下一位) |
| `3` | `HJ` | 劫持位 |
| `4` | `CutOff` (CO) | 关门位 (庄家前一位) |
| `5` | `Button` (BTN) | 庄家位 / 按钮位 |

### 4. 桌子/房间类型 (`table_type: UInt8`)
| 枚举值 | 英文释义 | 适用场景 |
| :---: | :--- | :--- |
| `2` | `HeadsUp` | 2人单挑局桌 |
| `6` | `SixMax` | 6人及以上满员桌 |

---

## 核心表结构及分析实战用法

### 一、`hands` (对局宏观维度表)

**1. 表格定位与用法场景**
- **定位**：最高层级的汇总表，每一行代表一局完整的牌局。
- **最佳分析用法**：
  - 统计特定时间段内的“抽水”(rake) 或 cash drop 发放数量。
  - 按桌子 (`table_name`) 聚合流量或玩家活跃情况。
  - 过滤特定的游戏盲注级别 (`small_blind_cents` 与 `big_blind_cents`)。
- **典型 SQL 分析案例**：查询各级别桌子的总局数与产生的总抽水。

**2. 字段字典表**

| 字段名 | 类型 | 含义说明 |
| :--- | :--- | :--- |
| `hand_hash` | `String` | 对局唯一哈希摘要 (本表与下级表的主键桥梁) |
| `source_name` | `String` | 原始对局文件名/标识 |
| `source_hand_id` | `String` | 唯一 Hand Number (如 `PokerStars Hand #12345`) |
| `played_at` | `Nullable(DateTime)`| UTC 时间戳 |
| `table_name` | `String` | 桌子/房间名称 |
| `seat_count` | `UInt8` | 这局开设的座位总数 |
| `table_type` | `UInt8` | `2`=HeadsUp, `6`=SixMax |
| `small_blind_cents` | `Int64` | 小盲金额(美分) |
| `big_blind_cents` | `Int64` | 大盲金额(美分) |
| `cash_drop_cents` | `Int64` | 掉落的现金奖励(美分) |
| `insurance_cost_cents`| `Int64` | 本局共计花掉的保险投入(美分) |
| `raw_text` | `String` | 原始手牌文本 |
| `normalized_text` | `String` | 去除 Run It Twice 等多余分支后的规范化文本 |

---

### 二、`player_hand_facts` (玩家单局最终统计事实表)

**1. 表格定位与用法场景**
- **定位**：每一行代表一位特定玩家在刚刚经过的一局牌中最终的“面貌”（赢钱/输钱、有没有VPIP、走到哪条街结账）。
- **最佳分析用法**：
  - 高效查出指定 User 的 VPIP%、PFR%、WTSD% 等核心牌手画像。
  - 直接计算按玩家分组的利润率 / 盈率曲线。
- **典型 SQL 分析案例**：查询玩家总体画像
```sql
-- 查询某玩家的核心入池/加注倾向以及总盈利情况
SELECT 
    player_name,
    COUNT(*) as total_hands,
    sum(is_vpip) / COUNT(*) as vpip_rate,
    sum(is_pfr) / COUNT(*) as pfr_rate,
    sum(is_3bet) / COUNT(*) as three_bet_rate,
    SUM(net_cents) / 100 as total_profit_dollars
FROM player_hand_facts
WHERE player_name = 'Hero'
GROUP BY player_name;
```

**2. 字段字典表**

| 字段名 | 类型 | 含义说明 | 数据口径/来源溯源 |
| :--- | :--- | :--- | :--- |
| `hand_hash` | `String` | 对局哈希 | 关联 `hands` 对应局 |
| `player_name` | `String` | 玩家昵称 | |
| `seat_no` | `UInt8` | 座位号 | |
| `position` | `UInt8` | 位置枚举 | `0`~`5`，依据人数推导分配 |
| `holdcard_index` | `Nullable(...)` | 底牌组合索引 | (待扩展填充字段) |
| `net_cents` | `Int64` | 净收益(美分)| `(收回的底池) - (总投入)` |
| `contributed_cents` | `Int64` | 总投入(美分)| 盲注加所有随后的实际 Bet/Call 金额 |
| `is_vpip` | `UInt8` | 是否主动入池 | 若有过 `Call/Bet/Raise/AllIn` 则置为 `1` |
| `is_pfr` | `UInt8` | 翻前是否加注 | 若有过 `Raise/AllIn` 则置为 `1` |
| `is_3bet` | `UInt8` | 是否3-Bet | 若其前有确切 `1` 次其他人的加注时进行的复加注 |
| `is_4bet` | `UInt8` | 是否4-Bet | 若其前有确切 `2` 次其他人的加注时进行的复加注 |
| `is_saw_flop` | `UInt8` | 是否看到翻牌 | 在 `PreFlop` 阶段内最后留有的存活状态 |
| `is_went_to_showdown`| `UInt8` | 是否摊牌(WTSD)| 根据文本明细中亮牌环节决议是否有该玩家名字 |
| `is_winner` | `UInt8` | 是否赢下底池 | 玩家是否最终获得底池筹码(collected) 分配 |

*(注：包括 `is_saw_turn`、`is_saw_river`、`is_winner_at_showdown` 等衍生字段与上类似逻辑提取)*

---

### 三、`player_actions` (行动序列明细事实表)

**1. 表格定位与用法场景**
- **定位**：最微观的流水表。记录局内每一张牌、每一个人的每一次行为与决策，包含做出决策时的精确赔率（Pot Odds）。
- **最佳分析用法**：
  - GTO 向数据实证挖掘，例如“探索玩家在面对 3-bet 大尺度 (sizing_pct) 下的 Fold 弃牌率”。
  - 分析在特定深度 (SPR) 下，Hero 的不同位置翻后策略。
- **典型 SQL 分析案例**：查询 UTG 开局加注后（Open Raise），面临背后 3-bet 的玩家反作用概率分布
```sql
-- 截取玩家在翻前，作为第一个 Raise（Open），面对别人后置的 3-bet 时的决策频率。
SELECT 
    action_type，-- 返回 0,2,4,5 等枚举数值，由此可知他的反应
    COUNT(*) as frequency
FROM player_actions
WHERE street = 1             -- PreFlop (街枚举为1)
  AND num_raises = 2         -- 此时他正面临2rd加注(即被3Bet)
  AND call_amount_cents > 0  -- 有差额需要应对
GROUP BY action_type;
```

**2. 字段字典表**

| 字段名 | 类型 | 含义说明 | 数据口径/来源溯源 |
| :--- | :--- | :--- | :--- |
| `hand_hash` | `String` | 对局哈希 | 关联主键 |
| `player_name` | `String` | 玩家昵称 | |
| `action_index` | `UInt32` | 动作序列号 | **核心排序键**：单局从起手开始的唯一全局递增步数序号 |
| `street` | `UInt8` | 所在街份 | `1`=PreFlop, `2`=Flop ... |
| `action_type` | `UInt8` | 动作分类 | `0`=Fold, `1`=Check ... |
| `position` | `UInt8` | 当前位置 | 在发生这一举动时这名玩家相对庄位的位置 |
| `amount_cents` | `Int64` | 本次动作引致之差| 这一举动拿去池中净增加筹码差(美分) |
| `pot_before_action_cents`| `Int64` | 动作前彩池大小| 在这个人的决定落地之前存在的底池，用来算出精准底池赔率 |
| `call_amount_cents` | `Int64` | 跟注需要的金额 | 该次出拳须要追平的最大筹码落差 |
| `num_raises` | `UInt8` | 序列前加注次数 | 用以判断是 Open 开池、或是被 3-Bet 环境下做出的决策 |
| `spr` | `Float32` | 筹码底池量比 | 动作之筹码增量除以当前彩池的值 |
| `sizing_pct` | `Nullable(...)`| 加注占底池比(%) | `amount_cents / pot_before_action_cents` (通常只有主动作非空) |

*(下半部分字段均会全等拷贝冗余 `player_hand_facts` 内的各个 `is_vpip`, `is_saw_flop` 宽表状态标签。为免写庞大的 `JOIN` ，这套 Schema 直接在每步行动流水横向展开带入了玩家这局的结果终态。)*

---

### 四、架构使用步骤速记
1. **解析入模**：通过 `GgTxtParser::parse_file()` 解析 `history.txt`；
2. **算子衍生**：传入 `EtlTransformer::transform_chunk()` 内聚合衍生出所有的统计量矩阵 (`hands`, `player_hand_facts`, `player_actions`)；
3. **入池落表**：借由 `ClickHouseLoader::load_batch()` 并行写入至远端服务端所初始化的引擎表中。

clickhouse-client --password '7q8w9e' --query "TRUNCATE TABLE IF EXISTS player_actions; TRUNCATE TABLE IF EXISTS player_hand_facts; TRUNCATE TABLE IF EXISTS hands;"

cargo run -p clickhouse_etl --bin clickhouse_etl -- ~/gg_handhistory/2025-02-13_GGHRC_NL2_SH_TGOVM255 http://localhost:8123 default default "7q8w9e"

cargo run --release -p clickhouse_etl -- data/handhistory http://localhost:8123 bayes_poker default "7q8w9e"

cd /home/autumn/bayes_poker

cargo run -p clickhouse_etl --bin export_preflop_population_dataset -- \
  --clickhouse-url http://127.0.0.1:8123 \
  --database default \
  --user default \
  --password '7q8w9e' \
  --output-dir data/population_vb \
  --table-type 6 \
  --date-from 2000-03-01 \
  --date-to 2026-03-27

会产出：

- data/population_vb/action_totals.csv
- data/population_vb/action_totals.csv.gz
- data/population_vb/exposed_combo_counts.csv
- data/population_vb/exposed_combo_counts.csv.gz
- data/population_vb/manifest.json

然后接着训练：

cd /home/autumn/bayes_poker

PYTHONPATH=src uv run python -m bayes_poker.strategy.strategy_engine.population_vb.cli \
  --strategy-db data/database/preflop_strategy.sqlite3 \
  --source-id 1 \
  --action-totals data/population_vb/action_totals.csv.gz \
  --exposed-counts data/population_vb/exposed_combo_counts.csv.gz \
  --output data/population_vb/population_artifact.npz \
  --table-type 6
