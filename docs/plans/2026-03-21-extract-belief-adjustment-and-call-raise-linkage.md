
提取 Belief Adjustment 算法 & Call/Raise 联动 Implementation Plan

 For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement
 this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

Goal: 将 EV-ranked belief_range 重分配算法提取为 range/belief_adjustment.py 共享模块, 并在 _adjust_hero_policy 中实现 call belief_range 与 raise 
belief_range
同向联动调整.

Architecture: 当前 EV-ranked redistribution 算法在 opponent_pipeline.py 和 hero_resolver.py 中各有一份几乎相同的实现 
(_adjust_belief_with_stats_and_ev / 
_adjust_hero_belief_range), 以及相同的 _combo_weight 辅助函数. 提取为 range/belief_adjustment.py::adjust_belief_range() 纯函数, 
两个调用方改为薄包装. 新功能: 当 
aggression_ratio != 1.0 时, call (C/X) 动作的 belief_range 也用 aggression_ratio 同向缩放 — ratio>1 则 call 和 raise 的 range 都扩大, ratio<1 
则都缩小.

Tech Stack: Python 3.12, pytest, PreflopRange (169维策略向量)

------------------------------------------------------------------------------------------------------------------------------------------------

文件结构

┌──────────┬─────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
│ 操作     │ 文件路径                                                        │ 职责                                              │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 新建     │ src/bayes_poker/strategy/range/belief_adjustment.py             │ 纯函数 adjust_belief_range() + combo_weight()     │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 新建     │ tests/test_belief_adjustment.py                                 │ 新模块的单元测试                                  │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 修改     │ src/bayes_poker/strategy/range/__init__.py                      │ 导出新函数                                        │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 修改     │ src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py   │ 删除本地副本, 导入新模块                          │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 修改     │ src/bayes_poker/strategy/strategy_engine/hero_resolver.py       │ 删除本地副本, 导入新模块, 添加 call belief 联动   │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 修改     │ tests/test_strategy_engine_v2_hero_resolver.py                  │ 新增 call belief 联动测试                         │
├──────────┼─────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ 修改     │ src/bayes_poker/strategy/range/AGENTS.md                        │ 更新文档                                          │
└──────────┴─────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘

------------------------------------------------------------------------------------------------------------------------------------------------

Phase 1: 提取共享算法

Task 1: 新建 belief_adjustment.py 及单元测试

Files:

 - Create: src/bayes_poker/strategy/range/belief_adjustment.py
 - Create: tests/test_belief_adjustment.py
 - Modify: src/bayes_poker/strategy/range/__init__.py:6-41

背景知识: _combo_weight(index) 计算 169 手牌中第 index 个手牌在 1326 总组合中的权重 (对子=6/1326, 同花=4/1326, 非同花=12/1326). 
adjust_belief_range 按目标频率做 EV-ranked 重分配:
delta>0 从高 EV 到低 EV 逐步增加策略值, delta<0 从低 EV 到高 EV 逐步削减.

 - [ ]  Step 1: 编写失败测试

