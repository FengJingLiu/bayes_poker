"""GGPoker 6-max 牌桌布局配置。

基于源项目 gg_6max_zoom_pos_info.py 的坐标配置，转换为相对坐标。
基准尺寸：1491 x 1056
"""

from __future__ import annotations

from bayes_poker.ocr.schema import (
    AreaColorCheck,
    Color,
    ColorCheckConfig,
    MultiPointColorCheck,
    PointColorCheck,
    RelativeArea,
    RelativePoint,
)
from bayes_poker.table.layout.base import (
    PlayerLayoutConfig,
    TableLayout,
    TableLayoutConfig,
)

BASE_WIDTH = 1491
BASE_HEIGHT = 1056


def _rel_area(x1: int, y1: int, x2: int, y2: int) -> RelativeArea:
    return RelativeArea(
        x1 / BASE_WIDTH,
        y1 / BASE_HEIGHT,
        x2 / BASE_WIDTH,
        y2 / BASE_HEIGHT,
    )


def _rel_point(x: int, y: int) -> RelativePoint:
    return RelativePoint(x / BASE_WIDTH, y / BASE_HEIGHT)


_PLAYER_CONFIGS = [
    PlayerLayoutConfig(
        id_ocr=_rel_area(656, 916, 656 + 190, 916 + 36),
        chip_ocr=_rel_area(658, 954, 658 + 180, 954 + 36),
        vpip_ocr=_rel_area(654, 884, 654 + 28, 884 + 20),
        bet_size_ocr=_rel_area(696, 693, 696 + 110, 693 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(696, 693, 696 + 110, 693 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(630, 715, 670, 755),
            config=ColorCheckConfig(Color(236, 197, 35), 10, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(660, 1004),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(673, 845), _rel_point(750, 839)],
            config=ColorCheckConfig(Color(244, 244, 244), 25),
        ),
    ),
    PlayerLayoutConfig(
        id_ocr=_rel_area(78, 736, 78 + 190, 736 + 36),
        chip_ocr=_rel_area(84, 772, 84 + 180, 772 + 36),
        vpip_ocr=_rel_area(80, 706, 80 + 28, 706 + 20),
        bet_size_ocr=_rel_area(286, 639, 286 + 110, 639 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(286, 639, 286 + 110, 639 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(310, 685, 353, 725),
            config=ColorCheckConfig(Color(236, 197, 35), 10, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(85, 816),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(75, 644), _rel_point(249, 644)],
            config=ColorCheckConfig(Color(244, 244, 244), 10),
        ),
    ),
    PlayerLayoutConfig(
        id_ocr=_rel_area(124, 302, 124 + 190, 302 + 36),
        chip_ocr=_rel_area(130, 338, 130 + 180, 338 + 36),
        vpip_ocr=_rel_area(126, 274, 126 + 28, 274 + 20),
        bet_size_ocr=_rel_area(331, 375, 331 + 110, 375 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(331, 375, 331 + 110, 375 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(316, 340, 356, 376),
            config=ColorCheckConfig(Color(236, 197, 35), 10, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(132, 383),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(121, 213), _rel_point(296, 212)],
            config=ColorCheckConfig(Color(244, 244, 244), 10),
        ),
    ),
    PlayerLayoutConfig(
        id_ocr=_rel_area(660, 198, 660 + 190, 198 + 36),
        chip_ocr=_rel_area(666, 232, 666 + 180, 232 + 36),
        vpip_ocr=_rel_area(662, 168, 662 + 28, 168 + 20),
        bet_size_ocr=_rel_area(688, 322, 688 + 110, 322 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(688, 322, 688 + 110, 322 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(659, 279, 701, 314),
            config=ColorCheckConfig(Color(236, 197, 35), 10, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(668, 278),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(657, 107), _rel_point(832, 109)],
            config=ColorCheckConfig(Color(244, 244, 244), 10),
        ),
    ),
    PlayerLayoutConfig(
        id_ocr=_rel_area(1196, 302, 1196 + 190, 302 + 36),
        chip_ocr=_rel_area(1202, 336, 1202 + 180, 336 + 36),
        vpip_ocr=_rel_area(1198, 274, 1198 + 28, 274 + 20),
        bet_size_ocr=_rel_area(1040, 374, 1040 + 110, 374 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(1040, 374, 1040 + 110, 374 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(1134, 338, 1177, 376),
            config=ColorCheckConfig(Color(236, 197, 35), 10, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(1203, 381),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(1193, 210), _rel_point(1367, 210)],
            config=ColorCheckConfig(Color(244, 244, 244), 10),
        ),
    ),
    PlayerLayoutConfig(
        id_ocr=_rel_area(1242, 736, 1242 + 190, 736 + 36),
        chip_ocr=_rel_area(1248, 770, 1248 + 180, 770 + 36),
        vpip_ocr=_rel_area(1244, 706, 1244 + 28, 706 + 20),
        bet_size_ocr=_rel_area(1087, 639, 1087 + 110, 639 + 36),
        bet_icon_color_check=AreaColorCheck(
            area=_rel_area(1087, 639, 1087 + 110, 639 + 36),
            config=ColorCheckConfig(Color(235, 235, 235), 25, 0.05),
        ),
        btn_icon_color_check=AreaColorCheck(
            area=_rel_area(1138, 688, 1176, 723),
            config=ColorCheckConfig(Color(236, 197, 35), 25, 0.05),
        ),
        thinking_bar_check=PointColorCheck(
            point=_rel_point(1250, 817),
            config=ColorCheckConfig(Color(224, 245, 56), 25),
        ),
        fold_check=MultiPointColorCheck(
            points=[_rel_point(1241, 643), _rel_point(1414, 644)],
            config=ColorCheckConfig(Color(235, 235, 235), 25),
        ),
    ),
]

_TABLE_CONFIG = TableLayoutConfig(
    hero_left_card_rank_ocr=_rel_area(650, 782, 693, 826),
    hero_left_card_color=_rel_point(706, 800),
    hero_right_card_rank_ocr=_rel_area(733, 776, 772, 817),
    hero_right_card_color=_rel_point(800, 810),
    btn_fold_color_check=AreaColorCheck(
        area=_rel_area(931, 941, 1067, 1016),
        config=ColorCheckConfig(Color(180, 60, 60), 40, 0.5),
    ),
    btn_call_color_check=AreaColorCheck(
        area=_rel_area(1123, 941, 1257, 1016),
        config=ColorCheckConfig(Color(180, 60, 60), 40, 0.5),
    ),
    btn_raise_color_check=AreaColorCheck(
        area=_rel_area(1313, 941, 1448, 1016),
        config=ColorCheckConfig(Color(180, 60, 60), 40, 0.5),
    ),
    size_input_area=_rel_area(1225, 880, 1313, 906),
    flop_detect_points=[
        _rel_point(458, 487),
        _rel_point(586, 487),
        _rel_point(712, 487),
    ],
    flop_detect_color=ColorCheckConfig(Color(235, 235, 235), 25),
    turn_detect_point=_rel_point(840, 487),
    turn_detect_color=ColorCheckConfig(Color(235, 235, 235), 25),
    river_detect_point=_rel_point(966, 487),
    river_detect_color=ColorCheckConfig(Color(235, 235, 235), 25),
    flop_detect_rank_areas=[
        _rel_area(446, 430, 478, 500),
        _rel_area(570, 430, 605, 500),
        _rel_area(700, 430, 730, 500),
    ],
    flop_detect_rank_color=ColorCheckConfig(Color(235, 235, 235), 25, 0.1),
    turn_detect_rank_area=_rel_area(823, 430, 853, 500),
    turn_detect_rank_color=ColorCheckConfig(Color(235, 235, 235), 25, 0.1),
    river_detect_rank_area=_rel_area(951, 430, 987, 500),
    river_detect_rank_color=ColorCheckConfig(Color(235, 235, 235), 25, 0.1),
    board_color_points=[
        _rel_point(515, 446),
        _rel_point(641, 446),
        _rel_point(767, 446),
        _rel_point(893, 446),
        _rel_point(1019, 446),
    ],
    board_rank_ocr_areas=[
        _rel_area(446, 428, 446 + 36, 428 + 36),
        _rel_area(572, 428, 572 + 36, 428 + 36),
        _rel_area(698, 428, 698 + 36, 428 + 36),
        _rel_area(824, 428, 824 + 36, 428 + 36),
        _rel_area(950, 428, 950 + 36, 428 + 36),
    ],
    ori_pot_size_ocr=_rel_area(686, 602, 686 + 120, 602 + 34),
    cur_pot_size_ocr=_rel_area(626, 376, 626 + 235, 376 + 34),
)


class GGPoker6MaxLayout(TableLayout):
    """GGPoker 6-max 牌桌布局。"""

    @property
    def base_width(self) -> int:
        return BASE_WIDTH

    @property
    def base_height(self) -> int:
        return BASE_HEIGHT

    @property
    def player_count(self) -> int:
        return 6

    def get_player_config(self, index: int) -> PlayerLayoutConfig:
        if not 0 <= index < 6:
            raise IndexError(f"玩家索引超出范围: {index}")
        return _PLAYER_CONFIGS[index]

    def get_table_config(self) -> TableLayoutConfig:
        return _TABLE_CONFIG


def get_gg_6max_layout() -> GGPoker6MaxLayout:
    """获取 GGPoker 6-max 布局实例。"""
    return GGPoker6MaxLayout()
