"""OCR 基础数据结构定义。

包含坐标点、区域、颜色等基础类型，支持绝对坐标与相对坐标的转换。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class Point:
    """绝对坐标点。"""

    x: int
    y: int

    def __str__(self) -> str:
        return f"Point(x={self.x}, y={self.y})"

    def scale(self, factor: float) -> Point:
        """按比例缩放坐标。"""
        return Point(int(self.x * factor), int(self.y * factor))

    def to_relative(self, width: int, height: int) -> RelativePoint:
        """转换为相对坐标。"""
        return RelativePoint(self.x / width, self.y / height)


@dataclass(frozen=True, slots=True)
class RelativePoint:
    """相对坐标点 (0.0 ~ 1.0)。"""

    x: float  # 相对于窗口宽度的比例
    y: float  # 相对于窗口高度的比例

    def __post_init__(self) -> None:
        if not (0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0):
            # 允许略微超出边界（容错）
            pass

    def to_absolute(self, width: int, height: int) -> Point:
        """转换为绝对坐标。"""
        return Point(int(self.x * width), int(self.y * height))

    def __str__(self) -> str:
        return f"RelativePoint(x={self.x:.4f}, y={self.y:.4f})"


@dataclass(frozen=True, slots=True)
class Area:
    """绝对坐标区域（左上角 + 右下角）。"""

    x1: int  # 左上角 x
    y1: int  # 左上角 y
    x2: int  # 右下角 x
    y2: int  # 右下角 y

    @classmethod
    def from_points(cls, top_left: Point, bottom_right: Point) -> Area:
        """从两个点创建区域。"""
        return cls(top_left.x, top_left.y, bottom_right.x, bottom_right.y)

    @classmethod
    def from_xywh(cls, x: int, y: int, width: int, height: int) -> Area:
        """从左上角坐标和宽高创建区域。"""
        return cls(x, y, x + width, y + height)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def top_left(self) -> Point:
        return Point(self.x1, self.y1)

    @property
    def bottom_right(self) -> Point:
        return Point(self.x2, self.y2)

    @property
    def center(self) -> Point:
        return Point((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    def scale(self, factor: float) -> Area:
        """按比例缩放区域。"""
        return Area(
            int(self.x1 * factor),
            int(self.y1 * factor),
            int(self.x2 * factor),
            int(self.y2 * factor),
        )

    def to_relative(self, width: int, height: int) -> RelativeArea:
        """转换为相对坐标区域。"""
        return RelativeArea(
            self.x1 / width,
            self.y1 / height,
            self.x2 / width,
            self.y2 / height,
        )

    def crop(self, img: np.ndarray) -> np.ndarray:
        """从图像中裁剪该区域。"""
        return img[self.y1 : self.y2, self.x1 : self.x2]

    def __str__(self) -> str:
        return f"Area(x={self.x1}, y={self.y1}, w={self.width}, h={self.height})"


@dataclass(frozen=True, slots=True)
class RelativeArea:
    """相对坐标区域 (0.0 ~ 1.0)。"""

    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_points(
        cls, top_left: RelativePoint, bottom_right: RelativePoint
    ) -> RelativeArea:
        """从两个相对坐标点创建区域。"""
        return cls(top_left.x, top_left.y, bottom_right.x, bottom_right.y)

    def to_absolute(self, width: int, height: int) -> Area:
        """转换为绝对坐标区域。"""
        return Area(
            int(self.x1 * width),
            int(self.y1 * height),
            int(self.x2 * width),
            int(self.y2 * height),
        )

    def __str__(self) -> str:
        return (
            f"RelativeArea(x1={self.x1:.4f}, y1={self.y1:.4f}, "
            f"x2={self.x2:.4f}, y2={self.y2:.4f})"
        )


@dataclass(frozen=True, slots=True)
class Color:
    """RGB 颜色值。"""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for c in (self.r, self.g, self.b):
            if not 0 <= c <= 255:
                raise ValueError(f"颜色值必须在 0-255 范围内: {c}")

    def like(self, other: Color, tolerance: int = 20) -> bool:
        """判断两个颜色是否相似。

        Args:
            other: 另一个颜色
            tolerance: 容差值（每个通道的最大差异）

        Returns:
            True 如果两个颜色在容差范围内相似
        """
        return (
            abs(self.r - other.r) <= tolerance
            and abs(self.g - other.g) <= tolerance
            and abs(self.b - other.b) <= tolerance
        )

    def point_like(self, img: np.ndarray, point: Point, tolerance: int = 20) -> bool:
        """检查图像中指定点的颜色是否与当前颜色相似。

        注意：OpenCV 图像为 BGR 格式。

        Args:
            img: OpenCV 格式图像 (BGR)
            point: 要检查的坐标点
            tolerance: 容差值

        Returns:
            True 如果颜色相似
        """
        # OpenCV 图像格式为 BGR，需要转换
        pixel = img[point.y, point.x]
        other = Color(int(pixel[2]), int(pixel[1]), int(pixel[0]))
        return self.like(other, tolerance)

    def area_like(
        self,
        img: np.ndarray,
        tolerance: int = 20,
        threshold: float = 0.5,
    ) -> bool:
        """检查图像区域中相似颜色像素的比例是否超过阈值。

        Args:
            img: OpenCV 格式图像区域 (BGR)
            tolerance: 颜色容差
            threshold: 相似像素比例阈值 (0.0 ~ 1.0)

        Returns:
            True 如果相似像素比例超过阈值
        """
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError("需要安装 opencv-python: uv add opencv-python") from e

        lower = np.array(
            [self.b - tolerance, self.g - tolerance, self.r - tolerance],
            dtype=np.int16,
        )
        upper = np.array(
            [self.b + tolerance, self.g + tolerance, self.r + tolerance],
            dtype=np.int16,
        )
        # 确保边界在有效范围内
        lower = np.clip(lower, 0, 255).astype(np.uint8)
        upper = np.clip(upper, 0, 255).astype(np.uint8)

        mask = cv2.inRange(img, lower, upper)
        match_ratio = cv2.countNonZero(mask) / (img.shape[0] * img.shape[1])
        return match_ratio >= threshold

    def to_bgr(self) -> tuple[int, int, int]:
        """转换为 BGR 格式（OpenCV 使用）。"""
        return (self.b, self.g, self.r)

    def __str__(self) -> str:
        return f"Color(r={self.r}, g={self.g}, b={self.b})"


# 预定义的扑克牌花色颜色 (基于 GGPoker 截图)
CARD_SUIT_COLORS: dict[str, Color] = {
    "c": Color(13, 144, 32),  # 梅花 (Club) - 绿色
    "d": Color(18, 82, 154),  # 方块 (Diamond) - 蓝色
    "h": Color(154, 25, 19),  # 红桃 (Heart) - 红色
    "s": Color(43, 44, 39),  # 黑桃 (Spade) - 黑色
}


@dataclass(frozen=True, slots=True)
class ColorCheckConfig:
    """颜色检测配置。

    用于定义一个颜色检测规则，包含：
    - 要检测的位置（点或区域）
    - 目标颜色
    - 容差和阈值
    """

    color: Color
    tolerance: int = 20
    threshold: float = 0.5  # 仅用于区域检测


@dataclass(frozen=True, slots=True)
class PointColorCheck:
    """单点颜色检测配置。"""

    point: Point | RelativePoint
    config: ColorCheckConfig


@dataclass(frozen=True, slots=True)
class MultiPointColorCheck:
    """多点颜色检测配置。"""

    points: Sequence[Point | RelativePoint]
    config: ColorCheckConfig


@dataclass(frozen=True, slots=True)
class AreaColorCheck:
    """区域颜色检测配置。"""

    area: Area | RelativeArea
    config: ColorCheckConfig
