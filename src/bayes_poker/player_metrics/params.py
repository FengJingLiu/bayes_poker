from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .enums import ActionType, Position, Street, TableType


@dataclass(frozen=True)
class PreFlopParams:
    table_type: TableType
    position: Position
    num_callers: int
    num_raises: int
    num_active_players: int
    previous_action: ActionType
    in_position_on_flop: bool

    def forced_action(self) -> bool:
        if self.position == Position.BIG_BLIND:
            return self.num_raises > 0
        return True

    def to_index(self) -> int:
        if self.table_type == TableType.HEADS_UP:
            if self.position == Position.SMALL_BLIND:
                return min(self.num_raises, 4)
            elif self.position == Position.BIG_BLIND:
                return 5 + min(self.num_raises, 4)
            else:
                raise ValueError(f"Invalid position for HU: {self.position}")

        if self.previous_action == ActionType.FOLD:
            a0 = int(self.position)
            a1 = -1
            if self.num_raises == 0:
                a1 = 0 if self.num_callers == 0 else 1
            elif self.num_raises == 1:
                a1 = 2 if self.num_callers == 0 else 3
            elif self.num_raises >= 2:
                a1 = 4

            assert a0 != -1 and a1 != -1, f"Invalid params: pos={a0}, callers/raises combo"
            return (5 * a0) + a1

        a0 = -1
        if self.previous_action in (ActionType.CHECK, ActionType.CALL):
            a0 = 0
        elif self.previous_action in (ActionType.BET, ActionType.RAISE):
            a0 = 1

        a1 = 0 if self.in_position_on_flop else 1
        a2 = 0 if self.num_active_players == 2 else 1

        a3 = -1
        if self.num_raises == 1:
            a3 = 0 if self.num_callers == 0 else 1
        elif self.num_raises >= 2:
            a3 = 2

        assert a0 != -1 and a3 != -1
        return 30 + (12 * a0) + (6 * a1) + (3 * a2) + a3

    @staticmethod
    @lru_cache(maxsize=4)
    def get_all_params(table_type: TableType) -> tuple[PreFlopParams, ...]:
        all_params: list[PreFlopParams] = []

        if table_type == TableType.HEADS_UP:
            for num_raises in range(5):
                all_params.append(
                    PreFlopParams(
                        table_type, Position.SMALL_BLIND, 0, num_raises, 2, ActionType.FOLD, True
                    )
                )
            for num_raises in range(5):
                all_params.append(
                    PreFlopParams(
                        table_type, Position.BIG_BLIND, 0, num_raises, 2, ActionType.FOLD, False
                    )
                )
        else:
            for pos in Position:
                if pos == Position.EMPTY:
                    continue
                all_params.append(
                    PreFlopParams(
                        table_type, pos, 0, 0, int(table_type), ActionType.FOLD, False
                    )
                )
                all_params.append(
                    PreFlopParams(
                        table_type, pos, 1, 0, int(table_type), ActionType.FOLD, False
                    )
                )
                all_params.append(
                    PreFlopParams(
                        table_type, pos, 0, 1, int(table_type), ActionType.FOLD, False
                    )
                )
                all_params.append(
                    PreFlopParams(
                        table_type, pos, 1, 1, int(table_type), ActionType.FOLD, False
                    )
                )
                all_params.append(
                    PreFlopParams(
                        table_type, pos, 0, 2, int(table_type), ActionType.FOLD, False
                    )
                )

            prev_actions = [ActionType.CHECK, ActionType.RAISE]
            for prev_action in prev_actions:
                for in_pos in (False, True):
                    for num_pl in (2, 3):
                        all_params.append(
                            PreFlopParams(
                                table_type,
                                Position.BIG_BLIND,
                                0,
                                1,
                                num_pl,
                                prev_action,
                                in_pos,
                            )
                        )
                        all_params.append(
                            PreFlopParams(
                                table_type,
                                Position.BIG_BLIND,
                                1,
                                1,
                                num_pl,
                                prev_action,
                                in_pos,
                            )
                        )
                        all_params.append(
                            PreFlopParams(
                                table_type,
                                Position.BIG_BLIND,
                                0,
                                2,
                                num_pl,
                                prev_action,
                                in_pos,
                            )
                        )

        return tuple(all_params)

    def __str__(self) -> str:
        if self.previous_action == ActionType.FOLD:
            return (
                f"{self.previous_action.name}, {self.position.name}, "
                f"bets: {self.num_raises}, limpers: {self.num_callers}"
            )
        pos_str = "inp" if self.in_position_on_flop else "oop"
        return (
            f"{self.previous_action.name}, {pos_str}, "
            f"players: {self.num_active_players}, raises: {self.num_raises}, "
            f"callers: {self.num_callers}"
        )


