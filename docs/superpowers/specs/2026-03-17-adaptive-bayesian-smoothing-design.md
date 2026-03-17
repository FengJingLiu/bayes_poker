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
  stats_adapter计算adaptive_k → repo.get(k=adaptive_k) → smoothed_stats
  → stats_adapter(附加global_pfr/vpip) → node_stats(含confidence+全局信号)
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
    max_strength: float = 40.0,
    reference_hands: float = 200.0,
) -> float:
    """根据玩家全局手牌量自适应调整 pool_prior_strength.

    全局手牌多 → 信任玩家数据 → 降低 prior_strength.
    全局手牌少 → 不确定性高 → 保持较高 prior_strength.

    Args:
        player_stats: 玩家统计数据.
        base_strength: 基础先验强度, 默认 20.0.
        min_strength: 最小先验强度下界, 默认 2.0.
        max_strength: 最大先验强度上界, 默认 40.0.
        reference_hands: 参考手牌数, 达到此数时 k 减半, 默认 200.

    Returns:
        自适应调整后的 pool_prior_strength.
    """
    total_hands = player_stats.vpip.total
    adaptive_k = base_strength / (1.0 + total_hands / reference_hands)
    return max(min_strength, min(max_strength, adaptive_k))
```

**参数行为**:

| total_hands | adaptive_k | 含义 |
|-------------|-----------|------|
| 0           | 20.0      | 完全依赖 pool 先验 |
| 100         | 13.3      | 先验开始减弱 |
| 200         | 10.0      | 先验强度减半 |
| 500         | 5.7       | 玩家数据占主导 |
| 1000        | 3.3       | 接近最小值 |

**修改流程**: `load()` 方法改为两步:

1. 先获取 raw `PlayerStats`(不平滑, `smooth_with_pool=False`)
2. 计算 `adaptive_k = _compute_adaptive_prior_strength(raw_stats)`
3. 再获取平滑后的 `PlayerStats`(使用 `pool_prior_strength=adaptive_k`)

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
`global_pfr` 通过 `builder.calculate_pfr(player_stats)` 获取.
`global_vpip` 通过 `player_stats.vpip.to_float()` 获取.

#### 2b. opponent_pipeline 混合逻辑

在 `_adjust_belief_with_stats_and_ev()` 中:

```python
# 原逻辑: target_frequency = stats_frequency (纯节点级)
# 新逻辑: 用 confidence 混合节点级 + 全局信号

node_confidence = node_stats.confidence

if action_type == "raise":
    global_signal = node_stats.global_pfr
elif action_type == "fold":
    global_signal = 1.0 - node_stats.global_vpip
else:  # call
    global_signal = node_stats.global_vpip - node_stats.global_pfr

# 确保 global_signal 非负
global_signal = max(0.0, global_signal)

target_frequency = (
    node_confidence * stats_frequency
    + (1.0 - node_confidence) * global_signal
)
```

**效果**:

| 玩家 | global_pfr | node_confidence (假设) | stats_freq | target_freq |
|------|-----------|----------------------|------------|-------------|
| bcsilva | 0.168 | 0.33 | 0.25 | 0.33×0.25 + 0.67×0.168 = 0.195 |
| Ivan_87 | 0.546 | 0.37 | 0.27 | 0.37×0.27 + 0.63×0.546 = 0.444 |

两者产生显著不同的 target_frequency, 问题解决.

## 不修改的文件

| 文件 | 原因 |
|------|------|
| `posterior.py` | 平滑算法本身正确, 问题在输入参数 |
| `player_stats_repository.py` | 已支持动态 `pool_prior_strength` 参数 |
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
    adaptive_max_strength: float = 40.0      # 新增: 最大先验强度
    use_global_pfr_补偿: bool = True         # 新增: 是否启用全局PFR补偿
```

## 测试策略

### 单元测试

1. `test_compute_adaptive_prior_strength`: 验证不同手牌量下返回正确的 k 值
2. `test_player_node_stats_global_fields`: 验证新字段正确填充
3. `test_global_pfr_blending`: 验证混合公式在各种 confidence 下的行为

### 集成测试

4. **修改现有测试**: `test_3bet_different_opponent_style_combos_produce_different_hero_strategy`
   - 验证 bcsilva 和 Ivan_87 现在产生**不同**的 posterior range
   - 验证不同 3bettor 风格确实影响 Hero 策略

### 回归测试

5. 确保 0 手牌玩家(纯 pool 先验)行为不变
6. 确保现有全部测试通过

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 修改平滑强度影响所有玩家 posterior | 全量回归测试 + min/max 限制 |
| reference_hands=200 可能不适合所有场景 | 参数化配置, 可通过 Config 调整 |
| 全局 PFR 作为节点级代理不够精确 | 仅在 confidence 低时使用, confidence 高时节点数据主导 |
| call 的全局信号 (VPIP-PFR) 可能为负 | 用 `max(0.0, ...)` 兜底 |
