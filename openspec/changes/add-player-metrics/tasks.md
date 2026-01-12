# Tasks: 添加玩家指标构建模块

## 1. 基础设施

- [x] 1.1 创建 `src/bayes_poker/player_metrics/__init__.py` 模块入口
- [x] 1.2 创建 `src/bayes_poker/player_metrics/enums.py` 定义枚举类型

## 2. 核心数据模型

- [x] 2.1 实现 `StatValue` dataclass（positive/total 计数器）
- [x] 2.2 实现 `ActionStats` dataclass（三态动作分布）
- [x] 2.3 实现 `PlayerStats` dataclass（玩家统计容器）

## 3. 情境参数

- [x] 3.1 实现 `PreFlopParams` dataclass（翻前情境维度）
- [x] 3.2 实现 `PreFlopParams.to_index()` 索引计算
- [x] 3.3 实现 `PreFlopParams.get_all_params()` 生成所有情境
- [x] 3.4 实现 `PostFlopParams` dataclass（翻后情境维度）
- [x] 3.5 实现 `PostFlopParams.to_index()` 索引计算
- [x] 3.6 实现 `PostFlopParams.get_all_params()` 生成所有情境

## 4. 手牌重放与动作提取

- [x] 4.1 实现 `extract_actions_from_hand_history()` 从 PHHS 提取动作流
- [x] 4.2 实现位置计算逻辑 `get_player_position()`
- [x] 4.3 实现 in-position 判断逻辑 `is_in_position()`

## 5. 统计构建器

- [x] 5.1 实现 `PlayerStats.increment(hand_history)` 增量更新方法
- [x] 5.2 实现 `build_player_stats_from_hands()` 批量构建函数
- [x] 5.3 实现顶层指标计算：`calculate_vpip()`, `calculate_pfr()`, `calculate_aggression()`, `calculate_wtp()`

## 6. 测试

- [x] 6.1 创建 `tests/test_player_metrics.py` 测试文件
- [x] 6.2 添加 `StatValue` 单元测试
- [x] 6.3 添加 `ActionStats` 单元测试
- [x] 6.4 添加 `PreFlopParams.to_index()` 边界测试
- [x] 6.5 添加 `PostFlopParams.to_index()` 边界测试
- [x] 6.6 添加 `PlayerStats.increment()` 集成测试（使用真实 PHHS 数据）
- [x] 6.7 添加顶层指标计算测试

## 7. 文档与导出

- [x] 7.1 在 `__init__.py` 中导出公开 API
- [x] 7.2 为公开函数添加 docstring

## Dependencies

- 任务 2.x 依赖 1.x 完成
- 任务 3.x 依赖 2.x 完成
- 任务 4.x 依赖 1.x 和 3.x 完成
- 任务 5.x 依赖 2.x、3.x、4.x 完成
- 任务 6.x 依赖对应功能模块完成
- 任务 7.x 在所有功能完成后执行

## Parallelizable Work

- 任务 3.1-3.3（PreFlop）和 3.4-3.6（PostFlop）可并行
- 任务 6.2-6.5（单元测试）可并行编写

## Verification

- ✅ 30 个单元测试全部通过
- ✅ Python 编译验证通过（无语法错误）
- ✅ 模块可正常导入
