"""窗口管理模块。

提供 GGPoker 窗口的自动发现、跟踪和管理功能。
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.screen.types import WindowInfo

if TYPE_CHECKING:
    import numpy as np

LOGGER = logging.getLogger(__name__)


GG_POKER_WINDOW_CLASS = "ApolloRuntimeContentWindow"


@dataclass
class TrackedWindow:
    """被追踪的窗口实例。"""

    info: WindowInfo
    index: int
    last_screenshot: np.ndarray | None = field(default=None, repr=False)

    @property
    def hwnd(self) -> int:
        return self.info.hwnd

    @property
    def is_valid_size(self) -> bool:
        return self.info.width > 100 and self.info.height > 100


class WindowDiscovery:
    """窗口发现服务。"""

    def __init__(self, window_class: str = GG_POKER_WINDOW_CLASS) -> None:
        self._window_class = window_class

        if sys.platform == "win32":
            try:
                import win32gui  # type: ignore[import-not-found]

                self._win32gui = win32gui
            except ImportError as e:
                raise ImportError("需要安装 pywin32: uv add pywin32") from e
        else:
            self._win32gui = None

    def find_all_windows(self, title_prefix: str = "") -> list[WindowInfo]:
        """查找所有匹配的窗口。

        Args:
            title_prefix: 窗口标题前缀过滤

        Returns:
            匹配的窗口信息列表
        """
        if sys.platform != "win32" or self._win32gui is None:
            LOGGER.warning("非 Windows 平台，无法发现窗口")
            return []

        windows: list[WindowInfo] = []

        def enum_callback(hwnd: int, _) -> None:
            if not self._win32gui.IsWindow(hwnd):
                return
            if not self._win32gui.IsWindowEnabled(hwnd):
                return
            if not self._win32gui.IsWindowVisible(hwnd):
                return

            class_name = self._win32gui.GetClassName(hwnd)
            if class_name != self._window_class:
                return

            title = self._win32gui.GetWindowText(hwnd)
            if title_prefix and not title.startswith(title_prefix):
                return

            try:
                left, top, right, bottom = self._win32gui.GetWindowRect(hwnd)
                windows.append(
                    WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        class_name=class_name,
                        x=left,
                        y=top,
                        width=right - left,
                        height=bottom - top,
                    )
                )
            except Exception as e:
                LOGGER.debug("获取窗口 %d 信息失败: %s", hwnd, e)

        self._win32gui.EnumWindows(enum_callback, 0)
        return windows

    def is_window_valid(self, hwnd: int) -> bool:
        """检查窗口是否仍然有效。"""
        if sys.platform != "win32" or self._win32gui is None:
            return False

        try:
            return self._win32gui.IsWindow(hwnd) and self._win32gui.IsWindowVisible(
                hwnd
            )
        except Exception:
            return False


class WindowManager:
    """多窗口管理器。

    负责跟踪多个 GGPoker 窗口，支持动态发现和生命周期管理。
    """

    def __init__(self, window_class: str = GG_POKER_WINDOW_CLASS) -> None:
        self._discovery = WindowDiscovery(window_class)
        self._tracked_windows: dict[int, TrackedWindow] = {}
        self._next_index = 0

    @property
    def windows(self) -> list[TrackedWindow]:
        """获取所有被追踪的窗口。"""
        return list(self._tracked_windows.values())

    @property
    def window_count(self) -> int:
        """获取窗口数量。"""
        return len(self._tracked_windows)

    def refresh(self) -> tuple[list[TrackedWindow], list[TrackedWindow]]:
        """刷新窗口列表。

        Returns:
            (新增的窗口列表, 关闭的窗口列表)
        """
        current_windows = self._discovery.find_all_windows()
        current_hwnds = {w.hwnd for w in current_windows}

        closed: list[TrackedWindow] = []
        for hwnd in list(self._tracked_windows.keys()):
            if hwnd not in current_hwnds:
                closed.append(self._tracked_windows.pop(hwnd))
                LOGGER.info("窗口已关闭: hwnd=%d", hwnd)

        added: list[TrackedWindow] = []
        for window_info in current_windows:
            if window_info.hwnd not in self._tracked_windows:
                tracked = TrackedWindow(
                    info=window_info,
                    index=self._next_index,
                )
                self._next_index += 1
                self._tracked_windows[window_info.hwnd] = tracked
                added.append(tracked)
                LOGGER.info(
                    "发现新窗口: hwnd=%d, title=%s, index=%d",
                    window_info.hwnd,
                    window_info.title,
                    tracked.index,
                )
            else:
                existing = self._tracked_windows[window_info.hwnd]
                existing.info = window_info

        return added, closed

    def get_window(self, hwnd: int) -> TrackedWindow | None:
        """根据句柄获取窗口。"""
        return self._tracked_windows.get(hwnd)

    def get_window_by_index(self, index: int) -> TrackedWindow | None:
        """根据索引获取窗口。"""
        for window in self._tracked_windows.values():
            if window.index == index:
                return window
        return None

    def remove_window(self, hwnd: int) -> TrackedWindow | None:
        """移除窗口。"""
        return self._tracked_windows.pop(hwnd, None)

    def clear(self) -> None:
        """清除所有窗口。"""
        self._tracked_windows.clear()
        self._next_index = 0
