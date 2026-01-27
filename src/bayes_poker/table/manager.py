"""多牌桌进程管理器。

管理多个牌桌解析器进程，基于桌面区域识别。
"""

from __future__ import annotations

import logging
import multiprocessing
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bayes_poker.ocr.schema import Area
from bayes_poker.screen.capture import ScreenCapture, get_screen_capture
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

    table_index: int
    capture_area: Area
    parser: TableParser
    is_running: bool = True


class MultiTableManager:
    """多牌桌管理器。

    基于桌面区域识别，管理多个牌桌解析器进程。
    """

    def __init__(
        self,
        small_blind: float = 0.5,
        big_blind: float = 1.0,
        max_tables: int = 8,
        poll_interval: float = 0.1,
    ) -> None:
        """初始化多牌桌管理器。

        Args:
            small_blind: 小盲注金额。
            big_blind: 大盲注金额。
            max_tables: 最大同时管理的牌桌数。
            poll_interval: 解析器轮询间隔（秒）。
        """
        self._small_blind = small_blind
        self._big_blind = big_blind
        self._max_tables = max_tables
        self._poll_interval = poll_interval

        self._parsers: dict[int, ParserInfo] = {}
        self._lock = multiprocessing.Lock()
        self._table_regions: list[Area] = []
        self._capture: ScreenCapture | None = None

    @property
    def table_count(self) -> int:
        """当前牌桌数量。"""
        return len(self._parsers)

    @property
    def parsers(self) -> list[ParserInfo]:
        """所有解析器信息。"""
        return list(self._parsers.values())

    def refresh_tables(self) -> tuple[int, int]:
        """刷新牌桌列表，启动/停止对应的解析器。

        Returns:
            (新增牌桌数, 关闭牌桌数)
        """
        if self._capture is None:
            self._capture = get_screen_capture()

        desktop_size = self._capture.get_desktop_size()
        if desktop_size is None:
            LOGGER.error("无法获取桌面尺寸")
            return (0, 0)

        screen_w, screen_h = desktop_size

        # 截取桌面全图用于区域检测
        screenshot = self._capture.capture_region(0, 0, screen_w, screen_h)
        if screenshot is None:
            LOGGER.error("无法截取桌面")
            return (0, 0)

        # 自动检测牌桌区域
        regions = detect_table_regions(screenshot, max_tables=self._max_tables)

        # 尝试使用固定配置
        if not regions:
            fixed = parse_fixed_table_regions(
                os.getenv("BAYES_POKER_DESKTOP_TABLE_RECTS")
            )
            if fixed:
                LOGGER.warning("自动识别失败，使用固定区域配置，count=%d", len(fixed))
                regions = fixed

        # 使用网格兜底
        if not regions:
            regions = fallback_grid_regions(
                screen_width=screen_w,
                screen_height=screen_h,
                max_tables=min(self._max_tables, 4),
            )
            LOGGER.warning(
                "自动识别与固定配置均为空，使用网格兜底，count=%d", len(regions)
            )

        # 区域未变化时不重启
        if regions == self._table_regions:
            return (0, 0)

        # 停止所有现有解析器
        closed_count = len(self._parsers)
        for table_id in list(self._parsers.keys()):
            self._stop_parser(table_id)

        self._table_regions = regions

        # 启动新解析器
        added_count = 0
        for idx, area in enumerate(regions):
            if len(self._parsers) >= self._max_tables:
                break

            parser = TableParser(
                table_index=idx,
                capture_area=area,
                small_blind=self._small_blind,
                big_blind=self._big_blind,
                lock=self._lock,
                poll_interval=self._poll_interval,
            )
            parser.start()
            self._parsers[idx] = ParserInfo(
                table_index=idx,
                capture_area=area,
                parser=parser,
                is_running=True,
            )
            LOGGER.info("解析器已启动: index=%d, area=%s", idx, area)
            added_count += 1

        return (added_count, closed_count)

    def _stop_parser(self, table_id: int) -> bool:
        """停止指定牌桌的解析器。"""
        if table_id not in self._parsers:
            return False

        info = self._parsers.pop(table_id)
        info.parser.stop()
        info.parser.join(timeout=2.0)

        if info.parser.is_alive():
            info.parser.terminate()
            LOGGER.warning("解析器强制终止: index=%d", table_id)
        else:
            LOGGER.info("解析器已停止: index=%d", table_id)

        return True

    def start_all(self) -> int:
        """启动所有解析器。

        Returns:
            启动的解析器数量
        """
        added, _ = self.refresh_tables()
        return added

    def stop_all(self) -> None:
        """停止所有解析器。"""
        for table_id in list(self._parsers.keys()):
            self._stop_parser(table_id)

        self._parsers.clear()
        LOGGER.info("所有解析器已停止")

    def get_parser(self, table_index: int) -> ParserInfo | None:
        """获取指定索引的解析器。"""
        return self._parsers.get(table_index)

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
) -> MultiTableManager:
    """创建多牌桌管理器。

    Args:
        small_blind: 小盲注金额。
        big_blind: 大盲注金额。
        max_tables: 最大同时管理的牌桌数。

    Returns:
        MultiTableManager: 多牌桌管理器实例。
    """
    return MultiTableManager(
        small_blind=small_blind,
        big_blind=big_blind,
        max_tables=max_tables,
    )
