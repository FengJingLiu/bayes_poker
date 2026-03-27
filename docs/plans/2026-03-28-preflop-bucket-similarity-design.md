# Preflop 分桶策略相似度与阈值合并设计

## 背景

当前 `player_actions.preflop_param_index` 已经能统计每个翻前分桶的命中量, 但仓库里还没有一个离线工具把这些桶与 solver GTO 策略连接起来, 进而判断哪些桶的策略画像足够接近, 可以合并以减少维度。

现有代码里已经具备两块基础能力:

1. [`src/bayes_poker/storage/preflop_strategy_repository.py`](/home/autumn/bayes_poker/src/bayes_poker/storage/preflop_strategy_repository.py) 可以从 sqlite 读取 `solver_nodes` 和 `solver_actions`。
2. [`src/bayes_poker/strategy/preflop_parse/parser.py`](/home/autumn/bayes_poker/src/bayes_poker/strategy/preflop_parse/parser.py) 已经有一套根据 `history_full + acting_position` 推导 preflop 行动位置、激进行动、位置关系的历史模拟逻辑。

同时, `preflop_param_index` 的权威定义不在 Python, 而在 [`crates/poker_stats_rs/src/preflop_params.rs`](/home/autumn/bayes_poker/crates/poker_stats_rs/src/preflop_params.rs)。后续任何离线分析都必须以这套 Rust 规则为准, 否则会出现“ClickHouse/统计层的桶”和“solver 相似度分析的桶”不一致的问题。

## 目标

本次新增一个离线分析脚本, 在单个 `source_id` 内完成以下工作:

1. 把 `solver_nodes` 映射回 `preflop_param_index`。
2. 为每个桶聚合出一个 `169 x 3(F/C/R)` 的 GTO 策略画像。
3. 计算桶与桶之间的策略距离。
4. 根据手动阈值或自动建议阈值, 输出可合并桶簇。
5. 每个簇使用 `hits` 最大的桶作为代表桶。

## 非目标

本轮不做以下事情:

1. 不在第一版直接接 ClickHouse 连接执行 SQL, `hits` 通过 CSV 输入。
2. 不混合多个 `source_id` 一起分析。
3. 不把 `169` 维手牌类展开到 `1326` 组合维度。
4. 不直接修改训练流程或运行时引擎逻辑。
5. 不引入新的持久化 schema。

## 关键约束

### 1. Param 规则以 Rust 为准

`preflop_param_index` 的唯一事实源是 [`preflop_params.rs`](/home/autumn/bayes_poker/crates/poker_stats_rs/src/preflop_params.rs)。Python 分析代码只能构造等价的 `PreFlopParams`, 再调用现有 Python 版本 `to_index()` 落桶, 不能自行发明新的桶编号规则。

### 2. 不能沿用当前 `gto_family_prior.py` 的粗映射

[`src/bayes_poker/strategy/strategy_engine/population_vb/gto_family_prior.py`](/home/autumn/bayes_poker/src/bayes_poker/strategy/strategy_engine/population_vb/gto_family_prior.py) 当前 `_to_param_index()` 只使用:

- `actor_position`
- `call_count`
- `limp_count`
- `raise_time`

这只能覆盖 first-in 的一部分语义, 无法正确重建 reentry 所需的:

- `previous_action`
- `aggressor_first_in`
- `hero_invest_raises`
- `in_position_on_flop`

所以第一版必须新增更完整的 `solver_node -> param_index` 映射器。

### 3. Reentry 语义必须看完整前缀

根据项目约定:

- `PreFlopParams.previous_action = FOLD` 表示“当前玩家在当前决策点之前尚未行动”。
- multi-action preflop 必须根据“当前决策点之前的完整前缀”推导上下文, 不能偷懒只看最后一次 raise/call 计数。

这意味着映射器必须以 `history_full/history_actions` 为主, 不能只看导入时写入的聚合字段。

## 方案结论

采用“共享历史重建逻辑 + 离线 bucket 相似度分析”的方案:

```text
solver_nodes + solver_actions
  -> history_full/history_actions + acting_position
  -> solver node param mapper
  -> param_index -> 169x3 bucket profile
  -> pairwise distance matrix
  -> complete-link threshold clustering
  -> merge suggestions + representative bucket
```

这个方案的优点:

1. 和 Rust `preflop_param_index` 口径一致。
2. 与现有 `preflop_parse` 历史模拟逻辑复用度高。
3. 第一版先做离线分析, 风险最小。
4. 后续如果要把桶簇喂给 `population_vb` 或别的训练流程, 可以直接复用中间层。

## 模块设计

### 新增模块

新增 [`src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py`](/home/autumn/bayes_poker/src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py)。

职责:

1. 定义输入/输出数据结构。
2. 从策略 sqlite 读取单个 `source_id` 的节点与动作。
3. 把 `solver_node` 映射到 `preflop_param_index`。
4. 构建每个桶的 `169 x 3` 策略画像。
5. 计算距离矩阵、最近邻和阈值聚类结果。
6. 生成自动阈值扫描与推荐结果。

### 新增脚本

新增 [`scripts/analyze_preflop_bucket_similarity.py`](/home/autumn/bayes_poker/scripts/analyze_preflop_bucket_similarity.py)。

职责:

1. 解析命令行参数。
2. 加载 hits CSV。
3. 调用 `bucket_similarity.py` 的主流程。
4. 将分析结果写入 CSV / JSON。

## Param 映射设计

### 输入

对每个 `solver_node`, 使用以下字段:

- `history_full`
- `history_actions`
- `acting_position`
- `actor_position` 仅作为辅助校验, 不是主事实源

### 历史模拟

直接复用 [`parser.py`](/home/autumn/bayes_poker/src/bayes_poker/strategy/preflop_parse/parser.py) 中已有的基础能力:

- `split_history_tokens()`
- 6-max preflop 行动顺序模拟
- token 对应位置序列解析
- `aggressor_position` 推导
- `is_in_position` 推导

在此基础上补足 `PreFlopParams` 所需的缺失字段:

1. `previous_action`
- 如果当前 actor 在历史前缀中从未行动, 设为 `FOLD`
- 否则取 actor 上一次真实动作族

2. `hero_invest_raises`
- 统计当前 actor 在历史前缀中已经投入的激进行动次数

3. `aggressor_first_in`
- 找到最后一次 aggressor 在其首次激进行动之前是否出现过非 `FOLD` 动作
- 若有, 则为 `False`; 否则为 `True`

4. `num_callers`
- first-in 阶段: 用前缀中的 limp 数语义压成 `0/1`
- reentry 阶段: 用当前轮最后一次激进行动后的 call 数语义压成 `0/1`

5. `num_raises`
- 直接按完整前缀中激进行动次数计算

6. `in_position_on_flop`
- 若存在 aggressor, 复用已有位置判断逻辑
- 否则对 first-in 阶段使用 `False` 占位, 因为 `to_index()` 在 `previous_action=FOLD` 时不会读取该字段

### 输出

产出:

- `param_index: int | None`
- 辅助调试字段:
  - `previous_action`
  - `hero_invest_raises`
  - `aggressor_first_in`
  - `num_raises`
  - `num_callers`

当历史无法可靠重建时, 返回 `None`, 并在分析结果里单独计数这些未映射节点。

## Bucket 策略画像

### 动作折叠

每个 `solver_action` 的 `preflop_range` 已经是 169 维。第一版统一折叠为 `F/C/R` 三动作族:

- `FOLD` -> `F`
- `CALL/CHECK/LIMP` -> `C`
- 任意 `RAISE/ALL-IN/不同尺度加注` -> `R`

对于同一节点下多个 raise 尺度, 统一累加到 `R`。

### 单节点画像

单节点画像是一个 `169 x 3` 浮点矩阵:

- 行: 169 手牌类
- 列: `F/C/R`

每一行做归一化, 满足:

```text
P[h, F] + P[h, C] + P[h, R] = 1
```

如果某一行在原始数据里全为 0, 则该行保持 0, 不做人工平滑。

### 单桶画像

同一个 `param_index` 下可能映射到多个 `solver_node`。第一版按节点 `total_combos` 总和作为权重, 对节点画像做加权平均, 得到桶级画像。

同时保留这些元信息:

- `node_count`
- `history_actions` 去重列表
- `total_node_weight`
- `hits`

## 距离定义

### 主方案

距离在 `169 x 3` 空间直接计算, 不展开到 `1326` 组合维度。

默认距离定义:

```text
D(a, b) = sqrt(
  sum_h w_h * sum_f (P_a[h, f] - P_b[h, f])^2
  / sum_h w_h
)
```

其中:

- `h` 为 169 手牌类
- `f` 为 `F/C/R`
- `w_h` 为该手牌类的组合数权重:
  - 对子 = 6
  - 同花 = 4
  - 非同花 = 12

### 可选权重模式

第一版保留一个参数开关:

- `combo`: 默认, 使用 `6/4/12` 权重
- `uniform`: 169 类完全等权

## 聚类与合并规则

### 聚类方法

使用 complete-link 阈值聚类。

合并条件:

- 两个簇合并后, 簇内任意两桶的距离都必须 `<= threshold`

这样可以避免 single-link 的链式误并:

- `A` 接近 `B`
- `B` 接近 `C`
- 但 `A` 与 `C` 很远

在 complete-link 下, 这种情况不会被误并成同一簇。

### 代表桶

每个簇的代表桶固定选择 `hits` 最大的桶。

如果 `hits` 并列, 再按:

1. 桶编号升序
2. 总节点权重降序