创建 tests/test_belief_adjustment.py:

 """belief_adjustment 模块单元测试."""
 
 from __future__ import annotations
 
 import pytest
 
 from bayes_poker.strategy.range import PreflopRange, RANGE_169_LENGTH
 from bayes_poker.strategy.range.belief_adjustment import (
     adjust_belief_range,
     combo_weight,
 )
 
 
 class TestComboWeight:
     """combo_weight 返回 169 手牌在 1326 总组合中的权重."""
 
     def test_pair_weight(self) -> None:
         """对子 (index=0, '22') 权重 = 6/1326."""
         w = combo_weight(0)
         assert w == pytest.approx(6 / 1326, rel=1e-6)
 
     def test_suited_weight(self) -> None:
         """同花 (index=2, '32s') 权重 = 4/1326."""
         w = combo_weight(2)
         assert w == pytest.approx(4 / 1326, rel=1e-6)
 
     def test_offsuit_weight(self) -> None:
         """非同花 (index=1, '32o') 权重 = 12/1326."""
         w = combo_weight(1)
         assert w == pytest.approx(12 / 1326, rel=1e-6)
 
 
 class TestAdjustBeliefRange:
     """adjust_belief_range 按目标频率与 EV 排序做约束式信念重分配."""
 
     def test_target_equals_current_no_change(self) -> None:
         """目标频率与当前频率相同时不调整."""
         br = PreflopRange(
             strategy=[0.5] * RANGE_169_LENGTH,
             evs=[float(i) for i in range(RANGE_169_LENGTH)],
         )
         current_freq = br.total_frequency()
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=current_freq,
         )
         for i in range(RANGE_169_LENGTH):
             assert result.strategy[i] == pytest.approx(0.5, abs=1e-6)
 
     def test_increase_target_adds_to_high_ev(self) -> None:
         """目标频率 > 当前频率时, 优先向高 EV 手牌增加频率."""
         evs = [float(i) for i in range(RANGE_169_LENGTH)]
         br = PreflopRange(
             strategy=[0.3] * RANGE_169_LENGTH,
             evs=evs,
         )
         current_freq = br.total_frequency()
         target = current_freq + 0.05
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=target,
         )
         assert result.strategy[168] > 0.3
         assert result.total_frequency() == pytest.approx(target, abs=1e-4)
 
     def test_decrease_target_removes_from_low_ev(self) -> None:
         """目标频率 < 当前频率时, 优先从低 EV 手牌削减频率."""
         evs = [float(i) for i in range(RANGE_169_LENGTH)]
         br = PreflopRange(
             strategy=[0.5] * RANGE_169_LENGTH,
             evs=evs,
         )
         current_freq = br.total_frequency()
         target = current_freq - 0.05
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=target,
         )
         assert result.strategy[0] < 0.5
         assert result.total_frequency() == pytest.approx(target, abs=1e-4)
 
     def test_all_zeros_stays_zero(self) -> None:
         """全零策略且目标为零时保持不变."""
         br = PreflopRange.zeros()
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=0.0,
         )
         assert all(v == 0.0 for v in result.strategy)
 
     def test_strategy_clamped_to_zero_one(self) -> None:
         """策略值始终在 [0, 1] 范围内."""
         br = PreflopRange(
             strategy=[0.9] * RANGE_169_LENGTH,
             evs=[float(i) for i in range(RANGE_169_LENGTH)],
         )
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=1.0,
         )
         assert all(0.0 <= v <= 1.0 + 1e-9 for v in result.strategy)
 
     def test_custom_threshold(self) -> None:
         """自定义 low_mass_threshold 参数."""
         br = PreflopRange(
             strategy=[0.5] * RANGE_169_LENGTH,
             evs=[float(i) for i in range(RANGE_169_LENGTH)],
         )
         current_freq = br.total_frequency()
         # delta 比 threshold 小, 应该不调整
         result = adjust_belief_range(
             belief_range=br,
             target_frequency=current_freq + 1e-6,
             low_mass_threshold=1e-3,
         )
         for i in range(RANGE_169_LENGTH):
             assert result.strategy[i] == pytest.approx(0.5, abs=1e-6)

 - [ ]  Step 2: 运行测试, 确认失败

 uv run pytest tests/test_belief_adjustment.py -v

Expected: FAIL — ModuleNotFoundError: No module named 'bayes_poker.strategy.range.belief_adjustment'

 - [ ]  Step 3: 实现 belief_adjustment.py

