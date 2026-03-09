# Preflop Engine 子模块

翻前推理内核。

## 文件

| 文件 | 行数 | 功能 |
|------|------|------|
| hero_engine.py | 467 | Hero 决策引擎 |
| policy_calibrator.py | 563 | 策略校准器 |
| mapper.py | 249 | 范围映射 |
| solver_prior.py | 226 | 先验求解器 |
| tendency.py | 173 | 倾向计算 |
| range_engine.py | 126 | 范围引擎 |
| state.py | 150 | 状态管理 |
| explain.py | 42 | 解释器 |

## 核心类

- `HeroEngine`: 翻前决策主引擎
- `PolicyCalibrator`: 策略参数校准
- `Tendency`: 玩家倾向分析

## 依赖

- `pokerkit`: 扑克逻辑
- `preflop_parse`: 策略加载
