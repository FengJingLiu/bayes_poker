# Draft: Strategy Engine

## Requirements (confirmed)
- 开发一个 strategy_engine 模块，供server StrategyHandler使用。
- 先给我整体框架和逻辑，然后我来审核修改。

## Technical Decisions
- 当前阶段只做方案设计与调用链梳理，不做源码实现。
- 新模块需围绕 `ObservedTableState` 直接建模，避免继续依赖松散 payload dict。

## Research Findings
- `src/bayes_poker/comm/server.py`: `StrategyHandler` 已改为接收 `session_id` 与 `ObservedTableState`。
- `src/bayes_poker/strategy/runtime/preflop.py`: 现有 preflop runtime 已声明使用 `ObservedTableState` 作为输入状态格式，但基础类型仍停留在 payload dict。
- `src/bayes_poker/strategy/opponent_range/predictor.py`: 已存在独立对手范围预测能力，可作为 strategy_engine 内部依赖。

## Open Questions
- strategy_engine 是只封装 preflop，还是要预留 postflop 扩展骨架。
- server 是否继续持有 `range_predictor`，还是完全下沉到 strategy_engine 内部。
- 输出给 server 的响应是否继续沿用当前 `dict[str, Any]` 结构，还是引入内部 response 模型后再序列化。

## Scope Boundaries
- INCLUDE: strategy_engine 模块边界、组件职责、调用链、扩展点、测试思路。
- EXCLUDE: 具体代码实现、server/source 代码改动、全量运行时重写。
