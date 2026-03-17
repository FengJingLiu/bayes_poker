# 自适应贝叶斯平滑 + 全局 PFR 补偿

> 日期: 2026-03-17
> 状态: 设计审批

## 问题描述

### 现象

在 MP facing 3bet 节点上, bcsilva (PFR=16.8%) 和 Ivan_87 (PFR=54.6%) 经过
`smooth_with_pool=True` 的 stats 适配后, 被映射到了**相同的 posterior_freq**,
导致:

1. **3bettor 风格影响极小**: 无论对手是 tight 还是 loose, Hero 策略几乎不变.
2. **Opener 风格影响过大**: 相比之下 Opener 的影响不成比例地大.

### 根因分析

**第一层: 固定 pool_prior_strength 过高**

当前 `pool_prior_strength=20.0` 固定不变. 在具体节点(如 "MP facing 3bet")上,
即使活跃玩家也可能只有 3-10 个样本:

```
posterior_raise = (20 × pool_raise + 观察raise次数) / (20 + 观察总数)
```

- bcsilva: 5/10 → `(20×pool + 5) / 30` ≈ pool 主导
- Ivan_87: 8/12 → `(20×pool + 8) / 32` ≈ pool 主导
- 两者收敛至几乎相同的 pool 后验值

**第二层: 全局统计信号未被利用**

`stats_adapter` 已经计算了 `confidence` 字段:
```python
confidence = total_samples / (total_samples + confidence_k)
```

但 `opponent_pipeline._adjust_belief_with_stats_and_ev()` 从未使用此字段.
同时, 玩家的全局 PFR/VPIP 等强信号在节点级计算中完全被忽略.

## 设计方案

### 架构概览

```
修改前:
  repo.get(k=20固定) → smoothed_stats → stats_adapter → node_stats
  → opponent_pipeline(忽略confidence)

修改后:
  stats_adapter计算adaptive_k → repo.get_with_raw(k=adaptive_k) → (raw_stats, smoothed_stats)
  → stats_adapter(从raw提取confidence+附加global_pfr/vpip) → node_stats(含raw_confidence+全局信号)
  → opponent_pipeline(用confidence混合节点+全局信号)
```

### 第 1 层: 自适应 pool_prior_strength

**修改文件**: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py`

**新增方法**: `_compute_adaptive_prior_strength()`

```python
def _compute_adaptive_prior_strength(
    self,
    player_stats: PlayerStats,
    base_strength: float = 20.0,
    min_strength: float = 2.0,
    reference_hands: float = 200.0,
) -> float:
    """根据玩家全局手牌量自适应调整 pool_prior_strength.

    全局手牌多 → 信任玩家数据 → 降低 prior_strength.
    全局手牌少 → 不确定性高 → 保持较高 prior_strength.

    Args:
        player_stats: 玩家统计数据.
        base_strength: 基础先验强度, 默认 20.0.
        min_strength: 最小先验强度下界, 默认 2.0.
        reference_hands: 参考手牌数, 达到此数时 k 减半, 默认 200.

    Returns:
        自适应调整后的 pool_prior_strength.
    """
    total_hands = player_stats.vpip.total
    adaptive_k = base_strength / (1.0 + total_hands / reference_hands)
    return max(min_strength, adaptive_k)
```

**参数行为**:

| total_hands | adaptive_k | 含义 |
|-------------|-----------|------|
| 0           | 20.0      | 完全依赖 pool 先验 |
| 100         | 13.3      | 先验开始减弱 |
| 200         | 10.0      | 先验强度减半 |
| 500         | 5.7       | 玩家数据占主导 |
| 1000        | 3.3       | 接近最小值 |

以上为初始可调参数, 需实测验证后确定最优值。

**修改流程**: `load()` 方法改为四步:

1. 调用 `_load_player_stats(smooth_with_pool=False)` 获取 raw_stats (仅用于读取 `vpip.total`)
2. 计算 `adaptive_k = _compute_adaptive_prior_strength(raw_stats)`, 基于全局手牌量
3. 调用 `repo.get_with_raw(player_name, table_type, pool_prior_strength=adaptive_k)` 获取 (raw_stats, smoothed_stats)
4. 从 raw_stats 提取 raw node `total_samples` 计算 `raw_confidence`; 用 smoothed stats 的概率 + raw confidence + 全局 PFR/VPIP 组装 `PlayerNodeStats`

> 注: 步骤 1 和步骤 3 都会读取 raw_stats, 但步骤 1 仅为获取 `vpip.total` 计算 adaptive_k.
> 优化: 可考虑让 `get_with_raw()` 内部先返回 raw_stats, 由调用方计算 adaptive_k 后再触发 smoothing.
> 或者更简单地: 由于 `vpip.total` 无需 smoothing 即可获取, 步骤 1 可直接从缓存或轻量级查询获得.

### 第 1.5 层: Repository 接口扩展

**修改文件**: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py` (使用端)
和 `src/bayes_poker/player_metrics/player_stats_repository.py` (提供端)

**新增方法**: `player_stats_repository.get_with_raw()`

