# 模块指南: `player_metrics`

> **注意**: 本模块为扑克统计与对手分析的核心模块，部分数据密集型逻辑使用了 Rust 后端加速。

## 概览

`player_metrics` 模块的主要职责是从手牌历史数据（Hand History）中解析、提取、构建并输出玩家的历史动作偏好统计（Stats）。这些统计指标包含了经典的总体指标（VPIP、PFR、Aggression、WTP），更重要的是，它将玩家动作精细地切分并映射到了数以千计的特定博弈决策节点上，为 `strategy/`（策略引擎）阶段进行**剥削性后验范围推断（Opponent Pipeline）**提供了客观的频率分布依据。

## 核心职责

1. **多维度动作统计 (Stats Building)**:
   - 解析每手牌每个街道的具体操作，提取底池大小、下注尺寸、玩家位置等信息。
   - 对翻前（Preflop）和翻后（Postflop）的各种复杂场景进行标准化参数化编目（Parametrization）。
2. **性能基建 (Rust Acceleration)**:
   - 依赖外部的 Rust 工程（`poker_stats_rs`）进行海量历史手牌的并发加载、解析与 SQLite 落盘提取，极大提效。 
3. **统计建模支持**:
   - 为下游策略模块提供稳定的玩家动作频数与节点统计基础数据。

## 关键文件结构

- **基础与定义**:
  - `enums.py`: 数据模型枚举，包含动作类型、位置、街等定义。
  - `models.py`: 负责承载玩家统计数据结构的容器模型，如 `PlayerStats` 树与 `ActionStats`。
  - `params.py`: **非常重要**；通过 `PreFlopParams` 和 `PostFlopParams` 提供博弈树状态节点的编码、解码映射体系。 
- **构建解析**:
  - `builder.py`: Python 侧核心手牌动作流提取器逻辑。从 PokerKit 解析的手牌树中逐条获取状态并打入节点的统计累加器。
- **接口与工具**:
  - `rust_api.py`: 提供 Python 层对 Rust 高性能批量解析器和 SQLite 的简便调用接口。
  - `serialization.py`: 模型的序列化保存配置与功能支持。
  - `analysis_helpers.py`: 提供探索、数据验证和指标输出图表相关的可视化功能与辅助统计。
  - `core_stats_csv.py`: 导出 VPIP/PFR/WTP/AGG/总手数到 CSV 的标准化工具, 复用 `builder.py` 统一口径。

## 新增导出/验证脚本（与本模块相关）

- `scripts/export_player_core_stats_csv.py`:
  - 从 `data/database/player_stats.db` 读取玩家统计。
  - 导出 `player_core_stats.csv`（含 `vpip/pfr/wtp/agg/total_hands`、百分比与分子分母）。
- `scripts/validate_utg_open_ev_adjustment.py`:
  - 基于 `player_core_stats.csv` 选取 VPIP/PFR 差异大的玩家。
  - 在 `strategy_engine` 的 UTG open 节点上执行 EV 调整验证并导出 `to_gtoplus` 文件。

## 开发与修改建议

1. **不可变数据倾向**: 大多数的统计结果返回时应当成不可变配置来处理，尤其是引擎依赖的 `PlayerStats` 读取结果，不允许被业务擅自变动。
2. **Rust与Python的边界**: 若涉及针对上亿手数据的重新建模计算或者是解析提速，请在配套的 Rust 端 `poker_stats_rs` 内修改或提 PR；Python 侧优先保持读取、分析和导出逻辑清晰。
