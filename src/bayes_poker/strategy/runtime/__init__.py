"""实时策略执行（runtime）。

与 `bayes_poker.strategy.preflop_parse`（策略文件解析/查询）区分：本包面向 server 的实时决策，
用于实现可注册到 `StrategyDispatcher` 的 preflop/postflop 策略处理器。
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. WebSocket Client 发送 STRATEGY_REQUEST 消息                              │
│     payload: { phh_data: "PHH格式字符串", state_version: 1, hero_index: 2 }   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. server.py: _message_loop() 接收消息                                      │
│     - JSON 解析 → MessageEnvelope                                           │
│     - 调用 _route_message()                                                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. server.py: _route_message() 路由到 _handle_strategy_request()           │
│     - 基于 msg.type == MessageType.STRATEGY_REQUEST                         │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. server.py: _handle_strategy_request() (L384-423)                        │
│     - 调用 self._strategy_handler(session_id, msg.payload)                  │
│     - 计算处理时间，封装响应                                                    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. engine.py: StrategyDispatcher.handle() (L90-146)                        │
│     - 从 payload 提取 phh_data                                              │
│     - 调用 phh_to_state(phh_data) 反序列化为 pokerkit State                   │
│     - 调用 extract_state_info() 提取 street/pot/board/stacks 等              │
│     - 构建 enriched_payload (添加 pokerkit_state, hand_history 等)           │
│     - 根据 street 路由到 preflop_strategy 或 postflop_strategy               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           │ street == "preflop"                       │ street != "preflop"
           ▼                                           ▼
┌──────────────────────────┐              ┌──────────────────────────┐
│  6a. preflop.py:         │              │  6b. postflop handler    │
│  PreflopRuntime.decide() │              │  (暂未实现)               │
└────────────┬─────────────┘              └──────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. preflop.py: decide() 内部处理                                            │
│     - 调用 extract_preflop_info(pokerkit_state, hand_history, hero_index)   │
│       从 State 提取: stack_bb, hero_cards, history, hero_position            │
│     - 调用 infer_preflop_layer(history) 判断分层 (RFI/3Bet/4Bet)             │
│     - 调用 _decide_rfi / _decide_3bet / _decide_4bet 等具体策略               │
│     - 返回策略响应                                                           │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8. 响应返回                                                                 │
│     { recommended_action: "R2", recommended_amount: 2.0, confidence: 0.8 }  │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from bayes_poker.strategy.runtime.postflop import create_postflop_strategy
from bayes_poker.strategy.runtime.preflop import (
    PreflopLayer,
    PreflopRuntimeConfig,
    create_preflop_strategy,
    create_preflop_strategy_from_directory,
    infer_preflop_layer,
    load_preflop_strategy_from_directory,
)

__all__ = [
    "PreflopLayer",
    "PreflopRuntimeConfig",
    "create_preflop_strategy",
    "create_preflop_strategy_from_directory",
    "create_postflop_strategy",
    "infer_preflop_layer",
    "load_preflop_strategy_from_directory",
]