```python
def get_with_raw(
    self,
    player_name: str,
    table_type: TableType,
    *,
    pool_prior_strength: float = 20.0,
) -> tuple[PlayerStats | None, PlayerStats | None]:
    """一次读取, 同时返回 (raw_stats, smoothed_stats).
    
    避免 stats_adapter 需要两次调用 get() 的性能问题.
    内部复用 _get_raw() 和 _smooth_player_stats_with_pool().
    
    Args:
        player_name: 玩家名称.
        table_type: 牌桌类型.
        pool_prior_strength: 平滑时使用的先验强度.
    
    Returns:
        元组 (raw_stats, smoothed_stats), 若玩家不存在则返回 (None, None).
    """
```

通过此接口一次性获取 raw stats（用于 confidence 计算）和 smoothed stats（用于节点级概率）,
避免重复数据库读取和反序列化。

### 第 2 层: 全局 PFR 补偿信号

**修改文件**: `src/bayes_poker/strategy/strategy_engine/stats_adapter.py` (数据传递)
和 `src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py` (消费端)

#### 2a. PlayerNodeStats 新增字段

```python
@dataclass(frozen=True)
class PlayerNodeStats:
    # 现有字段
    raise_probability: float
    fold_probability: float
    call_probability: float
    confidence: float
    # 新增字段
    global_pfr: float      # 玩家全局 PFR (0.0~1.0)
    global_vpip: float     # 玩家全局 VPIP (0.0~1.0)
    total_hands: int       # 总手牌数
```

`stats_adapter.load()` 负责计算并填充这三个字段.
`global_pfr` 通过 `builder.calculate_pfr(raw_stats)` 获取 (positive, total) 元组后安全换算: pfr = positive / total if total > 0 else 0.0. 注意: 此值必须基于 raw stats 计算.
`global_vpip` 通过 `player_stats.vpip.to_float()` 获取.

#### 2b. opponent_pipeline 混合逻辑

在 `_adjust_belief_with_stats_and_ev()` 中:

```python
# 原逻辑: target_frequency = stats_frequency (纯节点级)
# 新逻辑: 仅对 aggressive action 用 confidence 混合节点级 + 全局 PFR

if action_type in ("raise", "bet", "all_in"):
    node_confidence = node_stats.confidence
    global_signal = node_stats.global_pfr
    target_frequency = (
        node_confidence * stats_frequency
        + (1.0 - node_confidence) * global_signal
    )
else:
    # v1: fold/call 继续用节点级统计, 不做全局补偿
    target_frequency = stats_frequency
```

**效果**:

| 玩家 | global_pfr | node_confidence (假设) | stats_freq | target_freq |
|------|-----------|----------------------|------------|-------------|
| bcsilva | 0.168 | 0.33 | 0.25 | 0.33×0.25 + 0.67×0.168 = 0.195 |
| Ivan_87 | 0.546 | 0.37 | 0.27 | 0.37×0.27 + 0.63×0.546 = 0.444 |

两者产生显著不同的 target_frequency, 问题解决. v1 仅补偿 aggressive action, 后续版本可扩展到 fold/call.

## 不修改的文件

| 文件 | 原因 |
|------|------|
| `posterior.py` | 平滑算法本身正确, 问题在输入参数 |
| `hero_resolver.py` | 下游消费者, 上游修好后自然受益 |
| `models.py` | `PlayerStats`/`ActionStats` 结构不变 |

## 配置参数

所有新增参数集中在 `PlayerNodeStatsAdapterConfig`:

```python
@dataclass(frozen=True)
class PlayerNodeStatsAdapterConfig:
    pool_prior_strength: float = 20.0       # 基础先验强度(现有)
    confidence_k: float = 20.0              # confidence 计算参数(现有)
    adaptive_reference_hands: float = 200.0  # 新增: 手牌参考量
    adaptive_min_strength: float = 2.0       # 新增: 最小先验强度
    enable_global_raise_blending: bool = True  # 新增: 是否启用全局PFR补偿
```

## 测试策略

### 单元测试

1. `test_compute_adaptive_prior_strength`: 验证不同手牌量下返回正确的 k 值
2. `test_player_node_stats_global_fields`: 验证新字段正确填充
3. `test_global_pfr_blending`: 验证混合公式在各种 confidence 下的行为
4. `test_confidence_uses_raw_not_smoothed_samples`: 验证 confidence 基于 raw node samples 而非 smoothed pseudo-counts
5. `test_high_hands_sparse_node`: 高总手数(1000+)但目标节点稀疏(<5 samples)时的行为
6. `test_global_pfr_zero_denominator`: total=0 时 pfr fallback 为 0.0
7. `test_feature_flag_disabled_regression`: `enable_global_raise_blending=False` 时行为与旧逻辑完全一致

### 集成测试

8. `test_3bet_different_opponent_style_combos_produce_different_hero_strategy`: 验证 bcsilva 和 Ivan_87 现在产生**不同**的 posterior range, 验证不同 3bettor 风格确实影响 Hero 策略
9. `test_population_fallback_unchanged`: 无玩家数据时 population fallback 行为不变

### 回归测试

10. 确保 0 手牌玩家(纯 pool 先验)行为不变
11. 确保现有全部测试通过

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 修改平滑强度影响所有玩家 posterior | 全量回归测试 + min 限制 |
| reference_hands=200 可能不适合所有场景 | 参数化配置, 可通过 Config 调整 |
| 全局 PFR 作为节点级代理不够精确 | 仅在 confidence 低时使用, confidence 高时节点数据主导 |
| v1 仅补偿 aggressive action, 后续版本可扩展到 fold/call | 设计已明确 v1 范围, 后续迭代增加功能 |
