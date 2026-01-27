"""屏幕截图模块。

提供屏幕截图功能，仅支持桌面区域截图（Desktop 模式）。
目前主要支持 Windows (win32)。
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod

import numpy as np

LOGGER = logging.getLogger(__name__)


class ScreenCapture(ABC):
    """屏幕截图抽象基类。

    仅支持桌面区域截图，不支持基于窗口句柄 (hwnd) 的截图。
    """

    @abstractmethod
    def capture_region(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        """截取桌面指定区域的图像。

        Args:
            x: 区域左上角 x 坐标（相对于桌面）
            y: 区域左上角 y 坐标（相对于桌面）
            width: 区域宽度
            height: 区域高度

        Returns:
            OpenCV 格式图像 (BGR)，失败返回 None
        """
        ...

    @abstractmethod
    def get_desktop_size(self) -> tuple[int, int] | None:
        """获取桌面尺寸。

        Returns:
            (width, height)，失败返回 None
        """
        ...


class Win32ScreenCapture(ScreenCapture):
    """Windows 平台屏幕截图实现。

    基于 Win32 API 实现桌面区域截图。
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Win32ScreenCapture 仅支持 Windows 平台")

        try:
            import win32gui  # type: ignore[import-not-found]
            import win32ui  # type: ignore[import-not-found]
            import win32con  # type: ignore[import-not-found]
            import win32api  # type: ignore[import-not-found]

            self._win32gui = win32gui
            self._win32ui = win32ui
            self._win32con = win32con
            self._win32api = win32api
        except ImportError as e:
            raise ImportError("需要安装 pywin32: uv add pywin32") from e

    def capture_region(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        """截取桌面指定区域的图像。

        Args:
            x: 区域左上角 x 坐标（相对于虚拟桌面左上角）
            y: 区域左上角 y 坐标（相对于虚拟桌面左上角）
            width: 区域宽度
            height: 区域高度

        Returns:
            OpenCV 格式图像 (BGR)，失败返回 None
        """
        try:
            desktop_left = self._win32api.GetSystemMetrics(
                self._win32con.SM_XVIRTUALSCREEN
            )
            desktop_top = self._win32api.GetSystemMetrics(
                self._win32con.SM_YVIRTUALSCREEN
            )
        except Exception:
            desktop_left = 0
            desktop_top = 0

        desktop_hwnd = self._win32gui.GetDesktopWindow()

        try:
            hwnd_dc = self._win32gui.GetWindowDC(desktop_hwnd)
            mfc_dc = self._win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            save_bitmap = self._win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(save_bitmap)
            save_dc.BitBlt(
                (0, 0),
                (width, height),
                mfc_dc,
                (desktop_left + x, desktop_top + y),
                self._win32con.SRCCOPY,
            )

            signed_ints_array = save_bitmap.GetBitmapBits(True)

            self._win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            self._win32gui.ReleaseDC(desktop_hwnd, hwnd_dc)

            img = np.frombuffer(signed_ints_array, dtype=np.uint8)
            img.shape = (height, width, 4)
            return img[:, :, :3]  # BGRA -> BGR

        except Exception as e:
            LOGGER.warning("截图失败: %s", e)
            return None

    def get_desktop_size(self) -> tuple[int, int] | None:
        """获取虚拟桌面尺寸。

        Returns:
            (width, height)，失败返回 None
        """
        try:
            width = self._win32api.GetSystemMetrics(self._win32con.SM_CXVIRTUALSCREEN)
            height = self._win32api.GetSystemMetrics(self._win32con.SM_CYVIRTUALSCREEN)
            return (int(width), int(height))
        except Exception as e:
            LOGGER.warning("获取桌面尺寸失败: %s", e)
            return None


class MockScreenCapture(ScreenCapture):
    """测试用的模拟截图实现。"""

    def __init__(self, test_image: np.ndarray | None = None) -> None:
        self._test_image = test_image

    def set_test_image(self, image: np.ndarray) -> None:
        """设置测试图像。"""
        self._test_image = image

    def load_test_image(self, path: str) -> None:
        """从文件加载测试图像。"""
        try:
            import cv2  # type: ignore[import-not-found]

            self._test_image = cv2.imread(path)
        except Exception as e:
            LOGGER.error("加载测试图像失败: %s", e)

    def capture_region(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        """截取模拟图像的指定区域。"""
        if self._test_image is None:
            return None
        return self._test_image[y : y + height, x : x + width].copy()

    def get_desktop_size(self) -> tuple[int, int] | None:
        """获取模拟图像尺寸。"""
        if self._test_image is None:
            return None
        h, w = self._test_image.shape[:2]
        return (w, h)


def get_screen_capture(use_mock: bool = False) -> ScreenCapture:
    """获取屏幕截图实例。

    目前仅支持 Windows 平台（除 Mock 外）。

    Args:
        use_mock: 确定是否使用模拟实现（用于测试）。

    Returns:
        ScreenCapture: 屏幕截图实例。

    Raises:
        RuntimeError: 当在非 Windows 平台且未启用 Mock 时执行。
    """
    if use_mock:
        return MockScreenCapture()

    if sys.platform == "win32":
        return Win32ScreenCapture()

    raise RuntimeError(f"不支持的平台: {sys.platform}，目前截图功能仅支持 Windows")
