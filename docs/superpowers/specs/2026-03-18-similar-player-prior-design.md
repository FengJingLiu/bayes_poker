# 相似玩家个性化先验 — 设计文档

> 日期: 2026-03-18
> 分支: `feature/similar-player-prior`
> 前置: adaptive bayesian smoothing (df57836)

## 1. 背景与动机

当前 bayes_poker 的对手建模使用**单一 pool 先验** (`aggregated_sixmax_100`) 做贝叶斯平滑。
这意味着对一个 tight nit (PFR=8%) 和 maniac (PFR=35%), 在数据不足时都回归到同一个全局均值。

参考 G5 poker bot (ACPC 2018 冠军) 的核心创新: 基于 VPIP/PFR 欧氏距离找到风格相似的玩家,
用**他们在特定节点的实际数据**构建个性化先验, 而非全局池化均值。

同时引入 1000 手样本上限, 限制 confidence 和 adaptive_k 的增长,
使大样本玩家仍保留对先验的适度依赖。

## 2. 设计目标

1. 替换先验来源: pool 先验 → 相似玩家群体先验 (仅 preflop)
2. 保留现有 Dirichlet 平滑算法 (`posterior.py`), 只改变先验数据来源
3. 每个节点独立 fallback: 相似玩家数据不足时回退到 pool 先验
4. 功能开关默认**开启**, 可显式关闭
5. 样本上限 1000 手: 仅影响 `confidence` 和 `adaptive_k` 计算, 不影响 `_smooth_action_stats()` 的原始计数

## 3. 方案选择

评估了三种方案:

- **方案 A (采纳)**: Repository 层替换 — 最小侵入, 只改先验来源
- **方案 B**: Adapter 层全面重构 — 完整 G5 三层逻辑, 侵入性大
- **方案 C**: A + 累积合并 — A 的自然扩展, 可后续追加

选择方案 A 的理由:
- 不改变已验证的平滑算法, 风险最低
- 累积合并可作为 A 的增量扩展 (~30 行), 无需一次性引入
- 现有 Dirichlet 平滑刚通过 Oracle 4 轮审查

## 4. 架构设计

### 4.1 新增组件: SimilarPlayerIndex

**文件**: `src/bayes_poker/strategy/strategy_engine/similar_player_index.py`

**职责**: 纯内存的 VPIP/PFR 索引, 支持按欧氏距离查找最相似的 K 个玩家。

```python
@dataclass(frozen=True)
class PlayerProfile:
    """单个玩家的风格摘要."""
    player_name: str
    vpip: float          # 0.0~1.0
    pfr: float           # 0.0~1.0
    total_hands: int     # 用于过滤低样本玩家

class SimilarPlayerIndex:
    """基于 VPIP/PFR 欧氏距离的相似玩家索引."""

    def __init__(
        self,
        profiles: list[PlayerProfile],
        min_hands: int = 30,
    ) -> None:
        # 过滤掉 total_hands < min_hands 的玩家
        # 同时排除名称以 "aggregated_" 开头的聚合先验玩家
        self._profiles: list[PlayerProfile] = [
            p for p in profiles
            if p.total_hands >= min_hands
            and not p.player_name.startswith("aggregated_")
        ]

    def find_similar(
        self,
        target_vpip: float,
        target_pfr: float,
        max_results: int = 130,
        max_distance: float = 0.15,
        exclude_player: str | None = None,
    ) -> list[tuple[PlayerProfile, float]]:
        """返回 (profile, distance) 列表, 按距离升序.

        Args:
            target_vpip: 目标玩家 VPIP (0.0~1.0).
            target_pfr: 目标玩家 PFR (0.0~1.0).
            max_results: 最多返回的相似玩家数量.
            max_distance: 欧氏距离阈值, 超过则排除.
            exclude_player: 排除的玩家名 (通常是目标玩家自己).

        Returns:
            按距离升序排列的 (PlayerProfile, distance) 列表.
            可能返回空列表 (无相似玩家).
        """
        # 欧氏距离: sqrt((vpip_diff)^2 + (pfr_diff)^2)
        # 排除 distance > max_distance
        # 排除 exclude_player
        # 按 distance 升序排序, 取 top max_results
```

**关键参数**:

| 参数 | 默认值 | 说明 |
|-----|--------|------|
| `min_hands` | 30 | 相似玩家自身至少有 30 手, 否则 VPIP/PFR 不可靠 |
| `max_results` | 130 | 最多取 130 个相似玩家 (与 G5 一致) |
| `max_distance` | 0.15 | 欧氏距离阈值 (约等于两个维度各差 10%) |

**重要**: `aggregated_sixmax_100` 等聚合先验玩家在构造时被排除, 不会进入相似集合。

