"""屏幕截图模块。

提供跨平台的屏幕截图功能，支持 Windows (win32) 和 Linux。
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from bayes_poker.screen.types import WindowInfo

if TYPE_CHECKING:
    from bayes_poker.ocr.schema import Area

LOGGER = logging.getLogger(__name__)


class ScreenCapture(ABC):
    """屏幕截图抽象基类。"""

    @abstractmethod
    def capture_window(self, hwnd: int) -> np.ndarray | None:
        """截取指定窗口的图像。

        Args:
            hwnd: 窗口句柄

        Returns:
            OpenCV 格式图像 (BGR)，失败返回 None
        """
        ...

    @abstractmethod
    def capture_region(
        self, hwnd: int, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        """截取窗口内指定区域的图像。

        Args:
            hwnd: 窗口句柄
            x: 区域左上角 x 坐标（相对于窗口）
            y: 区域左上角 y 坐标（相对于窗口）
            width: 区域宽度
            height: 区域高度

        Returns:
            OpenCV 格式图像 (BGR)，失败返回 None
        """
        ...

    @abstractmethod
    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        """获取窗口位置和大小。

        Args:
            hwnd: 窗口句柄

        Returns:
            (x, y, width, height)，失败返回 None
        """
        ...


class Win32ScreenCapture(ScreenCapture):
    """Windows 平台屏幕截图实现。"""

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

    def capture_window(self, hwnd: int) -> np.ndarray | None:
        rect = self.get_window_rect(hwnd)
        if rect is None:
            return None
        _, _, width, height = rect

        if hwnd == 0:
            return self._capture_desktop_internal(x=0, y=0, width=width, height=height)

        return self._capture_internal(hwnd, x=0, y=0, width=width, height=height)

    def capture_region(
        self, hwnd: int, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        if hwnd == 0:
            return self._capture_desktop_internal(x=x, y=y, width=width, height=height)

        full_img = self.capture_window(hwnd)
        if full_img is None:
            return None
        return full_img[y : y + height, x : x + width]

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        if hwnd == 0:
            try:
                width = self._win32api.GetSystemMetrics(self._win32con.SM_CXVIRTUALSCREEN)
                height = self._win32api.GetSystemMetrics(self._win32con.SM_CYVIRTUALSCREEN)
                return (0, 0, int(width), int(height))
            except Exception as e:
                LOGGER.warning("获取桌面尺寸失败: %s", e)
                return None

        try:
            left, top, right, bottom = self._win32gui.GetWindowRect(hwnd)
            return (left, top, right - left, bottom - top)
        except Exception as e:
            LOGGER.warning("获取窗口尺寸失败 hwnd=%d: %s", hwnd, e)
            return None

    def _capture_internal(
        self, hwnd: int, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        try:
            hwnd_dc = self._win32gui.GetWindowDC(hwnd)
            mfc_dc = self._win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            save_bitmap = self._win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(save_bitmap)
            save_dc.BitBlt(
                (0, 0),
                (width, height),
                mfc_dc,
                (x, y),
                self._win32con.SRCCOPY,
            )

            signed_ints_array = save_bitmap.GetBitmapBits(True)

            self._win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            self._win32gui.ReleaseDC(hwnd, hwnd_dc)

            img = np.frombuffer(signed_ints_array, dtype=np.uint8)
            img.shape = (height, width, 4)
            return img[:, :, :3]  # BGRA -> BGR

        except Exception as e:
            LOGGER.warning("截图失败 hwnd=%d: %s", hwnd, e)
            return None

    def _capture_desktop_internal(
        self, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        """截取桌面区域图像。

        约定：`x/y` 为相对于虚拟桌面左上角（`SM_XVIRTUALSCREEN/SM_YVIRTUALSCREEN`）的偏移，
        与 `capture_window(hwnd=0)` 返回的图像坐标保持一致（从 0,0 开始）。
        """
        try:
            desktop_left = self._win32api.GetSystemMetrics(self._win32con.SM_XVIRTUALSCREEN)
            desktop_top = self._win32api.GetSystemMetrics(self._win32con.SM_YVIRTUALSCREEN)
        except Exception:
            desktop_left = 0
            desktop_top = 0

        desktop_hwnd = self._win32gui.GetDesktopWindow()
        return self._capture_internal(
            desktop_hwnd,
            x=desktop_left + x,
            y=desktop_top + y,
            width=width,
            height=height,
        )


class LinuxScreenCapture(ScreenCapture):
    """Linux 平台屏幕截图实现（基于 mss）。"""

    def __init__(self) -> None:
        try:
            import mss  # type: ignore[import-not-found]

            self._mss = mss.mss()
        except ImportError as e:
            raise ImportError("需要安装 mss: uv add mss") from e

    def capture_window(self, hwnd: int) -> np.ndarray | None:
        LOGGER.warning("Linux 平台暂不支持按窗口句柄截图，使用全屏截图")
        try:
            import cv2  # type: ignore[import-not-found]

            monitor = self._mss.monitors[1]
            screenshot = self._mss.grab(monitor)
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            LOGGER.warning("截图失败: %s", e)
            return None

    def capture_region(
        self, hwnd: int, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        try:
            import cv2  # type: ignore[import-not-found]

            monitor = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self._mss.grab(monitor)
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            LOGGER.warning("区域截图失败: %s", e)
            return None

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        LOGGER.warning("Linux 平台暂不支持获取窗口位置")
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

    def capture_window(self, hwnd: int) -> np.ndarray | None:
        return self._test_image.copy() if self._test_image is not None else None

    def capture_region(
        self, hwnd: int, x: int, y: int, width: int, height: int
    ) -> np.ndarray | None:
        if self._test_image is None:
            return None
        return self._test_image[y : y + height, x : x + width].copy()

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        if self._test_image is None:
            return None
        h, w = self._test_image.shape[:2]
        return (0, 0, w, h)


def get_screen_capture(use_mock: bool = False) -> ScreenCapture:
    """获取当前平台的屏幕截图实例。

    Args:
        use_mock: 是否使用模拟实现（用于测试）

    Returns:
        ScreenCapture 实例
    """
    if use_mock:
        return MockScreenCapture()

    if sys.platform == "win32":
        return Win32ScreenCapture()
    else:
        return LinuxScreenCapture()
