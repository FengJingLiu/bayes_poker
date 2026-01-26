# Tasks: 支持无 HWND 的桌面截图与牌桌区域识别

## 1. 桌面牌桌区域识别

- [ ] 1.1 新增 `src/bayes_poker/screen/table_region.py`（检测/解析/兜底 API）
- [ ] 1.2 添加单元测试：固定区域解析、网格兜底（不依赖 OpenCV）
- [ ] 1.3 （可选）添加 OpenCV 可用时的检测测试（本地环境有 cv2 才运行）

## 2. Windows 桌面截图支持

- [ ] 2.1 修改 `src/bayes_poker/screen/capture.py`：支持 `hwnd=0` 的桌面截图与区域截图
- [ ] 2.2 增加必要日志（识别/兜底路径、区域数量、屏幕尺寸）

## 3. 解析器与管理器集成

- [ ] 3.1 修改 `src/bayes_poker/table/parser.py`：支持 `capture_area` 初始化与截图
- [ ] 3.2 修改 `src/bayes_poker/table/manager.py`：新增 `capture_mode="desktop"` 管理逻辑
- [ ] 3.3 更新 `README.md`：补充桌面模式用法与固定区域配置示例

## 4. Verification

- [ ] 4.1 `uv run pytest -q` 通过
- [ ] 4.2 `uv run python -m compileall src` 通过

