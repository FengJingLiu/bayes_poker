# Preflop 策略 SQLite 化与 Mapper 主链重构设计

## 背景

当前 `strategy/preflop_parse` 的核心产物仍然是内存态 `PreflopStrategy / StrategyNode`:

- `parser.py` 负责从策略目录解析 JSON, 再堆成 `nodes_by_stack`。
- `query.py` 负责基于 `history` 做精确匹配和 fallback。
- `preflop_engine/mapper.py` 虽然已经改成按状态距离匹配, 但候选节点仍来自内存态 `StrategyNode`, 并在运行时临时推导匹配字段。

这导致两个问题:

1. 运行时主链仍被旧的内存结构绑住, 不能直接围绕 `mapper` 的访问模式建索引。
2. 解析层没有把“对 `mapper` 有用的数据”结构化保存下来, 每次启动都要重新解析和重建候选状态。

本次重构的目标不是简单把 JSON 原样落库, 而是把 `preflop_parse` 改造成一个面向 `mapper + solver_prior` 的结构化 sqlite 策略库。

## 目标

本轮重构的目标如下:

1. `preflop_parse` 从“目录解析为内存树”改成“目录解析为结构化记录并落到 sqlite”。
2. `mapper.py` 不再扫描 `nodes_by_stack`, 而是直接从 sqlite 读取候选节点并按距离排序。
3. `solver_prior.py` 不再按 `history` 取 `StrategyNode`, 而是按候选 `node_id` 批量读取动作。
4. `history_full` 仅保留为溯源和解释字段, 不再作为运行时主查询主键。
5. `query.py` 退出主链, 不再保留 fallback 语义设计。

## 非目标

本轮不做以下内容:

- 不按 `history` 保留旧的查询兼容层。
- 不为 `query.py` 继续补 fallback 规则。
- 不将 `169` 维 `strategy/ev` 拆成逐手牌行级表。
- 不处理 postflop 策略存储。
- 不自动做策略库增量同步或在线更新。

## 方案结论

采用“主链切换到 sqlite”的方案:

```text
策略目录 JSON
  -> parser 解析出结构化 node/action 记录
  -> importer 批量写入 sqlite

运行时:
真实动作
  -> build_preflop_decision_state
  -> mapper 从 sqlite 取候选节点并做距离匹配
  -> solver_prior 按 node_id 批量读取动作并聚合
```

核心原则:

> 后续运行时不再通过 `history` 查询策略, 而是完全通过共享状态和 `mapper` 找到 solver 节点。

## 模块设计

建议将 `preflop_parse` 和 `storage` 调整为如下结构:

```text
src/bayes_poker/strategy/preflop_parse/
├── __init__.py
├── records.py
├── parser.py
├── serialization.py
├── importer.py
└── loader.py

src/bayes_poker/storage/
└── preflop_strategy_repository.py
```

各模块职责:

- `records.py`
  - 定义导入阶段中间记录。
  - 包括 `ParsedStrategyNodeRecord`、`ParsedStrategyActionRecord`。

- `parser.py`
  - 负责 `JSON -> Parsed*Record`。
  - 直接生成供 sqlite 落库的结构化记录。
  - 在解析阶段就推导 `mapper` 所需匹配字段。

- `serialization.py`
  - 负责 `PreflopRange` 与 BLOB 互转。
  - 统一 `169 * float32 * little-endian` 编解码。

- `importer.py`
  - 负责批量导入策略目录。
  - 管理事务、清库重建、批量插入和索引初始化。

- `loader.py`
  - 提供高层入口, 例如:
    - `build_preflop_strategy_db(...)`
    - `open_preflop_strategy_repository(...)`

- `preflop_strategy_repository.py`
  - 负责 sqlite schema、连接、读写接口。
  - 为 `mapper` 和 `solver_prior` 提供统一读取面。

## 数据模型

### strategy_sources

保存策略源元信息。

建议字段:

- `source_id`
- `strategy_name`
- `source_dir`
- `format_version`
- `imported_at`

用途:

- 支持多个策略目录共存。
- 支持重建库时追踪来源和版本。

### solver_nodes

一行表示一个 solver 决策节点, 同时保存“节点事实”和“匹配字段”。

建议字段:

- `node_id`
- `source_id`
- `stack_bb`
- `history_full`
- `history_actions`
- `history_token_count`
- `acting_position`
- `source_file`
- `action_family`
- `actor_position`
- `aggressor_position`
- `call_count`
- `limp_count`
- `raise_size_bb`
- `is_in_position`

关键约束:

- `UNIQUE(source_id, stack_bb, history_full)`

关键索引:

- `(source_id, stack_bb, action_family, actor_position)`
- `(source_id, stack_bb, action_family, aggressor_position)`
- `(source_id, stack_bb, action_family, call_count, limp_count)`
- `(source_id, stack_bb, action_family, raise_size_bb)`

说明:

- `history_full` 仍保留, 但仅用于调试、解释和回溯。
- `mapper` 的运行时筛选和距离计算只依赖结构化字段。

### solver_actions

一行表示一个节点下的一个动作。

建议字段:

