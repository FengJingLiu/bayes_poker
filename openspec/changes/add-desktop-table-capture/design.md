# Design: 无 HWND 桌面截图与牌桌区域识别

## Context

现有实时牌桌解析依赖：
- `WindowManager`（基于 `pywin32` 枚举窗口）发现 `hwnd`
- `Win32ScreenCapture` 通过 `hwnd` 截图

采集卡场景无法获取 `hwnd`，只能从桌面整屏画面中定位牌桌区域。

## Goals / Non-Goals

### Goals
- 支持桌面整屏截图，并裁剪出牌桌区域供 `TableDetector` 解析
- 支持桌面上 1~N 张牌桌（数量、布局可能变化）
- 自动识别失败时可配置固定区域回退
- 保持现有 `create_manager()` 默认行为不变

### Non-Goals
- 不实现跨进程共享帧/零拷贝（可能需要共享内存/环形队列，后续再做）
- 不引入复杂的机器学习检测模型（优先颜色/几何启发式 + 兜底配置）
- 不保证任意桌面主题/壁纸/叠加窗口都能稳定识别（先覆盖典型全屏采集卡画面）

## Proposed Architecture

### 1) 截图源（ScreenCapture 扩展）

- 在 Windows 下支持“桌面截图”路径：
  - `capture_window(hwnd=0)`：表示捕获桌面（整屏）
  - `capture_region(hwnd=0, x, y, width, height)`：表示捕获桌面绝对坐标区域

### 2) 牌桌区域识别（纯函数）

新增模块 `bayes_poker.screen.table_region`：
- `detect_table_regions(img, max_tables)`：从整屏截图中识别出可能的牌桌矩形区域（按 y/x 排序，返回列表）
- `parse_fixed_table_regions(env_value)`：解析固定区域配置（`x,y,w,h|...`）
- `fallback_grid_regions(screen_w, screen_h, max_tables)`：在无识别结果且无配置时，提供简单网格兜底（1/2/4 桌）

识别策略：
- 优先使用 OpenCV（若安装）进行颜色分割（绿色台面）+ 轮廓过滤（面积、长宽比）得到台面区域
- 将台面矩形按经验比例向上/下扩展，覆盖顶部菜单与底部操作区，得到“桌窗口”矩形
- 对高度重叠的候选框做简单合并/去重

### 3) 管理器与解析器集成

- `TableParser` 增加可选参数 `capture_area`：
  - 传入时不再依赖 `get_window_rect(hwnd)`，直接使用该区域宽高建立 `ScaledLayout`
  - 每帧调用 `capture_region(hwnd=0, ...)` 截取对应区域再解析
- `MultiTableManager` 增加 `capture_mode` 参数：
  - `window`：现有路径（默认）
  - `desktop`：通过桌面截图识别区域后启动多个 `TableParser(capture_area=...)`

## Risks / Trade-offs

- Windows DPI 缩放可能影响桌面像素坐标与系统度量的一致性：实现上需尽量使用“真实像素”截图路径，并在日志中输出检测到的屏幕尺寸以便排查。
- 启发式识别存在误检/漏检：必须提供固定区域配置作为兜底，且识别逻辑需可调参数（后续按需扩展）。

