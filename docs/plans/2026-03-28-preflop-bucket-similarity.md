# Preflop 分桶策略相似度分析脚本 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为单个 `source_id` 构建一个离线脚本, 基于 solver 策略把 `preflop_param_index` 聚合成 `169 x 3` 桶画像, 计算桶间距离, 并按阈值输出可合并桶簇。

**Architecture:** 新增一个 `bucket_similarity` 模块负责 `solver_node -> param_index` 映射、桶画像聚合、距离矩阵和 complete-link 聚类。CLI 脚本只负责解析参数、读取 hits CSV 和落盘结果。映射规则必须以 `history_full/history_actions` 重建为主, 并最终通过 Python `PreFlopParams.to_index()` 与 Rust `preflop_params.rs` 保持一致。

**Tech Stack:** Python 3.12, numpy, sqlite3, csv, pytest, uv

---

### Task 1: 为 `solver_node -> param_index` 映射写失败测试

**Files:**
- Modify: `tests/test_bucket_similarity.py`
- Reference: `crates/poker_stats_rs/src/preflop_params.rs`
- Reference: `src/bayes_poker/strategy/preflop_parse/parser.py`

**Step 1: 写 first-in 场景失败测试**
- 新增一个最小测试, 断言空历史 + `acting_position=UTG` 能映射到桶 `0`。
- 再增加一个 `F-F-F-F-C` 且 `acting_position=BB` 的 limp defense 场景, 断言落到合法 first-in 桶。

**Step 2: 写 reentry 场景失败测试**
- 增加一个 passive reentry 场景, 覆盖 `previous_action=CALL/CHECK`。
- 增加一个 active reentry 场景, 覆盖 `hero_invest_raises > 0`。
- 增加一个 `aggressor_first_in=False` 的场景, 断言桶编号不同于 `True`。

**Step 3: 运行测试验证失败**
- Run: `uv run pytest tests/test_bucket_similarity.py -k param_index -q`
- Expected: 失败并提示缺少映射模块或返回值错误。

### Task 2: 实现共享的 bucket 映射与画像基础结构

**Files:**
- Create: `src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py`
- Modify: `src/bayes_poker/strategy/strategy_engine/population_vb/__init__.py`（如果该目录已有导出需求）
- Test: `tests/test_bucket_similarity.py`

**Step 1: 定义数据结构**
- 新增用于承载节点映射结果、桶画像结果、阈值扫描结果的 dataclass。
- 所有公开函数补全 Google 风格中文注释与类型标注。

**Step 2: 复用历史解析基础能力**
- 从 `preflop_parse.parser` 复用 `split_history_tokens()` 和现有位置模拟辅助函数。
- 在新模块中实现 `map_solver_node_to_preflop_param_index(...)`。

**Step 3: 实现 `previous_action / hero_invest_raises / aggressor_first_in` 推导**
- 基于完整历史前缀为当前 actor 重建前序动作。
- 保证 reentry 场景不退化成只看 `raise_time/call_count` 的粗映射。

**Step 4: 运行映射测试验证通过**
- Run: `uv run pytest tests/test_bucket_similarity.py -k param_index -q`
- Expected: PASS。

**Step 5: Commit**
```bash
git add src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py tests/test_bucket_similarity.py
git commit -m "feat: add preflop bucket param mapper"
```

### Task 3: 为桶画像聚合与距离计算写失败测试

**Files:**
- Modify: `tests/test_bucket_similarity.py`
- Reference: `src/bayes_poker/storage/preflop_strategy_repository.py`

**Step 1: 写动作折叠测试**
- 构造一个节点包含 `F/C/R4/R10` 四个动作。
- 断言画像聚合后只保留 `F/C/R` 三列, 且两个 raise 被累加到 `R`。

**Step 2: 写桶级加权聚合测试**
- 构造两个映射到同一 `param_index` 的节点, 给不同 `total_combos`。
- 断言桶画像按节点权重做加权平均。

**Step 3: 写距离测试**
- 构造两个小画像矩阵, 断言 `combo` 权重模式的距离值符合预期。
- 再断言 `uniform` 模式与 `combo` 模式结果不同。

**Step 4: 运行测试验证失败**
- Run: `uv run pytest tests/test_bucket_similarity.py -k "profile or distance" -q`
- Expected: FAIL, 因为画像与距离函数尚未实现。