做稳定 tie-break。

## 阈值扫描与自动建议

### 手动阈值

如果用户传入 `--distance-threshold`, 直接用该阈值生成合并簇。

### 自动建议阈值

如果未传阈值, 则扫描有效桶两两距离的默认分位点网格, 例如:

- `0.05, 0.10, ..., 0.50`

每个候选阈值输出:

- `cluster_count`
- `merged_bucket_count`
- `merged_hit_ratio`
- `non_singleton_cluster_count`
- `max_cluster_size`
- `max_cluster_hit_ratio`
- `avg_intra_cluster_distance`

推荐阈值遵循两层逻辑:

1. 优先找“簇数下降明显放缓”的 elbow 候选
2. 同时满足安全护栏:
   - `max_cluster_size <= 8`
   - `max_cluster_hit_ratio <= 0.35`

如果没有候选同时满足护栏, 则回退到最保守的可用阈值。

## CLI 设计

脚本入口: [`scripts/analyze_preflop_bucket_similarity.py`](/home/autumn/bayes_poker/scripts/analyze_preflop_bucket_similarity.py)

### 输入参数

必填:

- `--strategy-db`
- `--source-id`
- `--hits-csv`
- `--output-dir`

可选:

- `--stack-bb`, 默认 `100`
- `--table-type`, 默认 `6`
- `--distance-threshold`
- `--threshold-quantiles`
- `--weight-mode`, 默认 `combo`
- `--max-cluster-size`, 默认 `8`
- `--max-cluster-hit-ratio`, 默认 `0.35`
- `--nearest-k`, 默认 `5`

### hits CSV 格式

第一版只支持 CSV 输入, 至少包含两列:

- `preflop_param_index`
- `hits`

示例可由 ClickHouse SQL 导出:

```sql
SELECT preflop_param_index, COUNT() AS hits
FROM player_actions
WHERE street = 1 AND preflop_param_index >= 0
GROUP BY preflop_param_index
ORDER BY preflop_param_index ASC;
```

## 输出文件

输出目录下生成:

1. `bucket_profiles.csv`
- 每个桶的基础画像元信息

2. `bucket_distance_matrix.csv`
- 两两桶距离矩阵

3. `bucket_nearest_neighbors.csv`
- 每个桶最近的 `K` 个桶

4. `bucket_threshold_sweep.csv`
- 阈值扫描结果

5. `bucket_merge_suggestions.csv`
- 最终阈值下的建议合并簇

6. `bucket_merge_summary.json`
- 分析元数据、推荐阈值和整体统计

## 测试设计

新增 [`tests/test_bucket_similarity.py`](/home/autumn/bayes_poker/tests/test_bucket_similarity.py), 覆盖:

1. `history_full -> param_index`
- first-in 桶
- passive reentry 桶
- active reentry 桶
- `aggressor_first_in=False` 场景

2. 动作折叠
- 多个 raise 尺度正确合并到 `R`

3. 距离计算
- `169 x 3` 加权 `L2` 数值正确
- `combo` 与 `uniform` 两种模式输出可区分

4. 聚类规则
- complete-link 不发生链式误并
- 代表桶永远选择 `hits` 最大

5. 阈值扫描
- 小样本下输出稳定推荐阈值

新增 [`tests/test_analyze_preflop_bucket_similarity_cli.py`](/home/autumn/bayes_poker/tests/test_analyze_preflop_bucket_similarity_cli.py), 覆盖最小端到端 CLI 冒烟流程。

## 风险与应对

### 1. solver 节点历史不一定能 100% 映射到 65 桶

原因:

- 策略库可能包含更深的 4bet+/jam 树
- 某些历史 token 组合未被统计层定义覆盖

应对:

- 显式记录 `unmapped_node_count`
- 未映射节点不参与桶画像聚合
- 在 summary JSON 中输出未映射比例

### 2. 某些桶可能没有任何 solver 节点

应对:

- 只对“既有 hits 又有 GTO 画像”的桶计算距离
- 在 summary 里区分:
  - `hits_only_bucket_count`
  - `solver_only_bucket_count`
  - `analyzable_bucket_count`

### 3. 自动阈值可能过于激进或保守

应对:

- 始终输出完整 `threshold_sweep.csv`
- 用户可直接改用手动阈值
- 推荐阈值只作为默认建议, 不是强制值

## 结论

第一版以离线脚本为边界, 重点解决“正确映射 bucket”和“稳定给出阈值合并建议”两个问题。核心实现顺序应为:

1. 先完成 `solver_node -> param_index` 的历史重建映射。
2. 再完成 `param_index -> 169x3` 策略画像聚合。
3. 最后补距离、阈值扫描和 CSV/JSON 输出。

这样可以把风险集中在最关键的映射层, 也便于后续把这套桶级画像继续接入 `population_vb` 或其他降维训练流程。
