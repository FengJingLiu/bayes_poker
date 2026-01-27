"""屏幕与窗口基础类型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WindowInfo:
    """窗口信息。"""

    hwnd: int
    title: str
    class_name: str
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> tuple[int, int, int, int]:
        """返回窗口区域 (x, y, width, height)。"""
        return (self.x, self.y, self.width, self.height)