### Task 4: 实现桶画像聚合与距离矩阵

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py`
- Test: `tests/test_bucket_similarity.py`

**Step 1: 实现动作族折叠函数**
- 读取 `SolverActionRecord`。
- 将任意 raise 尺度统一折叠到 `R` 列。

**Step 2: 实现单节点 `169 x 3` 画像构建**
- 每个手牌行做 `F/C/R` 归一化。
- 零行保持零值, 不做隐式平滑。

**Step 3: 实现单桶画像聚合**
- 按 `total_combos` 聚合节点画像。
- 保留 `node_count / total_node_weight / history_actions / hits` 元信息。

**Step 4: 实现距离矩阵计算**
- 支持 `combo` 与 `uniform` 两种权重模式。
- 结果输出为对称矩阵, 对角线为 `0.0`。

**Step 5: 运行测试验证通过**
- Run: `uv run pytest tests/test_bucket_similarity.py -k "profile or distance" -q`
- Expected: PASS。

**Step 6: Commit**
```bash
git add src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py tests/test_bucket_similarity.py
git commit -m "feat: add preflop bucket profiles and distance matrix"
```

### Task 5: 为 complete-link 聚类与代表桶规则写失败测试

**Files:**
- Modify: `tests/test_bucket_similarity.py`

**Step 1: 写链式误并防护测试**
- 构造三个桶 `A/B/C`, 满足 `A-B` 和 `B-C` 低于阈值, `A-C` 高于阈值。
- 断言 complete-link 下不会把三者并成同一簇。

**Step 2: 写代表桶选择测试**
- 构造一个两桶簇, 距离很近, 但 `hits` 不同。
- 断言代表桶固定选择 `hits` 最大者。

**Step 3: 写阈值扫描测试**
- 构造一个小距离矩阵和 hits 映射。
- 断言阈值扫描会输出推荐阈值和完整 sweep 统计。

**Step 4: 运行测试验证失败**
- Run: `uv run pytest tests/test_bucket_similarity.py -k "cluster or threshold or representative" -q`
- Expected: FAIL, 因为聚类逻辑尚未实现。

### Task 6: 实现聚类、阈值扫描与分析结果结构

**Files:**
- Modify: `src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py`
- Test: `tests/test_bucket_similarity.py`

**Step 1: 实现 complete-link 阈值聚类**
- 输入距离矩阵和阈值。
- 输出稳定的簇列表, 成员桶升序。

**Step 2: 实现代表桶选择**
- 先按 `hits` 降序。
- 再按 `param_index` 升序兜底。

**Step 3: 实现阈值扫描与推荐逻辑**
- 根据默认分位点网格依次求簇统计。
- 按 `max_cluster_size` 与 `max_cluster_hit_ratio` 护栏筛选推荐值。

**Step 4: 运行测试验证通过**
- Run: `uv run pytest tests/test_bucket_similarity.py -k "cluster or threshold or representative" -q`
- Expected: PASS。

**Step 5: Commit**
```bash
git add src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py tests/test_bucket_similarity.py
git commit -m "feat: add preflop bucket merge clustering"
```

### Task 7: 为 CLI 冒烟流程写失败测试

**Files:**
- Create: `tests/test_analyze_preflop_bucket_similarity_cli.py`
- Reference: `tests/test_population_vb_cli.py`

**Step 1: 构造最小策略库 fixture**
- 使用 `PreflopStrategyRepository` 写入少量 `solver_nodes/solver_actions`。
- 保证至少两个桶可分析。

**Step 2: 构造 hits CSV fixture**
- 写出 `preflop_param_index,hits` 两列。

**Step 3: 写 CLI 测试**
- 调用脚本主入口。
- 断言输出目录生成 `bucket_merge_summary.json` 与 `bucket_merge_suggestions.csv`。

**Step 4: 运行测试验证失败**
- Run: `uv run pytest tests/test_analyze_preflop_bucket_similarity_cli.py -q`
- Expected: FAIL, 因为 CLI 入口尚未实现。

### Task 8: 实现 CLI 与结果落盘

**Files:**
- Create: `scripts/analyze_preflop_bucket_similarity.py`
- Modify: `src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py`
- Test: `tests/test_analyze_preflop_bucket_similarity_cli.py`

**Step 1: 实现 CLI 参数解析**
- 支持 `--strategy-db --source-id --hits-csv --output-dir` 必填参数。
- 支持 `--distance-threshold` 和自动阈值模式。

**Step 2: 实现 hits CSV 读取与校验**
- 缺列时报错。
- 自动忽略负桶或无效行。

**Step 3: 实现 CSV / JSON 落盘**
- 写出 `bucket_profiles.csv`
- 写出 `bucket_distance_matrix.csv`
- 写出 `bucket_nearest_neighbors.csv`
- 写出 `bucket_threshold_sweep.csv`
- 写出 `bucket_merge_suggestions.csv`
- 写出 `bucket_merge_summary.json`

**Step 4: 运行 CLI 冒烟测试验证通过**
- Run: `uv run pytest tests/test_analyze_preflop_bucket_similarity_cli.py -q`
- Expected: PASS。

**Step 5: Commit**
```bash
git add scripts/analyze_preflop_bucket_similarity.py src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py tests/test_analyze_preflop_bucket_similarity_cli.py
git commit -m "feat: add preflop bucket similarity analysis cli"
```

### Task 9: 完整验证

**Files:**
- No code changes

**Step 1: 运行新增测试文件**
- Run: `uv run pytest tests/test_bucket_similarity.py tests/test_analyze_preflop_bucket_similarity_cli.py -q`
- Expected: PASS。

**Step 2: 运行相关既有测试防回归**
- Run: `uv run pytest tests/test_population_vb_cli.py tests/test_preflop_strategy_repository.py -q`
- Expected: PASS。

**Step 3: 用真实库做一次脚本冒烟**
- Run: `uv run python scripts/analyze_preflop_bucket_similarity.py --strategy-db data/database/preflop_strategy.sqlite3 --source-id 1 --hits-csv <your_hits_csv> --output-dir /tmp/preflop_bucket_similarity`
- Expected: 产出完整 CSV/JSON 文件, summary 中给出推荐阈值或手动阈值结果。

**Step 4: Commit**
```bash
git add scripts/analyze_preflop_bucket_similarity.py src/bayes_poker/strategy/strategy_engine/population_vb/bucket_similarity.py tests/test_bucket_similarity.py tests/test_analyze_preflop_bucket_similarity_cli.py
git commit -m "test: verify preflop bucket similarity workflow"
```