创建 src/bayes_poker/strategy/range/belief_adjustment.py:

 """EV-ranked belief range 重分配算法.
 
 提供基于 EV 排序的约束式信念重分配纯函数, 供 opponent_pipeline 和
 hero_resolver 共享使用.
 """
 
 from __future__ import annotations
 
 from bayes_poker.strategy.range.mappings import (
     RANGE_169_LENGTH,
     RANGE_169_ORDER,
     RANGE_1326_LENGTH,
     combos_per_hand,
 )
 from bayes_poker.strategy.range.models import PreflopRange
 
 _DEFAULT_LOW_MASS_THRESHOLD = 1e-9
 
 
 def combo_weight(index: int) -> float:
     """返回某 169 手牌在总频率中的组合权重.
 
     Args:
         index: 169 维手牌索引.
 
     Returns:
         该手牌的组合数 / 1326.
     """
     return combos_per_hand(RANGE_169_ORDER[index]) / RANGE_1326_LENGTH
 
 
 def adjust_belief_range(
     *,
     belief_range: PreflopRange,
     target_frequency: float,
     low_mass_threshold: float = _DEFAULT_LOW_MASS_THRESHOLD,
 ) -> PreflopRange:
     """按目标频率与 EV 排序做约束式信念重分配.
 
     - delta > 0: 按 EV 从高到低增加频率 (优先加强手牌).
     - delta < 0: 按 EV 从低到高削减频率 (优先移除弱手牌).
 
     Args:
         belief_range: 原始 belief range (169 维).
         target_frequency: 调整后的目标总频率.
         low_mass_threshold: 低质量阈值, 差值小于此值时不调整.
 
     Returns:
         调整后的新 PreflopRange.
     """
     adjusted_strategy = [min(max(v, 0.0), 1.0) for v in belief_range.strategy]
     evs = list(belief_range.evs)
     weights = [combo_weight(i) for i in range(RANGE_169_LENGTH)]
 
     current_freq = sum(
         s * w for s, w in zip(adjusted_strategy, weights, strict=True)
     )
     delta = target_frequency - current_freq
     if abs(delta) <= low_mass_threshold:
         return PreflopRange(strategy=adjusted_strategy, evs=evs)
 
     if delta > 0.0:
         sorted_indices = sorted(
             range(RANGE_169_LENGTH),
             key=lambda idx: evs[idx],
             reverse=True,
         )
         for idx in sorted_indices:
             if delta <= low_mass_threshold:
                 break
             w = weights[idx]
             if w <= 0.0:
                 continue
             available = 1.0 - adjusted_strategy[idx]
             if available <= low_mass_threshold:
                 continue
             max_mass = available * w
             mass_to_add = min(delta, max_mass)
             adjusted_strategy[idx] += mass_to_add / w
             delta -= mass_to_add
     else:
         remaining = -delta
         sorted_indices = sorted(
             range(RANGE_169_LENGTH),
             key=lambda idx: evs[idx],
         )
         for idx in sorted_indices:
             if remaining <= low_mass_threshold:
                 break
             w = weights[idx]
             if w <= 0.0:
                 continue
             available = adjusted_strategy[idx]
             if available <= low_mass_threshold:
                 continue
             max_mass = available * w
             mass_to_remove = min(remaining, max_mass)
             adjusted_strategy[idx] -= mass_to_remove / w
             remaining -= mass_to_remove
 
     return PreflopRange(strategy=adjusted_strategy, evs=evs)

 - [ ]  Step 4: 更新 __init__.py 导出

修改 src/bayes_poker/strategy/range/__init__.py, 在现有导入后追加:

 from bayes_poker.strategy.range.belief_adjustment import (
     adjust_belief_range,
     combo_weight,
 )

并在 __all__ 列表中追加:

     # belief adjustment
     "adjust_belief_range",
     "combo_weight",

 - [ ]  Step 5: 运行测试, 确认通过

 uv run pytest tests/test_belief_adjustment.py -v

Expected: 7 passed

 - [ ]  Step 6: 运行全量测试, 确认无回归

 uv run pytest -q

Expected: 全部 PASS

 - [ ]  Step 7: Commit

 git add src/bayes_poker/strategy/range/belief_adjustment.py \
        src/bayes_poker/strategy/range/__init__.py \
        tests/test_belief_adjustment.py
 git commit -m "feat(range): extract adjust_belief_range to shared module
 
 Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

------------------------------------------------------------------------------------------------------------------------------------------------

Phase 2: 替换调用方

Task 2: opponent_pipeline.py 改用共享模块

Files:

 - Modify: src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py:1-506
 - Test: tests/test_strategy_engine_v2_opponent_pipeline.py (现有测试不变)

背景: opponent_pipeline.py 中 _adjust_belief_with_stats_and_ev (L426-500) 和 _combo_weight (L503-506) 要改为调用共享模块. 
_adjust_belief_with_stats_and_ev
仍保留为本地函数 (因为它额外有 _stats_frequency_for_action_type 计算 target), 只是内部调用改为 adjust_belief_range().

 - [ ]  Step 1: 修改 opponent_pipeline.py 导入

