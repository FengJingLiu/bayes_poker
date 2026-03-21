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
- `adjust_belief_range()`: 按目标频率与 EV 排序做约束式信念重分配
- `combo_weight()`: 计算 169 手牌在 1326 总组合中的权重