@dataclass(frozen=True)
class PostFlopParams:
    table_type: TableType
    street: Street
    round: int
    prev_action: ActionType
    num_bets: int
    in_position: bool
    num_players: int

    def forced_action(self) -> bool:
        return self.num_bets > 0

    def to_index(self) -> int:
        prev_action_mod = -1
        if self.prev_action in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            prev_action_mod = 0
        elif self.prev_action == ActionType.CALL:
            prev_action_mod = 1
        elif self.prev_action == ActionType.CHECK:
            prev_action_mod = 2

        if prev_action_mod == -1:
            prev_action_mod = 0

        if self.table_type == TableType.HEADS_UP:
            assert self.street in (Street.FLOP, Street.TURN, Street.RIVER)

            index = 0
            if self.street == Street.TURN:
                index = 15
            elif self.street == Street.RIVER:
                index = 30

            if self.in_position:
                if self.num_bets < 2:
                    index += prev_action_mod if self.num_bets == 0 else (3 + prev_action_mod)
                else:
                    index += 6 if self.num_bets == 2 else 7
            else:
                index += 8
                index += prev_action_mod if self.num_bets == 0 else (min(self.num_bets, 4) + 2)

            return index

        a0 = -1
        if self.street == Street.FLOP:
            a0 = 0
        elif self.street == Street.TURN:
            a0 = 1
        elif self.street == Street.RIVER:
            a0 = 2

        if a0 == -1:
            a0 = 0

        a1 = 0 if self.round == 0 else 1

        a3 = 0
        if self.num_bets <= 0:
            a3 = 0
        elif self.num_bets == 1:
            a3 = 1
        elif self.num_bets >= 2:
            a3 = 2

        a4 = 1 if self.in_position else 0

        a5 = 0 if self.num_players <= 2 else 1

        return a5 + (2 * a4) + (4 * a3) + (12 * prev_action_mod) + (36 * a1) + (72 * a0)

    @staticmethod
    @lru_cache(maxsize=4)
    def get_all_params(table_type: TableType) -> tuple[PostFlopParams, ...]:
        all_params: list[PostFlopParams] = []
        streets = [Street.FLOP, Street.TURN, Street.RIVER]

        if table_type == TableType.HEADS_UP:
            for street in streets:
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.RAISE, 0, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CALL, 0, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CHECK, 0, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.RAISE, 1, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CALL, 1, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CHECK, 1, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 1, ActionType.RAISE, 2, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 1, ActionType.RAISE, 3, True, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.RAISE, 0, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CALL, 0, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 0, ActionType.CHECK, 0, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 1, ActionType.CHECK, 1, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 1, ActionType.RAISE, 2, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 2, ActionType.RAISE, 3, False, 2)
                )
                all_params.append(
                    PostFlopParams(table_type, street, 2, ActionType.RAISE, 4, False, 2)
                )
        else:
            prev_actions = [ActionType.RAISE, ActionType.CALL, ActionType.CHECK]
            for street in streets:
                for round_num in range(2):
                    for prev_action in prev_actions:
                        for num_bets in range(3):
                            for in_pos in (False, True):
                                for num_pl in (2, 3):
                                    all_params.append(
                                        PostFlopParams(
                                            table_type,
                                            street,
                                            round_num,
                                            prev_action,
                                            num_bets,
                                            in_pos,
                                            num_pl,
                                        )
                                    )

        return tuple(all_params)

    def __str__(self) -> str:
        pos_str = "inp" if self.in_position else "oop"
        return (
            f"{self.street.name}, round: {self.round} {self.prev_action.name}, "
            f"bets: {self.num_bets}, {pos_str}, pl: {self.num_players}"
        )
