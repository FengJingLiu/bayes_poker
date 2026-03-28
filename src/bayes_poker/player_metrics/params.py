from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .enums import ActionType, Position, PreflopPotType, Street, TableType


@dataclass(frozen=True)
class PreFlopParams:
    """翻前节点参数。

    该参数对象用于把翻前决策上下文映射到致密索引桶。
    """

    table_type: TableType
    position: Position
    num_callers: int
    num_raises: int
    num_active_players: int
    previous_action: ActionType
    in_position_on_flop: bool
    aggressor_first_in: bool = True
    hero_invest_raises: int = 0

    def forced_action(self) -> bool:
        """判断当前是否为强制响应节点。

        Returns:
            对大盲位仅当已出现加注时返回 True。其余位置恒为 True。
        """

        if self.position == Position.BIG_BLIND:
            return self.num_raises > 0
        return True

    def to_index(self) -> int:
        """把参数映射到 42 维翻前致密桶索引。

        Returns:
            合法桶返回 [0, 41]。非法或时空冲突场景返回 -1。
        """

        if self.table_type != TableType.SIX_MAX:
            return -1

        r = self.num_raises
        c = 1 if self.num_callers > 0 else 0

        if self.previous_action == ActionType.FOLD:
            # 阶段一: 首次行动 (First-In), 21 个桶。
            if r >= 2:
                if self.position in (Position.CO, Position.BUTTON):
                    return 19
                if self.position in (Position.SMALL_BLIND, Position.BIG_BLIND):
                    return 20
                return -1

            if self.position == Position.UTG:
                return 0 if (r == 0 and c == 0) else -1
            if self.position == Position.HJ:
                return (1 + c) if r == 0 else 3
            if self.position == Position.CO:
                return (4 + c) if r == 0 else (6 + c)
            if self.position == Position.BUTTON:
                return (8 + c) if r == 0 else (10 + c)
            if self.position == Position.SMALL_BLIND:
                return (12 + c) if r == 0 else (14 + c)
            if self.position == Position.BIG_BLIND:
                if r == 0 and c == 1:
                    return 16
                if r == 1:
                    return 17 + c
            return -1

        # 阶段二: 重入池 (Re-entry), 21 个桶。
        is_oop = 0 if self.in_position_on_flop else 1
        is_react = 0 if self.aggressor_first_in else 1

        hr = self.hero_invest_raises
        if r <= hr:
            return -1

        if self.previous_action in (ActionType.CHECK, ActionType.CALL):
            # 1. 被动重入 (Passive), 9 个桶。
            hr = min(hr, 2)
            base = 21
            if hr == 0:
                if r == 1:
                    return base + is_oop  # 21, 22
                return base + 2  # 23
            if hr == 1:
                if r == 2:
                    return base + 3 + (is_react * 2) + is_oop  # 24..27
                return base + 7  # 28
            return base + 8  # 29

        # 2. 主动重入 (Active), 12 个桶。
        hr = max(min(hr, 3), 1)
        base = 30
        if hr == 1:
            if r == 2:
                return base + (is_react * 2) + is_oop  # 30..33
            return base + 4 + is_react  # 34, 35
        if hr == 2:
            if r == 3:
                return base + 6 + (is_react * 2) + is_oop  # 36..39
            return base + 10  # 40
        return base + 11  # 41

    @staticmethod
    @lru_cache(maxsize=4)
    def get_all_params(table_type: TableType) -> tuple[PreFlopParams, ...]:
        """返回翻前参数全集并保证 42 桶全覆盖。

        Args:
            table_type: 桌型。

        Returns:
            6-max 返回致密 42 桶参数列表。其他桌型返回空元组。
        """

        if table_type != TableType.SIX_MAX:
            return tuple()

        all_params: list[PreFlopParams | None] = [None] * 42
        tt = table_type

        def _add(params: PreFlopParams) -> None:
            idx = params.to_index()
            if idx != -1 and all_params[idx] is None:
                all_params[idx] = params

        # 通过穷举注入, 由 to_index() 负责过滤并锚定到 42 个合法桶。
        for position in Position:
            if position == Position.EMPTY:
                continue
            for raises in range(6):
                for callers in range(2):
                    _add(
                        PreFlopParams(
                            table_type=tt,
                            position=position,
                            num_callers=callers,
                            num_raises=raises,
                            num_active_players=6,
                            previous_action=ActionType.FOLD,
                            in_position_on_flop=False,
                            aggressor_first_in=True,
                            hero_invest_raises=0,
                        )
                    )
                    for hero_raises in range(5):
                        for is_react in (True, False):
                            for is_oop in (False, True):
                                in_position = not is_oop
                                _add(
                                    PreFlopParams(
                                        table_type=tt,
                                        position=position,
                                        num_callers=callers,
                                        num_raises=raises,
                                        num_active_players=6,
                                        previous_action=ActionType.CALL,
                                        in_position_on_flop=in_position,
                                        aggressor_first_in=not is_react,
                                        hero_invest_raises=hero_raises,
                                    )
                                )
                                _add(
                                    PreFlopParams(
                                        table_type=tt,
                                        position=position,
                                        num_callers=callers,
                                        num_raises=raises,
                                        num_active_players=6,
                                        previous_action=ActionType.RAISE,
                                        in_position_on_flop=in_position,
                                        aggressor_first_in=not is_react,
                                        hero_invest_raises=hero_raises,
                                    )
                                )

        missing = [idx for idx, params in enumerate(all_params) if params is None]
        assert not missing, f"状态机映射失败, 存在无法触达的空桶: {missing}"
        return tuple(
            sorted(
                (
                    params
                    for params in all_params
                    if params is not None
                ),
                key=lambda params: params.to_index(),
            )
        )

    def __str__(self) -> str:
        """返回可读字符串表示。"""

        idx = self.to_index()
        if self.previous_action == ActionType.FOLD:
            if idx == 19:
                return "FirstIn, CO/BTN, R:2+, C:Any"
            if idx == 20:
                return "FirstIn, Blinds, R:2+, C:Any"
            r_str = str(self.num_raises)
            c_str = "1+" if self.num_callers > 0 else "0"
            return f"FirstIn, {self.position.name}, R:{r_str}, C:{c_str}"

        pos_str = "IP" if self.in_position_on_flop else "OOP"
        aggr_str = "Cold" if self.aggressor_first_in else "React"
        if self.previous_action in (ActionType.CHECK, ActionType.CALL):
            if idx == 23:
                return "ReEntry(Limp), Face 3B+ (Merged)"
            if idx == 28:
                return "ReEntry(CallOpen), Face 4B+ (Merged)"
            if idx == 29:
                return "ReEntry(Call3B+), Face 4B+ (Merged)"
            act = "Limp/Check" if self.hero_invest_raises == 0 else "CallOpen"
            face = "Iso" if self.num_raises == 1 else "Squeeze"
            return f"ReEntry({act}), Face {aggr_str} {face}, {pos_str}"

        if idx in (34, 35):
            return f"ReEntry(Open), Face {aggr_str} 4B+ (Merged Pos)"
        if idx == 40:
            return "ReEntry(3B), Face 5B+ (Merged)"
        if idx == 41:
            return "ReEntry(4B+), Face 5B+ (Merged)"

        act = "Open" if self.hero_invest_raises == 1 else "3B"
        face = "3B" if self.num_raises == 2 else "4B"
        return f"ReEntry({act}), Face {aggr_str} {face}, {pos_str}"


