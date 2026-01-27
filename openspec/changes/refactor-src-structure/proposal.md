# Change: 精简 src 结构并提取公共基类/类型

## Why

当前 `src/bayes_poker` 存在空包、重复类型、构建产物与开发笔记混入等问题，导致理解成本与维护成本上升。
本次调整以 KISS/DRY/YAGNI 为原则，最小化结构噪声，统一可复用的基础类型与序列化逻辑。

## What Changes

- 抽取公共类型：新增 `bayes_poker/domain/poker.py`，统一 `ActionType` / `Street`（并保持原模块导出兼容）。
- 抽取公共方法：为 `comm/messages.py` 引入统一的 payload 序列化基类，去除重复 `to_dict/from_dict`。
- 统一重复类型：在 `screen/` 内抽取 `WindowInfo` 到独立模块，消除重复定义。
- 精简结构：移除空包与占位文件（`execution/`、`utils/`、`strategy/interface.py` 等）。
- 清理产物与开发笔记：将 `analysis/*.ipynb` 移出 `src/`，删除 `src` 内的 `*.egg-info` / `__pycache__`。

## Impact

- **Affected code**:
  - `src/bayes_poker/comm/messages.py`
  - `src/bayes_poker/comm/__init__.py`
  - `src/bayes_poker/table/state_bridge.py`
  - `src/bayes_poker/table/detector.py`
  - `src/bayes_poker/table/__init__.py`
  - `src/bayes_poker/screen/capture.py`
  - `src/bayes_poker/screen/window.py`
  - `src/bayes_poker/screen/__init__.py`
  - `src/bayes_poker/analysis/*`
  - `src/bayes_poker/execution/*`
  - `src/bayes_poker/utils/*`
- **Behavior**: 逻辑行为保持不变，结构更清晰，减少重复与无效文件。
