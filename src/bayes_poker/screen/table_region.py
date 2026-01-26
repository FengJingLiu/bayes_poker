"""桌面牌桌区域识别与兜底策略。

该模块用于“无 hwnd”场景（采集卡整屏画面）：
- 优先从整屏截图中识别牌桌区域（可选依赖 OpenCV）
- 识别失败时可解析固定区域配置（写死桌面位置）
- 最终仍无结果时提供简单网格兜底（保证可用性）
"""

from __future__ import annotations

import logging

import numpy as np

from bayes_poker.ocr.schema import Area

LOGGER = logging.getLogger(__name__)


def parse_fixed_table_regions(raw: str | None) -> list[Area]:
    """解析固定区域配置。

    配置格式：
    - `x,y,w,h|x,y,w,h|...`

    Args:
        raw: 原始配置字符串

    Returns:
        区域列表（无效项将被忽略）
    """
    if raw is None:
        return []

    raw = raw.strip()
    if not raw:
        return []

    regions: list[Area] = []
    for item in raw.split("|"):
        item = item.strip()
        if not item:
            continue

        parts = [p.strip() for p in item.split(",")]
        if len(parts) != 4:
            continue

        try:
            x, y, w, h = (int(p) for p in parts)
        except ValueError:
            continue

        if w <= 0 or h <= 0:
            continue

        regions.append(Area.from_xywh(x, y, w, h))

    return regions


def fallback_grid_regions(
    screen_width: int, screen_height: int, max_tables: int
) -> list[Area]:
    """基于屏幕尺寸的网格兜底区域。

    规则（尽量简单，避免过度设计）：
    - `max_tables<=1`：整屏一个区域
    - `max_tables==2`：左右二分
    - `max_tables>=3`：2x2 网格（最多返回 4 个）

    Args:
        screen_width: 屏幕宽度（像素）
        screen_height: 屏幕高度（像素）
        max_tables: 期望最大桌数

    Returns:
        区域列表
    """
    if screen_width <= 0 or screen_height <= 0:
        return []

    if max_tables <= 1:
        return [Area.from_xywh(0, 0, screen_width, screen_height)]

    if max_tables == 2:
        half_w = screen_width // 2
        return [
            Area.from_xywh(0, 0, half_w, screen_height),
            Area.from_xywh(half_w, 0, screen_width - half_w, screen_height),
        ]

    half_w = screen_width // 2
    half_h = screen_height // 2
    regions = [
        Area.from_xywh(0, 0, half_w, half_h),
        Area.from_xywh(half_w, 0, screen_width - half_w, half_h),
        Area.from_xywh(0, half_h, half_w, screen_height - half_h),
        Area.from_xywh(half_w, half_h, screen_width - half_w, screen_height - half_h),
    ]
    return regions[: min(max_tables, 4)]


def detect_table_regions(img: np.ndarray, max_tables: int = 8) -> list[Area]:
    """尝试从整屏截图中自动识别牌桌区域。

    当前实现采用启发式（优先依赖 OpenCV）。若 OpenCV 不可用，返回空列表。

    Args:
        img: 整屏截图（OpenCV BGR）
        max_tables: 最大返回桌数

    Returns:
        识别出的牌桌区域列表（按 y/x 排序）。失败返回空列表。
    """
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return []

    if img.size == 0:
        return []

    height, width = img.shape[:2]
    if width < 200 or height < 200:
        return []

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 绿色台面大致范围（可后续按需参数化）
    lower = np.array([35, 40, 40], dtype=np.uint8)
    upper = np.array([90, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((7, 7), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[Area] = []
    min_area = int(width * height * 0.03)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue

        area = w * h
        if area < min_area:
            continue

        aspect = w / max(h, 1)
        if not (1.1 <= aspect <= 2.8):
            continue

        # 绿色区域通常是“台面内部”，将其扩展为“牌桌窗口”大致矩形
        expand_left = int(w * 0.12)
        expand_right = int(w * 0.12)
        expand_top = int(h * 0.55)
        expand_bottom = int(h * 0.70)

        nx = max(0, x - expand_left)
        ny = max(0, y - expand_top)
        nright = min(width, x + w + expand_right)
        nbottom = min(height, y + h + expand_bottom)

        nw = max(1, nright - nx)
        nh = max(1, nbottom - ny)

        candidates.append(Area.from_xywh(nx, ny, nw, nh))

    # 简单去重/合并：按面积降序，抑制高度重叠框
    candidates.sort(key=lambda a: a.width * a.height, reverse=True)
    selected: list[Area] = []

    def iou(a: Area, b: Area) -> float:
        ix1 = max(a.x1, b.x1)
        iy1 = max(a.y1, b.y1)
        ix2 = min(a.x2, b.x2)
        iy2 = min(a.y2, b.y2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter == 0:
            return 0.0
        union = (a.width * a.height) + (b.width * b.height) - inter
        return inter / union if union > 0 else 0.0

    for candidate in candidates:
        if any(iou(candidate, kept) >= 0.35 for kept in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_tables:
            break

    selected.sort(key=lambda a: (a.y1, a.x1))
    return selected