@dataclass(frozen=True)
class PostFlopParams:
    table_type: TableType
    street: Street
    round: int
    prev_action: ActionType
    num_bets: int
    in_position: bool
    num_players: int
    preflop_pot_type: PreflopPotType = PreflopPotType.SINGLE_RAISED
    is_preflop_aggressor: bool = False

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

            base_index = 0
            if self.street == Street.TURN:
                base_index = 15
            elif self.street == Street.RIVER:
                base_index = 30

            if self.in_position:
                if self.num_bets < 2:
                    base_index += prev_action_mod if self.num_bets == 0 else (3 + prev_action_mod)
                else:
                    base_index += 6 if self.num_bets == 2 else 7
            else:
                base_index += 8
                base_index += prev_action_mod if self.num_bets == 0 else (min(self.num_bets, 4) + 2)

            pot_type_val = int(self.preflop_pot_type)
            aggressor_val = 1 if self.is_preflop_aggressor else 0
            return base_index + (45 * pot_type_val) + (45 * 3 * aggressor_val)

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

        pot_type_val = int(self.preflop_pot_type)
        aggressor_val = 1 if self.is_preflop_aggressor else 0

        base_idx = a5 + (2 * a4) + (4 * a3) + (12 * prev_action_mod) + (36 * a1) + (72 * a0)
        return base_idx + (216 * pot_type_val) + (216 * 3 * aggressor_val)

    @staticmethod
    @lru_cache(maxsize=4)
    def get_all_params(table_type: TableType) -> tuple[PostFlopParams, ...]:
        all_params: list[PostFlopParams] = []
        streets = [Street.FLOP, Street.TURN, Street.RIVER]
        pot_types = [PreflopPotType.LIMPED, PreflopPotType.SINGLE_RAISED, PreflopPotType.THREE_BET_PLUS]

        if table_type == TableType.HEADS_UP:
            for pot_type in pot_types:
                for is_aggressor in (False, True):
                    for street in streets:
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.RAISE, 0, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CALL, 0, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CHECK, 0, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.RAISE, 1, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CALL, 1, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CHECK, 1, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 1, ActionType.RAISE, 2, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 1, ActionType.RAISE, 3, True, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.RAISE, 0, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CALL, 0, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 0, ActionType.CHECK, 0, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 1, ActionType.CHECK, 1, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 1, ActionType.RAISE, 2, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 2, ActionType.RAISE, 3, False, 2, pot_type, is_aggressor)
                        )
                        all_params.append(
                            PostFlopParams(table_type, street, 2, ActionType.RAISE, 4, False, 2, pot_type, is_aggressor)
                        )
        else:
            prev_actions = [ActionType.RAISE, ActionType.CALL, ActionType.CHECK]
            for pot_type in pot_types:
                for is_aggressor in (False, True):
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
                                                    pot_type,
                                                    is_aggressor,
                                                )
                                            )

        return tuple(all_params)

    def __str__(self) -> str:
        pos_str = "inp" if self.in_position else "oop"
        pot_type_str = self.preflop_pot_type.name.lower()
        aggressor_str = "aggr" if self.is_preflop_aggressor else "caller"
        return (
            f"{self.street.name}, round: {self.round} {self.prev_action.name}, "
            f"bets: {self.num_bets}, {pos_str}, pl: {self.num_players}, "
            f"pot: {pot_type_str}, {aggressor_str}"
        )
