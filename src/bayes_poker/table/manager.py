"""多窗口进程管理器。

管理多个牌桌解析器进程。
"""

from __future__ import annotations

import logging
import multiprocessing
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.screen.capture import ScreenCapture, get_screen_capture
from bayes_poker.screen.window import TrackedWindow, WindowManager
from bayes_poker.screen.table_region import (
    detect_table_regions,
    fallback_grid_regions,
    parse_fixed_table_regions,
)
from bayes_poker.table.parser import TableParser

if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock

LOGGER = logging.getLogger(__name__)


@dataclass
class ParserInfo:
    """解析器信息。"""

    hwnd: int
    window_index: int
    parser: TableParser
    is_running: bool = True


class MultiTableManager:
    """多牌桌管理器。

    负责管理多个窗口的解析器进程。
    """

    def __init__(
        self,
        small_blind: float = 0.5,
        big_blind: float = 1.0,
        max_tables: int = 8,
        poll_interval: float = 0.1,
        capture_mode: str = "window",
    ) -> None:
        self._small_blind = small_blind
        self._big_blind = big_blind
        self._max_tables = max_tables
        self._poll_interval = poll_interval
        self._capture_mode = capture_mode

        if self._capture_mode not in {"window", "desktop"}:
            raise ValueError(f"不支持的 capture_mode: {self._capture_mode}")

        self._window_manager = WindowManager() if self._capture_mode == "window" else None
        self._parsers: dict[int, ParserInfo] = {}
        self._lock = multiprocessing.Lock()
        self._desktop_regions: list[Area] = []
        self._desktop_capture: ScreenCapture | None = None

    @property
    def window_count(self) -> int:
        """当前窗口数量。"""
        return len(self._parsers)

    @property
    def parsers(self) -> list[ParserInfo]:
        """所有解析器信息。"""
        return list(self._parsers.values())

    def refresh_windows(self) -> tuple[int, int]:
        """刷新窗口列表，启动/停止对应的解析器。

        Returns:
            (新增窗口数, 关闭窗口数)
        """
        if self._capture_mode == "desktop":
            return self._refresh_desktop_regions()

        if self._window_manager is None:
            return (0, 0)

        added_windows, closed_windows = self._window_manager.refresh()

        for window in closed_windows:
            self._stop_parser(window.hwnd)

        added_count = 0
        for window in added_windows:
            if len(self._parsers) >= self._max_tables:
                LOGGER.warning(
                    "已达到最大窗口数限制 (%d)，忽略新窗口: hwnd=%d",
                    self._max_tables,
                    window.hwnd,
                )
                continue

            if self._start_parser(window):
                added_count += 1

        return added_count, len(closed_windows)

    def _refresh_desktop_regions(self) -> tuple[int, int]:
        """桌面模式：识别牌桌区域并启动/停止解析器。"""
        if self._desktop_capture is None:
            self._desktop_capture = get_screen_capture()

        rect = self._desktop_capture.get_window_rect(0)
        if rect is None:
            LOGGER.error("桌面模式：无法获取桌面尺寸")
            return (0, 0)

        _, _, screen_w, screen_h = rect

        screenshot = self._desktop_capture.capture_window(0)
        if screenshot is None:
            LOGGER.error("桌面模式：无法截图桌面")
            return (0, 0)

        regions = detect_table_regions(screenshot, max_tables=self._max_tables)
        if not regions:
            fixed = parse_fixed_table_regions(os.getenv("BAYES_POKER_DESKTOP_TABLE_RECTS"))
            if fixed:
                LOGGER.warning(
                    "桌面模式：自动识别失败，使用固定区域配置，count=%d", len(fixed)
                )
                regions = fixed

        if not regions:
            regions = fallback_grid_regions(
                screen_width=screen_w,
                screen_height=screen_h,
                max_tables=min(self._max_tables, 4),
            )
            LOGGER.warning(
                "桌面模式：自动识别与固定配置均为空，使用网格兜底，count=%d",
                len(regions),
            )

        if regions == self._desktop_regions:
            return (0, 0)

        closed_count = len(self._parsers)
        for hwnd in list(self._parsers.keys()):
            self._stop_parser(hwnd)

        # `_stop_parser()` 会触发每个进程自己的停止事件，重启前无需额外清理。
        self._desktop_regions = regions

        added_count = 0
        for idx, area in enumerate(regions):
            if len(self._parsers) >= self._max_tables:
                break

            virtual_hwnd = -10_000 - idx
            parser = TableParser(
                hwnd=virtual_hwnd,
                window_index=idx,
                capture_area=area,
                small_blind=self._small_blind,
                big_blind=self._big_blind,
                lock=self._lock,
                poll_interval=self._poll_interval,
            )
            parser.start()
            self._parsers[virtual_hwnd] = ParserInfo(
                hwnd=virtual_hwnd,
                window_index=idx,
                parser=parser,
                is_running=True,
            )
            LOGGER.info(
                "桌面模式解析器已启动: id=%d, index=%d, area=%s",
                virtual_hwnd,
                idx,
                area,
            )
            added_count += 1

        return (added_count, closed_count)

    def _start_parser(self, window: TrackedWindow) -> bool:
        """为窗口启动解析器。"""
        if window.hwnd in self._parsers:
            return False

        parser = TableParser(
            hwnd=window.hwnd,
            window_index=window.index,
            small_blind=self._small_blind,
            big_blind=self._big_blind,
            lock=self._lock,
            poll_interval=self._poll_interval,
        )

        parser.start()

        self._parsers[window.hwnd] = ParserInfo(
            hwnd=window.hwnd,
            window_index=window.index,
            parser=parser,
            is_running=True,
        )

        LOGGER.info(
            "解析器已启动: hwnd=%d, index=%d, title=%s",
            window.hwnd,
            window.index,
            window.info.title,
        )
        return True

    def _stop_parser(self, hwnd: int) -> bool:
        """停止指定窗口的解析器。"""
        if hwnd not in self._parsers:
            return False

        info = self._parsers.pop(hwnd)
        info.parser.stop()
        info.parser.join(timeout=2.0)

        if info.parser.is_alive():
            info.parser.terminate()
            LOGGER.warning("解析器强制终止: hwnd=%d", hwnd)
        else:
            LOGGER.info("解析器已停止: hwnd=%d", hwnd)

        return True

    def start_all(self) -> int:
        """启动所有解析器。

        Returns:
            启动的解析器数量
        """
        added, _ = self.refresh_windows()
        return added

    def stop_all(self) -> None:
        """停止所有解析器。"""
        for hwnd in list(self._parsers.keys()):
            self._stop_parser(hwnd)

        self._parsers.clear()
        LOGGER.info("所有解析器已停止")

    def get_parser(self, hwnd: int) -> ParserInfo | None:
        """获取指定窗口的解析器。"""
        return self._parsers.get(hwnd)

    def get_parser_by_index(self, index: int) -> ParserInfo | None:
        """根据索引获取解析器。"""
        for info in self._parsers.values():
            if info.window_index == index:
                return info
        return None

    def is_running(self) -> bool:
        """检查是否有解析器在运行。"""
        return any(
            info.is_running and info.parser.is_alive()
            for info in self._parsers.values()
        )


def create_manager(
    small_blind: float = 0.5,
    big_blind: float = 1.0,
    max_tables: int = 8,
    capture_mode: str = "window",
) -> MultiTableManager:
    """创建多牌桌管理器。"""
    return MultiTableManager(
        small_blind=small_blind,
        big_blind=big_blind,
        max_tables=max_tables,
        capture_mode=capture_mode,
    )