### 4.2 Repository 层: 相似玩家先验构建

**文件**: `src/bayes_poker/storage/player_stats_repository.py`

**新增方法**: `get_with_similar_prior()`

**作用域**: **仅替换 preflop 节点的先验来源**; postflop 节点继续使用现有 pool 先验平滑,
与当前引擎只消费 preflop 节点的边界一致。

```python
def get_with_similar_prior(
    self,
    player_name: str,
    table_type: TableType,
    similar_player_names: list[str],
    prior_strength: float,
    min_aggregate_samples: int = 20,
) -> tuple[PlayerStats | None, PlayerStats | None]:
    """用相似玩家群体先验做 preflop 平滑, 返回 (raw, smoothed).

    Args:
        player_name: 目标玩家名.
        table_type: 桌型.
        similar_player_names: 相似玩家名列表 (由 SimilarPlayerIndex 提供).
        prior_strength: 先验强度 (adaptive_k, 从 stats_adapter 传入).
        min_aggregate_samples: 聚合样本最低阈值, 低于此值 fallback 到 pool.

    Returns:
        (raw_stats, smoothed_stats) 元组.
        raw_stats 为 None 表示目标玩家不存在.

    流程:
      1. 加载目标玩家原始数据 (raw) — 复用 _load_raw()
      2. 批量加载 similar_player_names 的原始数据
      3. 加载 pool 先验 (aggregated_sixmax_100) 作为 fallback
      4. 对每个 preflop 节点:
         a. 用 ActionStats.append() 聚合相似玩家在该节点的 ActionStats
         b. if aggregate.total_samples() >= min_aggregate_samples:
              用 aggregate 作为 pool_action_stats 参数
            else:
              用 pool 先验在该节点的 ActionStats
         c. 调用现有 _smooth_action_stats(raw, pool_or_aggregate, action_space, strength)
      5. postflop 节点: 直接调用现有 _smooth_postflop_stats(raw, pool, strength)
    """
```

**聚合逻辑 (per preflop node)**:

```python
# 对 preflop 节点 index i:
aggregate = ActionStats()  # 全零初始化
for similar_player_raw_stats in similar_players_raw:
    if i < len(similar_player_raw_stats.preflop_stats):
        aggregate.append(similar_player_raw_stats.preflop_stats[i])

if aggregate.total_samples() >= min_aggregate_samples:
    # 用 aggregate 作为 _smooth_action_stats 的 pool_action_stats 参数
    # _smooth_action_stats 内部会:
    #   1. _extract_field_counts(aggregate) → 提取 7 个字段计数
    #   2. _build_prior_probabilities(total_fields, field_counts) → 归一化为概率
    #   3. smooth_binary_counts / smooth_multinomial_counts → Dirichlet 平滑
    smoothed = self._smooth_action_stats(
        raw_action_stats=raw_stats.preflop_stats[i],
        pool_action_stats=aggregate,          # ← 相似玩家聚合替代 pool
        action_space=action_spaces[i],
        pool_prior_strength=prior_strength,
    )
else:
    # fallback: 用 pool 先验
    smoothed = self._smooth_action_stats(
        raw_action_stats=raw_stats.preflop_stats[i],
        pool_action_stats=pool_stats.preflop_stats[i],  # ← 原有 pool
        action_space=action_spaces[i],
        pool_prior_strength=prior_strength,
    )
```

**关键复用**:
- `ActionStats.append()`: 已有方法, 逐字段累加 (bet_0_40/40_80/80_120/over_120/raise/check_call/fold)
- `_smooth_action_stats()`: 完全复用, aggregate 直接作为 `pool_action_stats` 参数传入
- `_build_prior_probabilities()`: 内部自动从 field_counts 归一化为概率向量
- `_build_preflop_action_spaces()`: 复用, 决定每个节点是 binary 还是 multinomial
- 归一化由 `_build_prior_probabilities()` 自动完成, 无需额外代码

**Fallback 分支完整定义**:

| 条件 | 行为 |
|------|------|
| `raw_stats is None` | 返回 `(None, None)` |
| `similar_player_names` 为空列表 | 全部 preflop 节点 fallback 到 pool 先验 |
| 某 preflop 节点聚合样本 >= `min_aggregate_samples` | 用相似玩家聚合先验 |
| 某 preflop 节点聚合样本 < `min_aggregate_samples` | fallback 到 pool 先验 |
| 所有 postflop 节点 | 始终使用 pool 先验 (不变) |

### 4.3 stats_adapter.py 改动

**新增依赖**: 接收 `SimilarPlayerIndex` 实例 (可选)。

```python
class PlayerNodeStatsAdapter:
    def __init__(
        self,
        stats_repo: PlayerStatsRepository,
        config: PlayerNodeStatsAdapterConfig,
        similar_index: SimilarPlayerIndex | None = None,
    ):
        self._similar_index = similar_index
```

