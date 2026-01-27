# Tasks: 精简 src 结构并提取公共基类/类型

## 1. 结构精简

- [x] 1.1 移出 `src/bayes_poker/analysis/*.ipynb` 至仓库顶层（目录待确认）
- [x] 1.2 删除空包与占位文件：`execution/`、`utils/`、`strategy/interface.py`
- [x] 1.3 删除 `src` 内构建产物：`*.egg-info` 与 `__pycache__`

## 2. 公共类型与基类抽取

- [x] 2.1 新增 `src/bayes_poker/domain/poker.py`（`ActionType`/`Street`）
- [x] 2.2 更新 `table/state_bridge.py`、`table/detector.py`、`comm/messages.py` 使用统一类型
- [x] 2.3 新增 payload 基类并精简 `comm/messages.py` 的重复序列化逻辑
- [x] 2.4 抽取 `screen/types.py`，统一 `WindowInfo` 定义并保持导出兼容

## 3. 导出与兼容

- [x] 3.1 更新 `comm/__init__.py`、`table/__init__.py`、`screen/__init__.py` 的导出
- [x] 3.2 检查所有内部导入路径，确保无断链

## 4. Verification

- [x] 4.1 `uv run python -m compileall src`
- [x] 4.2 `uv run pytest -q`
