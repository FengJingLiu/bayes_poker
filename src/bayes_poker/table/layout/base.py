"""布局配置基类。

定义牌桌布局的抽象接口，支持动态缩放和多种牌桌尺寸。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bayes_poker.domain.table import (
    Position,
    SEAT_ORDER_6MAX,
    SEAT_ORDER_9MAX,
    get_position_by_seat,
)
from bayes_poker.ocr.schema import (
    Area,
    AreaColorCheck,
    Color,
    ColorCheckConfig,
    MultiPointColorCheck,
    Point,
    PointColorCheck,
    RelativeArea,
    RelativePoint,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class PlayerLayoutConfig:
    """单个玩家位置的布局配置（相对坐标）。"""

    id_ocr: RelativeArea
    chip_ocr: RelativeArea
    vpip_ocr: RelativeArea
    bet_size_ocr: RelativeArea

    bet_icon_color_check: AreaColorCheck
    btn_icon_color_check: AreaColorCheck
    thinking_bar_check: PointColorCheck
    fold_check: MultiPointColorCheck


@dataclass
class TableLayoutConfig:
    """牌桌全局元素的布局配置（相对坐标）。"""

    hero_left_card_rank_ocr: RelativeArea
    hero_left_card_color: RelativePoint
    hero_right_card_rank_ocr: RelativeArea
    hero_right_card_color: RelativePoint

    btn_fold_color_check: AreaColorCheck
    btn_call_color_check: AreaColorCheck
    btn_raise_color_check: AreaColorCheck

    size_input_area: RelativeArea

    flop_detect_points: list[RelativePoint]
    flop_detect_color: ColorCheckConfig
    turn_detect_point: RelativePoint
    turn_detect_color: ColorCheckConfig
    river_detect_point: RelativePoint
    river_detect_color: ColorCheckConfig

    flop_detect_rank_areas: list[RelativeArea]
    flop_detect_rank_color: ColorCheckConfig
    turn_detect_rank_area: RelativeArea
    turn_detect_rank_color: ColorCheckConfig
    river_detect_rank_area: RelativeArea
    river_detect_rank_color: ColorCheckConfig

    board_color_points: list[RelativePoint]
    board_rank_ocr_areas: list[RelativeArea]

    ori_pot_size_ocr: RelativeArea
    cur_pot_size_ocr: RelativeArea


class TableLayout(ABC):
    """牌桌布局抽象基类。

    定义了获取各种元素绝对坐标的接口，子类需实现具体配置。
    """

    @property
    @abstractmethod
    def base_width(self) -> int:
        """基准宽度（像素）。"""
        ...

    @property
    @abstractmethod
    def base_height(self) -> int:
        """基准高度（像素）。"""
        ...

    @property
    @abstractmethod
    def player_count(self) -> int:
        """玩家数量。"""
        ...

    @abstractmethod
    def get_player_config(self, index: int) -> PlayerLayoutConfig:
        """获取指定座位的玩家布局配置（相对坐标）。"""
        ...

    @abstractmethod
    def get_table_config(self) -> TableLayoutConfig:
        """获取牌桌全局布局配置（相对坐标）。"""
        ...


@dataclass
class ScaledLayout:
    """缩放后的布局实例。

    根据实际窗口尺寸，将相对坐标转换为绝对坐标。
    """

    layout: TableLayout
    actual_width: int
    actual_height: int
    _scale_x: float = field(init=False)
    _scale_y: float = field(init=False)

    def __post_init__(self) -> None:
        self._scale_x = self.actual_width / self.layout.base_width
        self._scale_y = self.actual_height / self.layout.base_height

    def _to_absolute_point(self, rel: RelativePoint) -> Point:
        return Point(
            int(rel.x * self.actual_width),
            int(rel.y * self.actual_height),
        )

    def _to_absolute_area(self, rel: RelativeArea) -> Area:
        return Area(
            int(rel.x1 * self.actual_width),
            int(rel.y1 * self.actual_height),
            int(rel.x2 * self.actual_width),
            int(rel.y2 * self.actual_height),
        )

    def get_player_id_ocr_area(self, index: int) -> Area:
        config = self.layout.get_player_config(index)
        return self._to_absolute_area(config.id_ocr)

    def get_player_chip_ocr_area(self, index: int) -> Area:
        config = self.layout.get_player_config(index)
        return self._to_absolute_area(config.chip_ocr)

    def get_player_vpip_ocr_area(self, index: int) -> Area:
        config = self.layout.get_player_config(index)
        return self._to_absolute_area(config.vpip_ocr)

    def get_player_bet_size_ocr_area(self, index: int) -> Area:
        config = self.layout.get_player_config(index)
        return self._to_absolute_area(config.bet_size_ocr)

    def get_player_bet_icon_check(self, index: int) -> tuple[Area, Color, int, float]:
        config = self.layout.get_player_config(index)
        check = config.bet_icon_color_check
        if isinstance(check.area, RelativeArea):
            area = self._to_absolute_area(check.area)
        else:
            area = check.area
        return (
            area,
            check.config.color,
            check.config.tolerance,
            check.config.threshold,
        )

    def get_player_btn_icon_check(self, index: int) -> tuple[Area, Color, int, float]:
        config = self.layout.get_player_config(index)
        check = config.btn_icon_color_check
        if isinstance(check.area, RelativeArea):
            area = self._to_absolute_area(check.area)
        else:
            area = check.area
        return (
            area,
            check.config.color,
            check.config.tolerance,
            check.config.threshold,
        )

    def get_player_thinking_bar_check(self, index: int) -> tuple[Point, Color, int]:
        config = self.layout.get_player_config(index)
        check = config.thinking_bar_check
        if isinstance(check.point, RelativePoint):
            point = self._to_absolute_point(check.point)
        else:
            point = check.point
        return (point, check.config.color, check.config.tolerance)

    def get_player_fold_check(self, index: int) -> tuple[list[Point], Color, int]:
        config = self.layout.get_player_config(index)
        check = config.fold_check
        points = []
        for p in check.points:
            if isinstance(p, RelativePoint):
                points.append(self._to_absolute_point(p))
            else:
                points.append(p)
        return (points, check.config.color, check.config.tolerance)

    def get_hero_card_rank_ocr_areas(self) -> tuple[Area, Area]:
        table_config = self.layout.get_table_config()
        return (
            self._to_absolute_area(table_config.hero_left_card_rank_ocr),
            self._to_absolute_area(table_config.hero_right_card_rank_ocr),
        )

    def get_hero_card_color_points(self) -> tuple[Point, Point]:
        table_config = self.layout.get_table_config()
        return (
            self._to_absolute_point(table_config.hero_left_card_color),
            self._to_absolute_point(table_config.hero_right_card_color),
        )

    def get_btn_fold_check(self) -> tuple[Area, Color, int, float]:
        table_config = self.layout.get_table_config()
        check = table_config.btn_fold_color_check
        if isinstance(check.area, RelativeArea):
            area = self._to_absolute_area(check.area)
        else:
            area = check.area
        return (
            area,
            check.config.color,
            check.config.tolerance,
            check.config.threshold,
        )

    def get_btn_call_check(self) -> tuple[Area, Color, int, float]:
        table_config = self.layout.get_table_config()
        check = table_config.btn_call_color_check
        if isinstance(check.area, RelativeArea):
            area = self._to_absolute_area(check.area)
        else:
            area = check.area
        return (
            area,
            check.config.color,
            check.config.tolerance,
            check.config.threshold,
        )

    def get_btn_raise_check(self) -> tuple[Area, Color, int, float]:
        table_config = self.layout.get_table_config()
        check = table_config.btn_raise_color_check
        if isinstance(check.area, RelativeArea):
            area = self._to_absolute_area(check.area)
        else:
            area = check.area
        return (
            area,
            check.config.color,
            check.config.tolerance,
            check.config.threshold,
        )

    def get_flop_detect_points(self) -> list[Point]:
        table_config = self.layout.get_table_config()
        return [self._to_absolute_point(p) for p in table_config.flop_detect_points]

    def get_flop_detect_color(self) -> ColorCheckConfig:
        return self.layout.get_table_config().flop_detect_color

    def get_turn_detect_point(self) -> Point:
        return self._to_absolute_point(self.layout.get_table_config().turn_detect_point)

    def get_river_detect_point(self) -> Point:
        return self._to_absolute_point(
            self.layout.get_table_config().river_detect_point
        )

    def get_board_color_point(self, index: int) -> Point:
        table_config = self.layout.get_table_config()
        return self._to_absolute_point(table_config.board_color_points[index])

    def get_board_rank_ocr_area(self, index: int) -> Area:
        table_config = self.layout.get_table_config()
        return self._to_absolute_area(table_config.board_rank_ocr_areas[index])

    def get_ori_pot_size_ocr_area(self) -> Area:
        return self._to_absolute_area(self.layout.get_table_config().ori_pot_size_ocr)

    def get_cur_pot_size_ocr_area(self) -> Area:
        return self._to_absolute_area(self.layout.get_table_config().cur_pot_size_ocr)