在文件头部 from bayes_poker.strategy.range import (...) 块中追加:

 from bayes_poker.strategy.range.belief_adjustment import (
     adjust_belief_range,
     combo_weight as _combo_weight_shared,
 )

 - [ ]  Step 2: 替换 _adjust_belief_with_stats_and_ev 实现

将 L426-500 替换为:

 def _adjust_belief_with_stats_and_ev(
     *,
     prior: PreflopRange,
     observed_action_type: ActionType,
     node_stats: PlayerNodeStats,
 ) -> PreflopRange:
     """按 stats 目标频率与 EV 排序做约束式信念重分配.
 
     Args:
         prior: 该动作对应的先验范围.
         observed_action_type: 真实观测动作类型.
         node_stats: 平滑后的节点统计概率.
 
     Returns:
         调整后的后验范围.
     """
     target_frequency = _stats_frequency_for_action_type(
         observed_action_type=observed_action_type,
         node_stats=node_stats,
     )
     target_frequency = min(max(target_frequency, 0.0), 1.0)
     return adjust_belief_range(
         belief_range=prior,
         target_frequency=target_frequency,
         low_mass_threshold=_BELIEF_LOW_MASS_THRESHOLD,
     )

 - [ ]  Step 3: 删除旧的 _combo_weight 函数