- `action_id`
- `node_id`
- `order_index`
- `action_code`
- `action_type`
- `bet_size_bb`
- `is_all_in`
- `total_frequency`
- `next_position`
- `strategy_blob`
- `ev_blob`
- `total_ev`
- `total_combos`

关键约束:

- `UNIQUE(node_id, order_index)`

说明:

- `strategy_blob` 和 `ev_blob` 使用 `float32` BLOB 保存。
- 读取时恢复为 `PreflopRange`。
- 不拆成 169 行, 避免库体积暴涨和读取成本上升。

## 解析与落库流程

### 1. 解析

`parser.py` 在读取每个 JSON 文件时完成以下工作:

1. 解析文件名, 得到 `stack_bb` 和 `history_full`。
2. 解析 `solutions` 数组, 生成动作记录。
3. 标准化 `history_actions`。
4. 根据节点信息推导 `mapper` 匹配字段:
   - `action_family`
   - `actor_position`
   - `aggressor_position`
   - `call_count`
   - `limp_count`
   - `raise_size_bb`
   - `is_in_position`
5. 产出 `ParsedStrategyNodeRecord` 和其下属 `ParsedStrategyActionRecord`。

### 2. 序列化

`serialization.py` 负责:

- 将 `PreflopRange.strategy` 编码为 `float32` BLOB。
- 将 `PreflopRange.evs` 编码为 `float32` BLOB。
- 解码时强校验:
  - 字节长度必须等于 `169 * 4`
  - 编码端序必须固定

### 3. 导入

`importer.py` 负责:

1. 创建或重建 sqlite 库。
2. 写入 `strategy_sources`。
3. 批量写入 `solver_nodes`。
4. 批量写入 `solver_actions`。
5. 建立索引并提交事务。

导入原则:

- 第一阶段只支持“从目录全量重建一个库”。
- 不做增量 merge, 避免状态复杂化。

## 运行时主链

### Mapper

`preflop_engine/mapper.py` 改造后:

- 输入仍然是 `PreflopDecisionState`。
- 候选来源改为 `PreflopStrategyRepository.list_candidates(...)`。
- repository 先按 `stack_bb + action_family + actor_position` 做粗筛。
- Python 层再按现有距离函数完成最终排序和价格修正。

这样保留当前 `mapper` 的可解释距离逻辑, 同时避免扫描整棵内存树。

### Solver Prior

`preflop_engine/solver_prior.py` 改造后:

- 输入是 `MappedSolverContext` 中的候选 `node_id`。
- 使用 repository 批量读取候选节点动作。
- 按 `candidate_distances` 做指数衰减权重聚合。

关键约束:

- 必须批量按 `node_id IN (...)` 取动作。
- 不能写成逐候选单独查库的 N+1 查询。

## 待退役模块

### query.py

`query.py` 在新设计里不再承担主链职责:

- 不再保留 fallback 策略设计。
- 不再作为 `PreflopStrategy.query()` 的主调用面。
- 可以在重构后删除, 或退化为明确报错/弃用模块。

### PreflopStrategy / StrategyNode

这两个对象不再作为运行时主链依赖:

- 可以保留为测试构造体或导入中间态。
- 但 `mapper` 和 `solver_prior` 不再依赖 `nodes_by_stack`。

## 风险与约束

### 1. 解析语义和映射语义必须只有一套

如果导入阶段和运行时对 `action_family`、`call_count`、`is_in_position`
的理解不一致, 会出现:

- 数据成功导入
- 但 `mapper` 永远匹配不准

约束:

- 匹配字段必须在导入阶段一次性生成。
- 运行时不允许再临时推导另一套逻辑。

### 2. sqlite 索引必须围绕运行时访问模式设计

这次访问主链只有两类:

- `mapper` 的候选筛选
- `solver_prior` 的动作批量回表

如果表结构只围绕原始 JSON 设计, 落库后性能可能比内存态更差。

### 3. BLOB 编解码必须稳定

`float32` 精度对策略频率是足够的, 真正的风险在于:

- 长度不一致
- 端序不一致
- 解码时静默容错

约束:

- 编解码必须显式校验长度和格式。

## 测试策略

建议测试分为四层:

1. `serialization` 单测
   - `PreflopRange -> BLOB -> PreflopRange`
   - 长度错误和坏数据失败行为

2. `parser` 单测
   - JSON -> node/action record
   - 匹配字段推导是否与 `mapper` 语义一致

3. `repository` 单测
   - schema 初始化
   - 全量导入
   - 候选节点读取
   - 批量动作读取

4. 端到端集成测试
   - 使用 `tests/fixtures/Cash6m50zGeneral`
   - 跑通:
     - 导入 sqlite
     - `mapper` 取候选
     - `solver_prior` 聚合

## 验收标准

本轮改造完成后, 至少应满足:

1. 策略目录可以完整导入 sqlite。
2. `mapper.py` 不再依赖 `nodes_by_stack`。
3. `solver_prior.py` 不再依赖 `history -> get_node()`。
4. 运行时主链变为 `state -> mapper -> solver_prior`。
5. `query.py` 不再作为系统主能力存在。
6. 小型真实策略目录上的 `mapper + solver_prior` 端到端测试通过。