**`load()` 流程变更 — 完整分支定义**:

```python
def load(self, player_name: str, table_type: TableType) -> ...:
    # Step 1: 加载原始数据
    raw = self._load_raw_player_stats(player_name, table_type)

    # Step 2: 计算 adaptive prior strength
    adaptive_k = self._compute_adaptive_prior_strength(raw)

    # Step 3: 选择平滑路径
    use_similar = (
        self._similar_index is not None
        and raw is not None
        and raw.vpip.total > 0
    )

    if use_similar:
        # 计算目标玩家 PFR
        pfr_positive, pfr_total = calculate_pfr(raw)
        target_pfr = pfr_positive / pfr_total if pfr_total > 0 else 0.0
        target_vpip = raw.vpip.to_float()

        # 查找相似玩家
        similar_results = self._similar_index.find_similar(
            target_vpip=target_vpip,
            target_pfr=target_pfr,
            max_results=self._config.similar_player_max_results,
            max_distance=self._config.similar_player_max_distance,
            exclude_player=player_name,
        )
        similar_names = [profile.player_name for profile, _dist in similar_results]

        raw, smoothed = self._stats_repo.get_with_similar_prior(
            player_name=player_name,
            table_type=table_type,
            similar_player_names=similar_names,
            prior_strength=adaptive_k,
        )
    else:
        # fallback: 原有 pool 先验流程
        raw, smoothed = self._stats_repo.get_with_raw(
            player_name=player_name,
            table_type=table_type,
            pool_prior_strength=adaptive_k,
        )

    # Step 4: build PlayerNodeStats (不变)
```

**fallback 到原流程的条件**:
- `similar_index is None` (功能关闭)
- `raw is None` (玩家不存在)
- `raw.vpip.total == 0` (无手牌数据, VPIP 不可靠)
- `pfr_total == 0` 时 PFR 按 0.0 处理, 仍走相似玩家路径 (让 find_similar 基于 VPIP 匹配)

**PFR 计算口径**: 直接调用 `builder.py` 的 `calculate_pfr(raw)` 返回 `(positive, total)`,
手动 `positive / total if total > 0 else 0.0`。这与 `stats_adapter._compute_global_pfr()` 的逻辑一致,
不新增 helper 以避免重复。

**向后兼容**: `similar_index=None` 时走原有逻辑, 零行为变更。

### 4.4 样本上限 (Phase 1)

在 `PlayerNodeStatsAdapterConfig` 新增字段:

```python
max_observation_samples: int = 1000
```

**作用域说明**: 样本上限**仅影响** `stats_adapter.py` 中的两个计算点,
**不影响** `_smooth_action_stats()` 的原始计数。即 repository 层平滑时使用完整的
raw ActionStats counts, 不做截断。样本上限的目的是限制 confidence 和 adaptive_k 的增长,
使超过 1000 手后这两个值趋于稳定, 而非限制平滑本身。

**作用点 1 — confidence 计算**:

```python
def _build_confidence(self, raw_action: ActionStats, ...) -> float:
    n = min(raw_action.total_samples(), self._config.max_observation_samples)
    return n / (n + self._config.confidence_k)
```

**作用点 2 — adaptive prior strength**:

```python
def _compute_adaptive_prior_strength(self, raw_stats: PlayerStats | None) -> float:
    total_hands = min(self._get_total_hands(raw_stats), self._config.max_observation_samples)
    # adaptive_strength = base / (1 + total_hands / reference_hands)
    # 其余逻辑不变
```

**效果**: 超过 1000 手后, `confidence` 稳定在 `1000 / (1000 + 20) ≈ 0.98`,
`adaptive_k` 稳定在 `20 / (1 + 1000/200) = 3.33`。先验仍有约 3.33 个虚拟样本的影响力。

### 4.5 engine.py 接线

```python
def build_strategy_engine(config: StrategyEngineConfig, ...) -> StrategyEngine:
    stats_repo = PlayerStatsRepository(db_path)

    similar_index: SimilarPlayerIndex | None = None
    if config.enable_similar_player_prior:
        all_stats = stats_repo.get_all(table_type)
        profiles = []
        for s in all_stats:
            pfr_positive, pfr_total = calculate_pfr(s)
            pfr_float = pfr_positive / pfr_total if pfr_total > 0 else 0.0
            profiles.append(PlayerProfile(
                player_name=s.player_name,
                vpip=s.vpip.to_float(),
                pfr=pfr_float,
                total_hands=s.vpip.total,
            ))
        similar_index = SimilarPlayerIndex(
            profiles,
            min_hands=config.similar_player_min_hands,
        )

    adapter_config = PlayerNodeStatsAdapterConfig(
        pool_prior_strength=config.pool_prior_strength,
        max_observation_samples=config.max_observation_samples,
        similar_player_max_results=config.similar_player_max_results,
        similar_player_max_distance=config.similar_player_max_distance,
        # ... 其余字段
    )
    stats_adapter = PlayerNodeStatsAdapter(stats_repo, adapter_config, similar_index)
```

