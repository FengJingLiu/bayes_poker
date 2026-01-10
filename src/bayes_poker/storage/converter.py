"""HandHistory -> SQLite 转换器（精简版）。"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

from bayes_poker.storage.actions import extract_board_tokens
from bayes_poker.storage.hash import HASH_VERSION, compute_hand_hash
from bayes_poker.storage.models import HandPlayerRecord, HandRecord
from bayes_poker.storage.position import map_all_positions
from bayes_poker.storage.repository import HandRepository

if TYPE_CHECKING:
    from pokerkit.notation import HandHistory

LOGGER = logging.getLogger(__name__)


class HandHistoryConverter:
    def __init__(self, repository: HandRepository):
        self.repository = repository

    def convert(
        self,
        hh: HandHistory,
        source: str | None = None,
    ) -> HandRecord | None:
        try:
            return self._do_convert(hh, source)
        except Exception as e:
            LOGGER.warning("转换 HandHistory 失败: %s", e)
            return None

    def _do_convert(
        self,
        hh: HandHistory,
        source: str | None = None,
    ) -> HandRecord:
        yyyymmdd = self._compute_yyyymmdd(hh)
        seat_count = hh.seat_count or 6
        actions = list(hh.actions) if hh.actions else []

        seats = list(hh.seats) if hh.seats else []
        players = list(hh.players) if hh.players else []
        starting_stacks = list(hh.starting_stacks) if hh.starting_stacks else []

        button_seat = self._find_button_seat(hh, seats)

        position_map_by_seat: dict[int, str] = {}
        if button_seat and seats:
            position_map_by_seat = map_all_positions(
                button_seat=button_seat,
                seat_count=seat_count,
                player_seats=seats,
            )

        board_tokens = extract_board_tokens(actions)

        player_records: list[HandPlayerRecord] = []
        player_snapshots: list[tuple[str | None, str, int]] = []

        for i, seat in enumerate(seats):
            rel_pos = position_map_by_seat.get(seat)
            player_name = players[i] if i < len(players) else f"Player{i}"
            starting_stack = starting_stacks[i] if i < len(starting_stacks) else 0

            player_records.append(
                HandPlayerRecord(
                    hand_hash="",
                    player_id=0,
                    player_name=player_name,
                    yyyymmdd=yyyymmdd,
                    seat_no=seat,
                    rel_pos=rel_pos,
                    starting_stack=starting_stack,
                )
            )

            player_snapshots.append((rel_pos, player_name, starting_stack))

        hand_hash = compute_hand_hash(
            yyyymmdd=yyyymmdd,
            player_snapshots=player_snapshots,
            actions=actions,
            board_tokens=board_tokens,
        )

        for p in player_records:
            p.hand_hash = hand_hash

        phhs_blob = b""
        try:
            buffer = BytesIO()
            hh.dump(buffer)
            phhs_blob = buffer.getvalue()
        except Exception:
            pass

        return HandRecord(
            hand_hash=hand_hash,
            hash_version=HASH_VERSION,
            yyyymmdd=yyyymmdd,
            seat_count=seat_count,
            phhs_blob=phhs_blob,
            table_name=str(hh.table) if hh.table else None,
            hand_id=int(hh.hand) if hh.hand else None,
            button_seat=button_seat,
            source=source,
            players=player_records,
        )

    def _compute_yyyymmdd(self, hh: HandHistory) -> int:
        if hh.year and hh.month and hh.day:
            return hh.year * 10000 + hh.month * 100 + hh.day
        return 19700101

    def _find_button_seat(
        self,
        hh: HandHistory,
        seats: list[int],
    ) -> int | None:
        if not seats:
            return None
        return seats[0] if seats else None

    def convert_and_save(
        self,
        hh: HandHistory,
        source: str | None = None,
    ) -> bool:
        record = self.convert(hh, source)
        if record is None:
            return False

        return self.repository.insert_hand(record)

    def batch_convert_and_save(
        self,
        hands: list[HandHistory],
        source: str | None = None,
    ) -> tuple[int, int]:
        success = 0
        failed = 0

        for hh in hands:
            if self.convert_and_save(hh, source):
                success += 1
            else:
                failed += 1

        return success, failed
