"""6-max 位置映射。"""

from __future__ import annotations

# 6-max 位置顺序（从 BTN 开始顺时针）
POSITIONS_6MAX = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
POSITIONS_5MAX = ["BTN", "SB", "BB", "UTG", "CO"]
POSITIONS_4MAX = ["BTN", "SB", "BB", "UTG"]
POSITIONS_3MAX = ["BTN", "SB", "BB"]
POSITIONS_2MAX = ["BTN", "BB"]


def get_position_list(player_count: int) -> list[str]:
    if player_count >= 6:
        return POSITIONS_6MAX
    elif player_count == 5:
        return POSITIONS_5MAX
    elif player_count == 4:
        return POSITIONS_4MAX
    elif player_count == 3:
        return POSITIONS_3MAX
    else:
        return POSITIONS_2MAX


def compute_relative_position(
    seat_no: int,
    button_seat: int,
    seat_count: int,
    occupied_seats: list[int],
) -> str | None:
    """
    计算玩家的相对位置。

    Args:
        seat_no: 玩家座位号 (1-based)
        button_seat: 按钮位座位号 (1-based)
        seat_count: 最大座位数
        occupied_seats: 所有在座玩家的座位号列表

    Returns:
        相对位置字符串 (BTN/SB/BB/UTG/MP/CO)，若无法计算返回 None
    """
    if not occupied_seats or button_seat not in occupied_seats:
        return None

    sorted_seats = sorted(occupied_seats)
    player_count = len(sorted_seats)
    positions = get_position_list(player_count)

    btn_index = sorted_seats.index(button_seat)

    ordered_seats = []
    for i in range(player_count):
        idx = (btn_index + i) % player_count
        ordered_seats.append(sorted_seats[idx])

    if seat_no not in ordered_seats:
        return None

    position_index = ordered_seats.index(seat_no)

    if position_index < len(positions):
        return positions[position_index]

    return None


def map_all_positions(
    button_seat: int,
    seat_count: int,
    player_seats: list[int],
) -> dict[int, str]:
    """
    为所有玩家计算相对位置映射。

    Returns:
        dict[seat_no, rel_pos]
    """
    result = {}
    for seat_no in player_seats:
        pos = compute_relative_position(
            seat_no=seat_no,
            button_seat=button_seat,
            seat_count=seat_count,
            occupied_seats=player_seats,
        )
        if pos:
            result[seat_no] = pos
    return result