**`calculate_pfr()` 返回 `tuple[int, int]`** (positive, total), 必须手动除法。
`vpip.to_float()` 返回 `positive / total if total > 0 else 0.0`。

## 5. 配置

### StrategyEngineConfig 新增字段

```python
enable_similar_player_prior: bool = True    # 默认开启, 可显式关闭
similar_player_max_results: int = 130       # 与 G5 一致
similar_player_max_distance: float = 0.15   # 欧氏距离阈值
similar_player_min_hands: int = 30          # 相似玩家最低手数门槛
max_observation_samples: int = 1000         # 样本上限
```

### PlayerNodeStatsAdapterConfig 新增字段

```python
max_observation_samples: int = 1000         # 从 StrategyEngineConfig 透传
similar_player_max_results: int = 130       # 从 StrategyEngineConfig 透传
similar_player_max_distance: float = 0.15   # 从 StrategyEngineConfig 透传
```

**`min_aggregate_samples = 20`**: 定义为 `get_with_similar_prior()` 的参数默认值,
不纳入配置, 因为这是聚合逻辑的内部阈值, 与 G5 的 `minSamples` 一致, 无需外部调整。

### 配置接线路径

```
StrategyEngineConfig
  → engine.py: 构建 SimilarPlayerIndex (min_hands)
  → PlayerNodeStatsAdapterConfig (max_observation_samples, max_results, max_distance)
    → stats_adapter.py: load() 中使用
  → handler.py: 透传 enable_similar_player_prior
```

## 6. 文件改动汇总

| 文件 | 改动类型 | 约估行数 |
|------|---------|---------|
| `strategy/strategy_engine/similar_player_index.py` | **新增** | ~80 |
| `storage/player_stats_repository.py` | 新增 `get_with_similar_prior()` | ~60 |
| `strategy/strategy_engine/stats_adapter.py` | 修改 `load()` + `confidence` cap | ~40 |
| `strategy/strategy_engine/engine.py` | 接线 | ~25 |
| `strategy/strategy_engine/handler.py` | 透传 config | ~5 |
| 测试文件 (新增) | 测试覆盖 | ~200 |
| **总计** | | **~410** |

## 7. 测试策略

### 7.1 SimilarPlayerIndex 单元测试

- 距离计算正确性 (已知 VPIP/PFR, 验证排序)
- `exclude_player` 生效
- `max_distance` 过滤生效
- `min_hands` 过滤生效
- `aggregated_` 前缀玩家被排除
- 空索引返回空列表
- 所有玩家超出 `max_distance` 返回空列表

### 7.2 Repository `get_with_similar_prior()` 集成测试

- 相似玩家在某 preflop 节点有足够数据 → 使用聚合先验 (结果不同于 pool 先验)
- 相似玩家在某 preflop 节点数据不足 → fallback 到 pool 先验 (结果与 `get_with_raw()` 相同)
- `similar_player_names` 为空 → 全部 fallback (结果与 `get_with_raw()` 相同)
- postflop 节点始终使用 pool 先验 (不受相似玩家影响)
- 可观测验证: 固定 fixture, 断言特定节点的 smoothed ActionStats 数值

### 7.3 stats_adapter 测试

- `similar_index=None` → 结果与原流程完全一致 (向后兼容)
- `raw.vpip.total == 0` → fallback 到原流程
- 样本上限 `max_observation_samples=1000`:
  - `total_samples=500` → confidence 正常计算
  - `total_samples=2000` → confidence 按 1000 计算
  - adaptive_k 同理

### 7.4 端到端验证

- 两个不同 PFR 的玩家, 相同节点, 产生不同的 posterior_freq
- 一个 nit (PFR=8%) 的先验应该更接近其他 nit 在该节点的行为, 而非全局 pool 均值

## 8. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 相似玩家数据库太小, 找不到相似玩家 | 每个节点独立 fallback 到 pool 先验 |
| `max_distance` / `max_results` 参数不合适 | 可调配置; 后续可通过离线 EV 评估优化 |
| 初始化时加载全部玩家耗时 | 一次性 O(N), N 通常 < 10000, 毫秒级 |
| `aggregated_sixmax_100` 意外进入相似集合 | 构造时排除 `aggregated_` 前缀 |
| 默认开启导致意外行为 | 所有 fallback 路径保证不比 pool 先验差; 可显式关闭 |
