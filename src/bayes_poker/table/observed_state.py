"""观察者视角的牌桌状态。

用于动态牌桌解析场景，仅记录屏幕上可见的信息。
支持 JSON 序列化用于 WebSocket 传输。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import (
    Player,
    PlayerAction,
    Position,
    get_position_by_seat,
)


def _get_position_name(hero_seat: int, btn_seat: int, player_count: int = 6) -> str:
    """根据 hero 座位和 BTN 座位计算位置名称。

    Args:
        hero_seat: Hero 座位索引。
        btn_seat: 庄家座位索引。
        player_count: 玩家总数。

    Returns:
        位置名称字符串（如 'BTN', 'SB', 'BB', 'UTG', 'MP', 'CO'）。
    """
    position = _get_position_enum(hero_seat, btn_seat, player_count)
    if position is None:
        return f"P{hero_seat}"
    return position.value


def _get_position_enum(
    hero_seat: int,
    btn_seat: int,
    player_count: int = 6,
) -> Position | None:
    """根据座位信息计算位置枚举。

    Args:
        hero_seat: Hero 座位索引。
        btn_seat: 庄家座位索引。
        player_count: 玩家总数。

    Returns:
        位置枚举, 无法计算时返回 `None`。
    """
    if btn_seat < 0 or player_count <= 0:
        return None

    if player_count == 2:
        offset = (hero_seat - btn_seat) % player_count
        return Position.SB if offset == 0 else Position.BB

    if player_count not in (6, 9):
        return None

    try:
        return get_position_by_seat(hero_seat, btn_seat, player_count)
    except Exception:
        return None


@dataclass
class ObservedTableState:
    """观察者视角的牌桌状态。

    用于动态牌桌解析场景，仅记录屏幕上可见的信息。
    支持 JSON 序列化用于 WebSocket 传输。

    Attributes:
        table_id: 牌桌标识。
        player_count: 玩家数量。
        small_blind: 小盲注。
        big_blind: 大盲注。
        hand_id: 手牌唯一标识。
        street: 当前街道。
        pot: 底池总额。
        btn_seat: 庄家座位。
        actor_seat: 当前行动玩家座位。
        hero_seat: Hero 座位。
        hero_cards: Hero 底牌。
        board_cards: 公共牌。
        players: 玩家状态列表。
        action_history: 动作历史。
        state_version: 状态版本。
        timestamp: 最后更新时间戳。
    """

    # 牌桌基本信息
    table_id: str = ""
    player_count: int = 6
    small_blind: float = 0.5
    big_blind: float = 1.0

    # 当前手牌状态
    hand_id: str = ""
    street: Street = Street.PREFLOP
    pot: float = 0.0

    # 位置信息
    btn_seat: int = -1
    actor_seat: int | None = None

    # 牌面信息
    hero_seat: int = 0
    hero_cards: tuple[str, str] | None = None
    board_cards: list[str] = field(default_factory=list)

    # 玩家状态
    players: list[Player] = field(default_factory=list)

    # 动作历史（当前手牌）
    action_history: list[PlayerAction] = field(default_factory=list)

    # 元数据
    state_version: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 JSON 传输）。

        Returns:
            包含完整状态信息的字典。
        """
        return {
            "table_id": self.table_id,
            "player_count": self.player_count,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "hand_id": self.hand_id,
            "street": self.street.value,
            "pot": self.pot,
            "btn_seat": self.btn_seat,
            "actor_seat": self.actor_seat,
            "hero_seat": self.hero_seat,
            "hero_cards": list(self.hero_cards) if self.hero_cards else None,
            "board_cards": self.board_cards,
            "players": [p.to_dict() for p in self.players],
            "action_history": [a.to_dict() for a in self.action_history],
            "state_version": self.state_version,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservedTableState":
        """从字典反序列化。

        Args:
            data: 包含状态信息的字典。

        Returns:
            ObservedTableState 实例。
        """
        hero_cards_raw = data.get("hero_cards")
        hero_cards = (
            tuple(hero_cards_raw)
            if hero_cards_raw and len(hero_cards_raw) == 2
            else None
        )

        action_history = [
            PlayerAction.from_dict(a) for a in data.get("action_history", [])
        ]

        return cls(
            table_id=data.get("table_id", ""),
            player_count=data.get("player_count", 6),
            small_blind=data.get("small_blind", 0.5),
            big_blind=data.get("big_blind", 1.0),
            hand_id=data.get("hand_id", ""),
            street=Street(data.get("street", "preflop")),
            pot=data.get("pot", 0.0),
            btn_seat=data.get("btn_seat", -1),
            actor_seat=data.get("actor_seat"),
            hero_seat=data.get("hero_seat", 0),
            hero_cards=hero_cards,
            board_cards=data.get("board_cards", []),
            players=[Player.from_dict(p) for p in data.get("players", [])],
            action_history=action_history,
            state_version=data.get("state_version", 0),
            timestamp=data.get("timestamp", 0.0),
        )

    def to_json(self) -> str:
        """序列化为 JSON 字符串。

        Returns:
            JSON 格式字符串。
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ObservedTableState":
        """从 JSON 字符串反序列化。

        Args:
            json_str: JSON 格式字符串。

        Returns:
            ObservedTableState 实例。
        """
        return cls.from_dict(json.loads(json_str))

    def record_action(
        self, seat: int, action_type: ActionType, amount: float = 0.0
    ) -> None:
        """记录玩家动作。

        Args:
            seat: 玩家座位索引。
            action_type: 动作类型。
            amount: 动作金额。
        """
        action = PlayerAction(
            player_index=seat,
            action_type=action_type,
            amount=amount,
            street=self.street,
        )
        self.action_history.append(action)

        # 同时记录到对应玩家的行动历史
        if 0 <= seat < len(self.players):
            self.players[seat].record_action(action)

        self.state_version += 1
        self.timestamp = time.time()

    def enter_new_street(self, street: Street, board_cards: list[str]) -> None:
        """进入新街道。

        Args:
            street: 新街道。
            board_cards: 公共牌列表。
        """
        self.street = street
        self.board_cards = board_cards
        self.state_version += 1
        self.timestamp = time.time()

    def start_new_hand(
        self,
        btn_seat: int,
        players: list["Player"],
        small_blind: float = 0.5,
        big_blind: float = 1.0,
    ) -> None:
        """开始新手牌。

        Args:
            btn_seat: 庄家座位。
            players: 玩家状态列表。
            small_blind: 小盲注。
            big_blind: 大盲注。
        """
        import hashlib

        hash_parts = []
        for p in players:
            if p.player_id:
                original_stack = p.stack + p.bet
                hash_parts.append(f"{p.player_id}:{original_stack:.2f}")

        seed_string = ",".join(hash_parts)

        self.hand_id = hashlib.md5(seed_string.encode("utf-8")).hexdigest()[:8]
        self.btn_seat = btn_seat
        self.street = Street.PREFLOP
        self.pot = 0.0
        self.board_cards = []
        self.hero_cards = None
        self.action_history : list[PlayerAction] = []
        self.small_blind = small_blind
        self.big_blind = big_blind

        # 将 Player 列表存储到 players
        self.players = [
            Player(
                seat_index=p.seat_index,
                player_id=p.player_id,
                stack=p.stack,
                bet=p.bet,
                position=_get_position_enum(p.seat_index, btn_seat, len(players)),
                is_folded=p.is_folded,
                is_thinking=p.is_thinking,
                is_button=p.is_button,
                vpip=p.vpip,
                action_history=[],
            )
            for p in players
        ]

        self.state_version = 0
        self.timestamp = time.time()

    def update_players(self, players: list["Player"]) -> None:
        """更新玩家状态。

        Args:
            players: 玩家状态列表。
        """
        # 保留现有玩家的行动历史
        existing_histories: dict[int, list[PlayerAction]] = {
            player.seat_index: player.action_history for player in self.players
        }

        self.players = [
            Player(
                seat_index=p.seat_index,
                player_id=p.player_id,
                stack=p.stack,
                bet=p.bet,
                position=_get_position_enum(
                    p.seat_index,
                    self.btn_seat,
                    len(players),
                ),
                is_folded=p.is_folded,
                is_thinking=p.is_thinking,
                is_button=p.is_button,
                vpip=p.vpip,
                action_history=existing_histories.get(p.seat_index, []),
            )
            for p in players
        ]

    def update_pot(self, pot: float) -> None:
        """更新底池。

        Args:
            pot: 底池总额。
        """
        self.pot = pot

    def set_hero_cards(self, cards: tuple[str, str]) -> None:
        """设置 Hero 底牌。

        Args:
            cards: 底牌元组，如 ("As", "Kd")。
        """
        self.hero_cards = cards

    def get_hero_stack_bb(self) -> float:
        """获取 Hero 筹码（BB 单位）。

        Returns:
            Hero 筹码（以大盲注为单位）。
        """
        if self.hero_seat < 0 or self.hero_seat >= len(self.players):
            return 0.0

        hero_player = self.players[self.hero_seat]
        return hero_player.get_stack_bb(self.big_blind)

    def get_hero_position(self) -> str:
        """获取 Hero 位置名称。

        Returns:
            位置名称字符串（如 'BTN', 'SB', 'BB', 'UTG', 'MP', 'CO'）。
        """
        return _get_position_name(self.hero_seat, self.btn_seat, self.player_count)

    def get_hero_position_enum(self) -> Position | None:
        """获取 Hero 位置枚举。

        Returns:
            Hero 的位置枚举, 无法计算时返回 `None`。
        """
        return _get_position_enum(self.hero_seat, self.btn_seat, self.player_count)

    def get_action_history_string(self) -> str:
        """获取动作历史字符串（用于策略查询）。

        Returns:
            动作历史字符串，格式如 'F-C-R8'。
        """
        tokens: list[str] = []

        for action in self.action_history:
            if action.action_type == ActionType.FOLD:
                tokens.append("F")
            elif action.action_type in (ActionType.CHECK, ActionType.CALL):
                tokens.append("C")
            elif action.action_type in (
                ActionType.BET,
                ActionType.RAISE,
                ActionType.ALL_IN,
            ):
                # 金额转换为 BB 单位
                if self.big_blind > 0:
                    amount_bb = action.amount / self.big_blind
                    amount_str = f"{amount_bb:.1f}".rstrip("0").rstrip(".")
                else:
                    amount_str = f"{action.amount:.0f}"
                tokens.append(f"R{amount_str}")

        return "-".join(tokens)


def create_observed_state(
    player_count: int = 6,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
    table_id: str = "",
) -> ObservedTableState:
    """创建观察者状态实例。

    Args:
        player_count: 玩家数量。
        small_blind: 小盲注。
        big_blind: 大盲注。
        table_id: 牌桌标识。

    Returns:
        ObservedTableState 实例。
    """
    return ObservedTableState(
        table_id=table_id or str(uuid.uuid4())[:8],
        player_count=player_count,
        small_blind=small_blind,
        big_blind=big_blind,
    )