删除 opponent_pipeline.py 中 L503-506 的 _combo_weight 函数定义. 搜索文件内所有 _combo_weight( 调用 — 替换后应该已不再有直接引用 (它只被旧的 
_adjust_belief_with_stats_and_ev 内部使用).

 - [ ]  Step 4: 移除不再需要的 range 导入

从 opponent_pipeline.py 头部的 from bayes_poker.strategy.range import (...) 块中移除不再直接使用的符号:

 - RANGE_169_ORDER — 不再直接使用 (只通过 adjust_belief_range 间接使用)
 - RANGE_1326_LENGTH — 不再直接使用
 - combos_per_hand — 不再直接使用

保留 RANGE_169_LENGTH 和 PreflopRange (文件其他位置仍在使用).

注意: 先搜索确认这些符号在文件中除了被删除的函数外没有其他引用, 再移除.

 - [ ]  Step 5: 运行现有测试, 确认无回归

 uv run pytest tests/test_strategy_engine_v2_opponent_pipeline.py -v

Expected: 全部 PASS, 无变化

 - [ ]  Step 6: 运行全量测试

 uv run pytest -q

Expected: 全部 PASS

 - [ ]  Step 7: Commit

 git add src/bayes_poker/strategy/strategy_engine/opponent_pipeline.py
 git commit -m "refactor(opponent_pipeline): delegate to shared adjust_belief_range
 
 Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

------------------------------------------------------------------------------------------------------------------------------------------------

Task 3: hero_resolver.py 改用共享模块

Files:

 - Modify: src/bayes_poker/strategy/strategy_engine/hero_resolver.py:1-706
 - Test: tests/test_strategy_engine_v2_hero_resolver.py (现有测试不变)

背景: hero_resolver.py 中 _adjust_hero_belief_range (L523-591) 和 _combo_weight (L518-520) 要改为调用共享模块. _adjust_hero_belief_range 
是纯包装, 直接替换为 
adjust_belief_range 导入.

 - [ ]  Step 1: 修改 hero_resolver.py 导入

在文件头部 from bayes_poker.strategy.range import (...) 块中追加:

 from bayes_poker.strategy.range.belief_adjustment import adjust_belief_range

 - [ ]  Step 2: 删除 _combo_weight 和 _adjust_hero_belief_range

删除 L518-591 (_combo_weight + _adjust_hero_belief_range 两个函数).

 - [ ]  Step 3: 更新 _adjust_hero_policy 中对 _adjust_hero_belief_range 的调用

将 L660 的:

 new_belief = _adjust_hero_belief_range(
     belief_range=action.belief_range,
     target_frequency=new_target,
 )

替换为:

 new_belief = adjust_belief_range(
     belief_range=action.belief_range,
     target_frequency=new_target,
     low_mass_threshold=_HERO_ADJUST_LOW_MASS_THRESHOLD,
 )

 - [ ]  Step 4: 移除不再需要的 range 导入

从 hero_resolver.py 头部的 from bayes_poker.strategy.range import (...) 块中移除不再直接使用的符号:

 - RANGE_169_ORDER — 不再直接使用
 - RANGE_1326_LENGTH — 不再直接使用
 - combos_per_hand — 不再直接使用

保留 RANGE_169_LENGTH 和 PreflopRange (文件其他位置仍在使用).

注意: 先搜索确认这些符号在文件中除了被删除的函数外没有其他引用, 再移除.

 - [ ]  Step 5: 更新测试文件导入

修改 tests/test_strategy_engine_v2_hero_resolver.py L27:

将:

 from bayes_poker.strategy.strategy_engine.hero_resolver import (
     HeroGtoResolver,
     _adjust_hero_belief_range,
     _adjust_hero_policy,
     _compute_opponent_aggression_ratio,
     _is_aggressive_action,
 )

替换为:

 from bayes_poker.strategy.range.belief_adjustment import adjust_belief_range
 from bayes_poker.strategy.strategy_engine.hero_resolver import (
     HeroGtoResolver,
     _adjust_hero_policy,
     _compute_opponent_aggression_ratio,
     _is_aggressive_action,
 )

然后将测试类 TestAdjustHeroBeliefRange 中所有 _adjust_hero_belief_range( 调用替换为 adjust_belief_range(. 这些调用在:

 - L1081: result = _adjust_hero_belief_range(
 - L1097: result = _adjust_hero_belief_range(
 - L1115: result = _adjust_hero_belief_range(
 - L1127: result = _adjust_hero_belief_range(
 - [ ] 
 
 Step 6: 运行现有测试, 确认无回归

 uv run pytest tests/test_strategy_engine_v2_hero_resolver.py -v

Expected: 全部 PASS

 - [ ]  Step 7: 运行全量测试

 uv run pytest -q

Expected: 全部 PASS

 - [ ]  Step 8: Commit

 git add src/bayes_poker/strategy/strategy_engine/hero_resolver.py \
        tests/test_strategy_engine_v2_hero_resolver.py
 git commit -m "refactor(hero_resolver): delegate to shared adjust_belief_range
 
 Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

------------------------------------------------------------------------------------------------------------------------------------------------

Phase 3: Call Belief Range 联动

Task 4: _adjust_hero_policy 添加 call belief_range 同向调整

Files:

 - Modify: src/bayes_poker/strategy/strategy_engine/hero_resolver.py (_adjust_hero_policy 被动分支 + 新增 _is_call_action helper)
 - Modify: tests/test_strategy_engine_v2_hero_resolver.py (新增测试类)

背景: 当前 _adjust_hero_policy 对被动动作 (F/C) 只调整 blended_frequency, 不调整 belief_range. 新需求:

 - ratio > 1 (对手弱): hero raise range 扩大, 同时 call range 也扩大 (fold→call 升级)
 - ratio < 1 (对手强): hero raise range 缩小, 同时 call range 也缩小 (call→fold 降级)
 - 使用 aggression_ratio (不是 pass_scale) 作为 call belief_range 的缩放因子, 因为 call 和 raise 同向变化
 - 只影响 call (C) 和 check (X) 动作, 不影响 fold (F) 动作
 - [ ] 
 
 Step 1: 编写失败测试

在 tests/test_strategy_engine_v2_hero_resolver.py 文件末尾 (在现有 TestAdjustHeroPolicy 类之后, 
test_hero_resolve_with_aggressive_opponent_adjusts_notes 之前)
添加辅助函数和新测试类:

 def _make_frc_policy(
     *,
     fold_freq: float = 0.3,
     call_freq: float = 0.3,
     raise_freq: float = 0.4,
     call_belief: PreflopRange | None = None,
     raise_belief: PreflopRange | None = None,
 ) -> GtoPriorPolicy:
     """构造包含 F/C/R 三个动作的 policy.
 
     Args:
         fold_freq: fold 频率.
         call_freq: call 频率.
         raise_freq: raise 频率.
         call_belief: call 的 belief range.
         raise_belief: raise 的 belief range.
 
     Returns:
         GtoPriorPolicy 实例.
     """
     fold_action = GtoPriorAction(
         action_name="F",
         blended_frequency=fold_freq,
         belief_range=None,
         total_ev=-1.0,
     )
     call_action = GtoPriorAction(
         action_name="C",
         blended_frequency=call_freq,
         belief_range=call_belief,
         total_ev=0.5,
     )
     raise_action = GtoPriorAction(
         action_name="R2.5",
         blended_frequency=raise_freq,
         belief_range=raise_belief,
         total_ev=2.0,
     )
     return GtoPriorPolicy(
         action_names=("R2.5", "C", "F"),
         actions=(fold_action, call_action, raise_action),
     )
 
 
 class TestAdjustHeroPolicyCallBeliefLinkage:
     """_adjust_hero_policy 中 call belief_range 与 aggression_ratio 同向联动."""
 
     def _make_belief(self, base_strategy: float = 0.4) -> PreflopRange:
         """创建带 EV 梯度的 belief range."""
         return PreflopRange(
             strategy=[base_strategy] * RANGE_169_LENGTH,
             evs=[float(i) for i in range(RANGE_169_LENGTH)],
         )
 
     def test_ratio_gt1_call_belief_expands(self) -> None:
         """ratio > 1 时 call belief_range 总频率应增大 (fold→call 升级)."""
         call_belief = self._make_belief(0.4)
         raise_belief = self._make_belief(0.3)
         original_call_freq = call_belief.total_frequency()
 
         policy = _make_frc_policy(
             fold_freq=0.3,
             call_freq=0.3,
             raise_freq=0.4,
             call_belief=call_belief,
             raise_belief=raise_belief,
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
 
         call_action = next(a for a in result.actions if a.action_name == "C")
         assert call_action.belief_range is not None
         new_call_freq = call_action.belief_range.total_frequency()
         assert new_call_freq > original_call_freq
 
     def test_ratio_lt1_call_belief_shrinks(self) -> None:
         """ratio < 1 时 call belief_range 总频率应减小 (call→fold 降级)."""
         call_belief = self._make_belief(0.4)
         raise_belief = self._make_belief(0.3)
         original_call_freq = call_belief.total_frequency()
 
         policy = _make_frc_policy(
             fold_freq=0.3,
             call_freq=0.3,
             raise_freq=0.4,
             call_belief=call_belief,
             raise_belief=raise_belief,
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=0.5)
 
         call_action = next(a for a in result.actions if a.action_name == "C")
         assert call_action.belief_range is not None
         new_call_freq = call_action.belief_range.total_frequency()
         assert new_call_freq < original_call_freq
 
     def test_ratio_one_call_belief_unchanged(self) -> None:
         """ratio = 1.0 时 policy 原样返回, call belief 不变."""
         call_belief = self._make_belief(0.4)
         policy = _make_frc_policy(
             call_freq=0.3,
             raise_freq=0.4,
             call_belief=call_belief,
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=1.0)
         assert result is policy  # 原对象返回
 
     def test_call_no_belief_range_passthrough(self) -> None:
         """call 动作没有 belief_range 时, 不报错, belief_range 保持 None."""
         policy = _make_frc_policy(
             call_freq=0.3,
             raise_freq=0.4,
             call_belief=None,
             raise_belief=None,
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
         call_action = next(a for a in result.actions if a.action_name == "C")
         assert call_action.belief_range is None
 
     def test_fold_belief_not_adjusted(self) -> None:
         """F 动作的 belief_range 不受联动影响, 仍然直接透传."""
         fold_belief = self._make_belief(0.5)
         fold_action = GtoPriorAction(
             action_name="F",
             blended_frequency=0.3,
             belief_range=fold_belief,
             total_ev=-1.0,
         )
         call_action = GtoPriorAction(
             action_name="C",
             blended_frequency=0.3,
             belief_range=self._make_belief(0.4),
             total_ev=0.5,
         )
         raise_action = GtoPriorAction(
             action_name="R2.5",
             blended_frequency=0.4,
             belief_range=self._make_belief(0.3),
             total_ev=2.0,
         )
         policy = GtoPriorPolicy(
             action_names=("R2.5", "C", "F"),
             actions=(fold_action, call_action, raise_action),
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
         fold_result = next(a for a in result.actions if a.action_name == "F")
         # fold 的 belief_range 应原样透传
         assert fold_result.belief_range is fold_belief
 
     def test_check_action_also_adjusted(self) -> None:
         """X (check) 动作也属于 call 类, belief_range 应被调整."""
         check_belief = self._make_belief(0.4)
         original_freq = check_belief.total_frequency()
 
         check_action = GtoPriorAction(
             action_name="X",
             blended_frequency=0.3,
             belief_range=check_belief,
             total_ev=0.2,
         )
         raise_action = GtoPriorAction(
             action_name="R2.5",
             blended_frequency=0.7,
             belief_range=self._make_belief(0.3),
             total_ev=2.0,
         )
         policy = GtoPriorPolicy(
             action_names=("R2.5", "X"),
             actions=(check_action, raise_action),
         )
         result = _adjust_hero_policy(policy=policy, aggression_ratio=1.5)
         check_result = next(a for a in result.actions if a.action_name == "X")
         assert check_result.belief_range is not None
         assert check_result.belief_range.total_frequency() > original_freq
 
     def test_frequencies_still_sum_to_one(self) -> None:
         """带 call belief 联动后, blended_frequency 总和仍为 1.0."""
         policy = _make_frc_policy(
             fold_freq=0.3,
             call_freq=0.3,
             raise_freq=0.4,
             call_belief=self._make_belief(0.4),
             raise_belief=self._make_belief(0.3),
         )
         for ratio in [0.2, 0.5, 0.8, 1.5, 2.0, 3.0]:
             result = _adjust_hero_policy(policy=policy, aggression_ratio=ratio)
             total = sum(a.blended_frequency for a in result.actions)
             assert total == pytest.approx(1.0, abs=1e-6), f"ratio={ratio}"

还需在测试文件头部确认已导入 _is_call_action (如果作为公开 helper 导出的话). 不过 _is_call_action 是内部函数, 测试通过 _adjust_hero_policy 
间接覆盖即可.

 - [ ]  Step 2: 运行测试, 确认失败

 uv run pytest tests/test_strategy_engine_v2_hero_resolver.py::TestAdjustHeroPolicyCallBeliefLinkage -v

Expected: FAIL — call belief_range 没有被调整 (当前实现直接透传)

 - [ ]  Step 3: 实现 _is_call_action helper

在 hero_resolver.py 的 _is_aggressive_action 函数 (L421-431) 之后添加:

 def _is_call_action(action_name: str) -> bool:
     """判断动作编码是否属于 call/check 类 (非 fold 的被动动作).
 
     Args:
         action_name: 动作编码, 如 'C', 'X', 'F'.
 
     Returns:
         是否为 call/check 动作.
     """
     normalized = action_name.upper()
     return normalized in {"C", "X"}

 - [ ]  Step 4: 修改 _adjust_hero_policy 被动分支

将 _adjust_hero_policy 中 L681-697 的 else 分支:

         else:
             new_freq = action.blended_frequency * pass_scale
             adjusted_actions.append(
                 GtoPriorAction(
                     action_name=action.action_name,
                     blended_frequency=new_freq,
                     source_id=action.source_id,
                     node_id=action.node_id,
                     action_type=action.action_type,
                     bet_size_bb=action.bet_size_bb,
                     is_all_in=action.is_all_in,
                     next_position=action.next_position,
                     belief_range=action.belief_range,
                     total_ev=action.total_ev,
                     total_combos=action.total_combos,
                 )
             )

替换为:

         else:
             new_freq = action.blended_frequency * pass_scale
             new_belief = action.belief_range
             if (
                 _is_call_action(action.action_name)
                 and action.belief_range is not None
             ):
                 old_total = action.belief_range.total_frequency()
                 call_target = old_total * aggression_ratio
                 call_target = min(max(call_target, 0.0), 1.0)
                 new_belief = adjust_belief_range(
                     belief_range=action.belief_range,
                     target_frequency=call_target,
                     low_mass_threshold=_HERO_ADJUST_LOW_MASS_THRESHOLD,
                 )
             adjusted_actions.append(
                 GtoPriorAction(
                     action_name=action.action_name,
                     blended_frequency=new_freq,
                     source_id=action.source_id,
                     node_id=action.node_id,
                     action_type=action.action_type,
                     bet_size_bb=action.bet_size_bb,
                     is_all_in=action.is_all_in,
                     next_position=action.next_position,
                     belief_range=new_belief,
                     total_ev=action.total_ev,
                     total_combos=action.total_combos,
                 )
             )

关键设计点: call belief_range 使用 aggression_ratio (不是 pass_scale) 缩放 old_total, 因为:

 - pass_scale 方向相反 (ratio>1 → pass_scale<1)
 - 需求是 call 和 raise 同向变化: ratio>1 → 两者都扩大
 - [ ] 
 
 Step 5: 运行新测试, 确认通过

 uv run pytest tests/test_strategy_engine_v2_hero_resolver.py::TestAdjustHeroPolicyCallBeliefLinkage -v

Expected: 7 passed

 - [ ]  Step 6: 运行全量 hero_resolver 测试, 确认无回归

 uv run pytest tests/test_strategy_engine_v2_hero_resolver.py -v

Expected: 全部 PASS (新测试 + 旧测试)

 - [ ]  Step 7: 运行全量测试

 uv run pytest -q

Expected: 全部 PASS

 - [ ]  Step 8: Commit

 git add src/bayes_poker/strategy/strategy_engine/hero_resolver.py \
        tests/test_strategy_engine_v2_hero_resolver.py
 git commit -m "feat(hero_resolver): link call belief_range with aggression_ratio
 
 ratio > 1 (weak opponents): both raise and call belief ranges expand
 ratio < 1 (strong opponents): both raise and call belief ranges shrink
 fold belief_range is not affected (passthrough)
 
 Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

------------------------------------------------------------------------------------------------------------------------------------------------

Phase 4: 文档更新

Task 5: 更新 AGENTS.md

Files:

 - Modify: src/bayes_poker/strategy/range/AGENTS.md
 - [ ] 
 
 Step 1: 更新 AGENTS.md

将 src/bayes_poker/strategy/range/AGENTS.md 的文件表格更新, 添加 belief_adjustment.py 行:

 # Range 子模块
 
 范围模型、映射与信念重分配算法。
 
 ## 文件
 
 | 文件 | 行数 | 功能 |
 |------|------|------|
 | models.py | 362 | 范围数据模型 |
 | mappings.py | 402 | 范围映射逻辑 |
 | belief_adjustment.py | ~100 | EV-ranked belief range 重分配算法 |
 | __init__.py | ~50 | 模块导出 |
 
 ## 核心类型
 
 - `PreflopRange`: 169 维翻前策略范围
 - `PostflopRange`: 1326 维翻后策略范围
 - `adjust_belief_range()`: 按目标频率与 EV 排序做约束式信念重分配 (纯函数)
 - `combo_weight()`: 计算 169 手牌在 1326 总组合中的权重

 - [ ]  Step 2: Commit

 git add src/bayes_poker/strategy/range/AGENTS.md
 git commit -m "docs(range): update AGENTS.md with belief_adjustment module
 
 Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"

------------------------------------------------------------------------------------------------------------------------------------------------

风险与缓解

┌─────────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┐
│ 风险                                                                            │ 缓解                                                    │
├─────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ opponent_pipeline.py 中 RANGE_169_ORDER 等符号在被删函数之外也被使用            │ Step 4 要求先搜索确认再删除                             │
├─────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ _BELIEF_LOW_MASS_THRESHOLD vs _HERO_ADJUST_LOW_MASS_THRESHOLD 值不同            │ 新模块参数化 low_mass_threshold, 各调用方传自己的阈值   │
├─────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ call belief 联动在极端 ratio 下可能产生 >1.0 的 target                          │ 已加 min(max(..., 0.0), 1.0) clamp                      │
├─────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ 现有 TestAdjustHeroPolicy 测试中 _make_simple_policy 只有 F+R, 无 call 动作     │ 新增 _make_frc_policy 和独立测试类, 不影响旧测试        │
└─────────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────┘

成功标准

 - [ ]  adjust_belief_range 在 range/belief_adjustment.py 中, 有独立单元测试
 - [ ]  opponent_pipeline.py 和 hero_resolver.py 无本地副本, 导入共享模块
 - [ ]  call/check 动作的 belief_range 随 aggression_ratio 同向缩放
 - [ ]  fold 动作的 belief_range 不受影响
 - [ ]  全量测试通过, 无回归
 - [ ]  每个 phase 有独立 commit