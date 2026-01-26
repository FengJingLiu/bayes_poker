"""桌面牌桌区域识别测试。

该测试覆盖：
- 固定区域配置解析（不依赖 OpenCV）
- 网格兜底策略（不依赖 OpenCV）
"""

from __future__ import annotations

from bayes_poker.ocr.schema import Area
from bayes_poker.screen.table_region import (
    fallback_grid_regions,
    parse_fixed_table_regions,
)


def test_parse_fixed_table_regions_valid() -> None:
    regions = parse_fixed_table_regions("0,0,100,200|10,20,30,40")
    assert regions == [
        Area.from_xywh(0, 0, 100, 200),
        Area.from_xywh(10, 20, 30, 40),
    ]


def test_parse_fixed_table_regions_ignores_invalid_items() -> None:
    regions = parse_fixed_table_regions("0,0,100,200|bad|1,2,3|4,5,6,7")
    assert regions == [
        Area.from_xywh(0, 0, 100, 200),
        Area.from_xywh(4, 5, 6, 7),
    ]


def test_fallback_grid_regions_4k_4_tables() -> None:
    regions = fallback_grid_regions(screen_width=3840, screen_height=2160, max_tables=4)
    assert regions == [
        Area.from_xywh(0, 0, 1920, 1080),
        Area.from_xywh(1920, 0, 1920, 1080),
        Area.from_xywh(0, 1080, 1920, 1080),
        Area.from_xywh(1920, 1080, 1920, 1080),
    ]


def test_fallback_grid_regions_4k_2_tables() -> None:
    regions = fallback_grid_regions(screen_width=3840, screen_height=2160, max_tables=2)
    assert regions == [
        Area.from_xywh(0, 0, 1920, 2160),
        Area.from_xywh(1920, 0, 1920, 2160),
    ]

