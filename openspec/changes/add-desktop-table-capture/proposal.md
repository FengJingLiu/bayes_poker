# Change: 支持无 HWND 的桌面截图与牌桌区域识别

## Why

在部分平台封禁/隔离策略下，打牌电脑与运行解析器的电脑不在同一台机器上。采集卡电脑接入打牌电脑的 HDMI/DP 输出后，只能获得“整屏画面”，无法通过 Windows API 获取目标窗口的 `hwnd`，导致现有按窗口句柄截图与窗口发现逻辑不可用。

需要新增“桌面截图模式”，以便在采集卡电脑上对全屏画面进行截取，并自动识别出 1~N 张牌桌区域，供现有 OCR 牌桌解析器复用。

## What Changes

- **新增** 桌面截图模式（`capture_mode="desktop"`）
  - 以桌面为截图源，支持按绝对坐标区域截图
  - 自动识别桌面中的牌桌区域（数量与排列可能变化）
  - 识别失败时支持回退到用户配置的固定区域（写死桌面位置）
- **保持兼容** 现有 Windows `hwnd` 窗口发现与按窗口截图模式（默认不变）

## Impact

- **Affected specs**: 新增 `screen-desktop-capture` 能力（当前仓库未落地 `openspec/specs`，本次以 change 级文档为准）
- **Affected code**:
  - 修改 `src/bayes_poker/screen/capture.py`（支持桌面截图路径）
  - 新增 `src/bayes_poker/screen/table_region.py`（牌桌区域识别与固定区域解析）
  - 修改 `src/bayes_poker/table/parser.py`（支持传入“截图区域”而非仅 hwnd）
  - 修改 `src/bayes_poker/table/manager.py`（新增桌面模式管理器/入口参数）
  - 新增/修改测试覆盖区域识别与配置解析

## Key Design Decisions

1. **最小侵入**：默认行为不变，只有显式启用 `capture_mode="desktop"` 时走新路径。
2. **强兜底**：自动识别失败时，允许使用环境变量配置固定区域，避免因识别不稳定导致不可用。
3. **性能优先但不超前设计**：先实现“按区域截图 + 每桌独立解析进程”的最小方案；不引入跨进程帧共享（后续按需优化）。

