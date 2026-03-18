"""真实场景测试公共工具函数与数据结构。

提供从 player_core_stats.csv 加载玩家样本、构造 ObservedTableState、
导出 GTO+ 范围文本、打印策略快照等可复用能力。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
)
from bayes_poker.strategy.strategy_engine.utg_open_ev_validation import (
    parse_percent_value,
    sanitize_filename,
)
from bayes_poker.table.observed_state import ObservedTableState

from bayes_poker.player_metrics.enums import (
    ActionType as MetricsActionType,
    TableType,
)
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.estimated_ad import EstimatedAD
from bayes_poker.player_metrics.params import PreFlopParams, PostFlopParams

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
STRATEGY_DB_PATH: Path = REPO_ROOT / "data" / "database" / "preflop_strategy.sqlite3"
PLAYER_STATS_DB_PATH: Path = REPO_ROOT / "data" / "database" / "player_stats.db"
PLAYER_CORE_STATS_CSV_PATH: Path = (
    REPO_ROOT / "data" / "database" / "player_core_stats.csv"
)
RUN_REAL_SCENARIO_ENV: str = "BAYES_POKER_RUN_REAL_SCENARIO_TESTS"

# 6-max 翻前行动顺序: UTG -> MP -> CO -> BTN -> SB -> BB
PREFLOP_ACTION_ORDER_6MAX: list[Position] = [
    Position.UTG,
    Position.MP,
    Position.CO,
    Position.BTN,
    Position.SB,
    Position.BB,
]

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlayerPfrRow:
    """玩家核心统计中的 PFR 行视图。

    Attributes:
        player_name: 玩家名。
        total_hands: 总手数。
        pfr_pct: PFR 百分比值。
    """

    player_name: str
    total_hands: int
    pfr_pct: float


@dataclass(frozen=True, slots=True)
class HeroStrategySnapshot:
    """单个玩家场景下的 Hero 策略快照。

    Attributes:
        player_name: 对手玩家名。
        total_hands: 对手总手数。
        pfr_pct: 对手 PFR 百分比。
        selected_node_id: Hero 命中的策略节点 ID。
        selected_source_id: Hero 命中的策略源 ID。
        action_distribution: Hero 调整后的动作分布 (posterior)。
        prior_action_distribution: Hero 调整前的 GTO 先验动作分布。
        opponent_aggression_details: 逐对手 prior/posterior/ratio 明细。
        sampling_random: 采样随机数。
        sampled_action_code: 采样选中的动作编码。
        gtoplus_by_action: 各动作的 GTO+ 范围文本。
    """

    player_name: str
    total_hands: int
    pfr_pct: float
    selected_node_id: int
    selected_source_id: int
    action_distribution: dict[str, float]
    prior_action_distribution: dict[str, float]
    opponent_aggression_details: list[dict[str, object]]
    sampling_random: float
    sampled_action_code: str | None
    gtoplus_by_action: dict[str, str]


# ---------------------------------------------------------------------------
# 玩家采样
# ---------------------------------------------------------------------------


def load_players_with_large_pfr_spread(
    *,
    csv_path: Path,
    min_hands: int,
    sample_count: int,
) -> list[PlayerPfrRow]:
    """按 PFR 差异挑选玩家样本。

    策略为: 先过滤 ``SIX_MAX`` 且 ``total_hands > min_hands`` 的玩家,
    再按 PFR 升序等距取点, 以确保样本之间的 PFR 差异尽可能大。

    Args:
        csv_path: 玩家核心统计 CSV 路径。
        min_hands: 最小总手数 (严格大于)。
        sample_count: 期望样本数。

    Returns:
        选中的玩家样本列表。

    Raises:
        ValueError: 当输入参数不合法或可用样本不足时抛出。
    """

    if sample_count <= 0:
        raise ValueError("sample_count 必须大于 0。")
    if min_hands < 0:
        raise ValueError("min_hands 不能为负数。")

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    candidates: list[PlayerPfrRow] = []
    for row in rows:
        table_type = (row.get("table_type") or "").strip().upper()
        if table_type != "SIX_MAX":
            continue
        player_name = (row.get("player_name") or "").strip()
        if not player_name or player_name.lower().startswith("aggregated_"):
            continue

        total_hands_raw = (row.get("total_hands") or "0").strip()
        try:
            total_hands = int(float(total_hands_raw or "0"))
        except ValueError:
            continue
        if total_hands <= min_hands:
            continue

        pfr_pct = parse_percent_value(row.get("pfr_pct", ""))
        if pfr_pct is None:
            continue

        candidates.append(
            PlayerPfrRow(
                player_name=player_name,
                total_hands=total_hands,
                pfr_pct=pfr_pct,
            )
        )

    if len(candidates) < sample_count:
        raise ValueError(
            "满足条件的玩家数量不足: "
            f"required={sample_count}, available={len(candidates)}"
        )

    candidates.sort(
        key=lambda item: (item.pfr_pct, -item.total_hands, item.player_name)
    )
    spread_indexes = build_even_spread_indexes(
        total_count=len(candidates),
        sample_count=sample_count,
    )
    return [candidates[index] for index in spread_indexes]


def build_even_spread_indexes(*, total_count: int, sample_count: int) -> list[int]:
    """在有序序列中构造等距采样索引。

    Args:
        total_count: 序列总长度。
        sample_count: 采样数量。

    Returns:
        升序去重后的索引列表。

    Raises:
        ValueError: 当输入不合法时抛出。
    """

    if sample_count <= 0:
        raise ValueError("sample_count 必须大于 0。")
    if total_count < sample_count:
        raise ValueError("total_count 必须大于等于 sample_count。")

    if sample_count == 1:
        return [total_count // 2]

    raw_indexes = [
        round(index * (total_count - 1) / (sample_count - 1))
        for index in range(sample_count)
    ]

    deduplicated: list[int] = []
    for index in raw_indexes:
        if index not in deduplicated:
            deduplicated.append(index)

    if len(deduplicated) == sample_count:
        return deduplicated

    for index in range(total_count):
        if index in deduplicated:
            continue
        deduplicated.append(index)
        if len(deduplicated) == sample_count:
            break

    deduplicated.sort()
    return deduplicated


# ---------------------------------------------------------------------------
# 场景构造: 通用 RFI (Raise First In)
# ---------------------------------------------------------------------------

# 6-max 固定座位映射 (position -> seat_index)。
# BTN=0 作为锚点, 按 SEAT_ORDER_6MAX 顺序排列。
_POSITION_TO_SEAT_6MAX: dict[Position, int] = {
    Position.BTN: 0,
    Position.SB: 1,
    Position.BB: 2,
    Position.UTG: 3,
    Position.MP: 4,
    Position.CO: 5,
}


def build_rfi_state(
    *,
    hero_position: Position,
    opener_position: Position,
    opener_player_name: str,
    state_version: int = 1,
    hero_cards: tuple[str, str] = ("As", "Kh"),
    open_size_bb: float = 2.5,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
) -> ObservedTableState:
    """构造 6-max RFI 场景的 preflop 观察状态。

    场景描述: opener 在指定位置 open raise, 中间玩家全部 fold, 轮到 hero 行动。

    Args:
        hero_position: Hero 所在位置。
        opener_position: RFI opener 所在位置。
        opener_player_name: Opener 玩家名。
        state_version: 状态版本号。
        hero_cards: Hero 手牌, 默认 AKo。
        open_size_bb: Open raise 大小 (以 BB 为单位), 默认 2.5。
        small_blind: 小盲注额, 默认 0.5。
        big_blind: 大盲注额, 默认 1.0。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。

    Raises:
        ValueError: opener 必须在 hero 之前行动 (按 preflop 行动顺序)。
    """

    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)
    if opener_order >= hero_order:
        raise ValueError(
            f"RFI 场景要求 opener 在 hero 之前行动: "
            f"opener={opener_position.value}(order={opener_order}) "
            f"hero={hero_position.value}(order={hero_order})"
        )

    hero_seat = _POSITION_TO_SEAT_6MAX[hero_position]
    opener_seat = _POSITION_TO_SEAT_6MAX[opener_position]
    open_amount = open_size_bb * big_blind

    # 构造 6 名玩家
    players: list[Player] = []
    action_history: list[PlayerAction] = []

    # 计算底池: SB + BB + open_amount
    pot = small_blind + big_blind + open_amount

    for position in PREFLOP_ACTION_ORDER_6MAX:
        seat = _POSITION_TO_SEAT_6MAX[position]

        if position == hero_position:
            # Hero: 即将行动, 不在 action_history 中
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"hero_{position.value.lower()}",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
        elif position == opener_position:
            # Opener: 已 open raise
            players.append(
                Player(
                    seat_index=seat,
                    player_id=opener_player_name,
                    stack=100.0 - open_amount,
                    bet=open_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=open_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == Position.SB:
            # SB: 已投盲注。无论是否 fold, 盲注已投入底池。
            is_folded = _is_between_opener_and_hero(
                position, opener_position, hero_position
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="sb_player",
                    stack=100.0 - small_blind,
                    bet=small_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        elif position == Position.BB:
            # BB: 已投盲注。无论是否 fold, 盲注已投入底池。
            is_folded = _is_between_opener_and_hero(
                position, opener_position, hero_position
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="bb_player",
                    stack=100.0 - big_blind,
                    bet=big_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        else:
            # 其他非 hero/opener 玩家
            is_folded = _is_between_opener_and_hero(
                position, opener_position, hero_position
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"{position.value.lower()}_player",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )

    table_id = (
        f"rfi_{hero_position.value.lower()}_vs_{opener_position.value.lower()}_open"
    )

    return ObservedTableState(
        table_id=table_id,
        player_count=6,
        small_blind=small_blind,
        big_blind=big_blind,
        hand_id=f"rfi_hand_{state_version}",
        street=Street.PREFLOP,
        pot=pot,
        btn_seat=_POSITION_TO_SEAT_6MAX[Position.BTN],
        actor_seat=hero_seat,
        hero_seat=hero_seat,
        hero_cards=hero_cards,
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


def _is_between_opener_and_hero(
    position: Position,
    opener_position: Position,
    hero_position: Position,
) -> bool:
    """判断某位置是否在 opener 和 hero 之间 (即需要 fold 的玩家)。

    按翻前行动顺序, opener 之后、hero 之前的玩家需要 fold。
    opener 之前的玩家不在 action_history 中 (因为 opener 是 RFI)。

    Args:
        position: 待判断的位置。
        opener_position: Opener 位置。
        hero_position: Hero 位置。

    Returns:
        True 表示该位置需要 fold。
    """

    order = PREFLOP_ACTION_ORDER_6MAX.index(position)
    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)
    return opener_order < order < hero_order


# ---------------------------------------------------------------------------
# 场景构造: 3-Bet
# ---------------------------------------------------------------------------


def build_3bet_state(
    *,
    hero_position: Position,
    opener_position: Position,
    three_bettor_position: Position,
    opener_player_name: str,
    three_bettor_player_name: str,
    state_version: int = 1,
    hero_cards: tuple[str, str] = ("As", "Kh"),
    open_size_bb: float = 2.5,
    three_bet_size_bb: float = 8.0,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
) -> ObservedTableState:
    """构造 6-max 3-Bet 场景的 preflop 观察状态。

    场景描述: opener open raise, 中间玩家 fold, 3bettor 3-bet,
    中间玩家 fold, 轮到 hero 行动。

    行动顺序约束: opener < 3bettor < hero (按翻前行动顺序)。

    Args:
        hero_position: Hero 所在位置。
        opener_position: 首先 open raise 的玩家位置。
        three_bettor_position: 3-bet 的玩家位置。
        opener_player_name: Opener 玩家名。
        three_bettor_player_name: 3-bettor 玩家名。
        state_version: 状态版本号。
        hero_cards: Hero 手牌, 默认 AKo。
        open_size_bb: Open raise 大小 (以 BB 为单位), 默认 2.5。
        three_bet_size_bb: 3-bet 大小 (以 BB 为单位), 默认 8.0。
        small_blind: 小盲注额, 默认 0.5。
        big_blind: 大盲注额, 默认 1.0。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。

    Raises:
        ValueError: 位置行动顺序不合法时抛出。
    """

    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    three_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(three_bettor_position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)

    if not (opener_order < three_bettor_order < hero_order):
        raise ValueError(
            f"3-Bet 场景要求 opener < 3bettor < hero (按行动顺序): "
            f"opener={opener_position.value}(order={opener_order}) "
            f"3bettor={three_bettor_position.value}(order={three_bettor_order}) "
            f"hero={hero_position.value}(order={hero_order})"
        )

    hero_seat = _POSITION_TO_SEAT_6MAX[hero_position]
    opener_seat = _POSITION_TO_SEAT_6MAX[opener_position]
    three_bettor_seat = _POSITION_TO_SEAT_6MAX[three_bettor_position]
    open_amount = open_size_bb * big_blind
    three_bet_amount = three_bet_size_bb * big_blind

    players: list[Player] = []
    action_history: list[PlayerAction] = []

    # 底池: SB + BB + open_amount + three_bet_amount
    pot = small_blind + big_blind + open_amount + three_bet_amount

    for position in PREFLOP_ACTION_ORDER_6MAX:
        seat = _POSITION_TO_SEAT_6MAX[position]

        if position == hero_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"hero_{position.value.lower()}",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
        elif position == opener_position:
            # Opener: 已 open raise
            players.append(
                Player(
                    seat_index=seat,
                    player_id=opener_player_name,
                    stack=100.0 - open_amount,
                    bet=open_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=open_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == three_bettor_position:
            # 3-bettor: 已 3-bet
            players.append(
                Player(
                    seat_index=seat,
                    player_id=three_bettor_player_name,
                    stack=100.0 - three_bet_amount,
                    bet=three_bet_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=three_bet_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == Position.SB:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="sb_player",
                    stack=100.0 - small_blind,
                    bet=small_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        elif position == Position.BB:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="bb_player",
                    stack=100.0 - big_blind,
                    bet=big_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        else:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"{position.value.lower()}_player",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )

    table_id = (
        f"3bet_{hero_position.value.lower()}"
        f"_vs_{three_bettor_position.value.lower()}"
        f"_vs_{opener_position.value.lower()}_open"
    )

    return ObservedTableState(
        table_id=table_id,
        player_count=6,
        small_blind=small_blind,
        big_blind=big_blind,
        hand_id=f"3bet_hand_{state_version}",
        street=Street.PREFLOP,
        pot=pot,
        btn_seat=_POSITION_TO_SEAT_6MAX[Position.BTN],
        actor_seat=hero_seat,
        hero_seat=hero_seat,
        hero_cards=hero_cards,
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


# ---------------------------------------------------------------------------
# 场景构造: Facing 3-Bet (Hero 是 opener)
# ---------------------------------------------------------------------------


def build_facing_3bet_state(
    *,
    hero_opener_position: Position,
    three_bettor_position: Position,
    three_bettor_player_name: str,
    state_version: int = 1,
    hero_cards: tuple[str, str] = ("As", "Kh"),
    open_size_bb: float = 2.5,
    three_bet_size_bb: float = 8.0,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
) -> ObservedTableState:
    """构造 Hero 作为 opener 遭遇 3-Bet 的 6-max preflop 观察状态。

    场景描述: Hero 在 hero_opener_position open raise, 中间玩家 fold,
    3bettor 在 three_bettor_position 3-bet, 3bettor 之后的剩余玩家 fold,
    行动权回到 Hero, 轮到 Hero 做 call/fold/4bet 决策。

    行动顺序约束: hero_opener < 3bettor (按翻前行动顺序)。

    与 build_3bet_state 的区别:
    - Hero 就是 opener, 已有 RAISE 记录和投注额。
    - Hero 的 stack = 100 - open_amount, bet = open_amount。
    - raise_time = 2 (open + 3bet)。

    Args:
        hero_opener_position: Hero 所在位置 (同时也是 opener)。
        three_bettor_position: 3-bet 的对手位置。
        three_bettor_player_name: 3-bettor 玩家名。
        state_version: 状态版本号。
        hero_cards: Hero 手牌, 默认 AKo。
        open_size_bb: Hero open raise 大小 (以 BB 为单位), 默认 2.5。
        three_bet_size_bb: 3-bet 大小 (以 BB 为单位), 默认 8.0。
        small_blind: 小盲注额, 默认 0.5。
        big_blind: 大盲注额, 默认 1.0。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。

    Raises:
        ValueError: hero_opener 不在 3bettor 之前行动时抛出。
    """

    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_opener_position)
    three_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(three_bettor_position)

    if not (hero_order < three_bettor_order):
        raise ValueError(
            f"Facing 3-Bet 场景要求 hero(opener) < 3bettor (按行动顺序): "
            f"hero={hero_opener_position.value}(order={hero_order}) "
            f"3bettor={three_bettor_position.value}(order={three_bettor_order})"
        )

    hero_seat = _POSITION_TO_SEAT_6MAX[hero_opener_position]
    three_bettor_seat = _POSITION_TO_SEAT_6MAX[three_bettor_position]
    open_amount = open_size_bb * big_blind
    three_bet_amount = three_bet_size_bb * big_blind

    players: list[Player] = []
    action_history: list[PlayerAction] = []

    pot = small_blind + big_blind + open_amount + three_bet_amount

    for position in PREFLOP_ACTION_ORDER_6MAX:
        seat = _POSITION_TO_SEAT_6MAX[position]

        if position == hero_opener_position:
            # Hero (opener): 已 open raise, 现在等待第二次行动
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"hero_{position.value.lower()}",
                    stack=100.0 - open_amount,
                    bet=open_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=open_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == three_bettor_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=three_bettor_player_name,
                    stack=100.0 - three_bet_amount,
                    bet=three_bet_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=three_bet_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == Position.SB:
            is_folded = _should_fold_in_facing_3bet(
                position,
                hero_opener_position,
                three_bettor_position,
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="sb_player",
                    stack=100.0 - small_blind,
                    bet=small_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        elif position == Position.BB:
            is_folded = _should_fold_in_facing_3bet(
                position,
                hero_opener_position,
                three_bettor_position,
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="bb_player",
                    stack=100.0 - big_blind,
                    bet=big_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        else:
            is_folded = _should_fold_in_facing_3bet(
                position,
                hero_opener_position,
                three_bettor_position,
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"{position.value.lower()}_player",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )

    table_id = (
        f"facing_3bet_{hero_opener_position.value.lower()}"
        f"_open_vs_{three_bettor_position.value.lower()}_3bet"
    )

    return ObservedTableState(
        table_id=table_id,
        player_count=6,
        small_blind=small_blind,
        big_blind=big_blind,
        hand_id=f"facing_3bet_hand_{state_version}",
        street=Street.PREFLOP,
        pot=pot,
        btn_seat=_POSITION_TO_SEAT_6MAX[Position.BTN],
        actor_seat=hero_seat,
        hero_seat=hero_seat,
        hero_cards=hero_cards,
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


# ---------------------------------------------------------------------------
# 场景构造: 4-Bet
# ---------------------------------------------------------------------------


def build_4bet_state(
    *,
    hero_position: Position,
    opener_position: Position,
    three_bettor_position: Position,
    four_bettor_position: Position,
    opener_player_name: str,
    three_bettor_player_name: str,
    four_bettor_player_name: str,
    state_version: int = 1,
    hero_cards: tuple[str, str] = ("As", "Kh"),
    open_size_bb: float = 2.5,
    three_bet_size_bb: float = 8.0,
    four_bet_size_bb: float = 20.0,
    small_blind: float = 0.5,
    big_blind: float = 1.0,
) -> ObservedTableState:
    """构造 6-max 4-Bet 场景的 preflop 观察状态。

    场景描述: opener open raise, 中间玩家 fold, 3bettor 3-bet,
    中间玩家 fold, 4bettor 4-bet, 中间玩家 fold, 轮到 hero 行动。

    行动顺序约束: opener < 3bettor < 4bettor < hero (按翻前行动顺序)。

    Args:
        hero_position: Hero 所在位置。
        opener_position: 首先 open raise 的玩家位置。
        three_bettor_position: 3-bet 的玩家位置。
        four_bettor_position: 4-bet 的玩家位置。
        opener_player_name: Opener 玩家名。
        three_bettor_player_name: 3-bettor 玩家名。
        four_bettor_player_name: 4-bettor 玩家名。
        state_version: 状态版本号。
        hero_cards: Hero 手牌, 默认 AKo。
        open_size_bb: Open raise 大小 (以 BB 为单位), 默认 2.5。
        three_bet_size_bb: 3-bet 大小 (以 BB 为单位), 默认 8.0。
        four_bet_size_bb: 4-bet 大小 (以 BB 为单位), 默认 20.0。
        small_blind: 小盲注额, 默认 0.5。
        big_blind: 大盲注额, 默认 1.0。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。

    Raises:
        ValueError: 位置行动顺序不合法时抛出。
    """

    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    three_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(three_bettor_position)
    four_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(four_bettor_position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)

    if not (opener_order < three_bettor_order < four_bettor_order < hero_order):
        raise ValueError(
            f"4-Bet 场景要求 opener < 3bettor < 4bettor < hero (按行动顺序): "
            f"opener={opener_position.value}(order={opener_order}) "
            f"3bettor={three_bettor_position.value}(order={three_bettor_order}) "
            f"4bettor={four_bettor_position.value}(order={four_bettor_order}) "
            f"hero={hero_position.value}(order={hero_order})"
        )

    hero_seat = _POSITION_TO_SEAT_6MAX[hero_position]
    open_amount = open_size_bb * big_blind
    three_bet_amount = three_bet_size_bb * big_blind
    four_bet_amount = four_bet_size_bb * big_blind

    players: list[Player] = []
    action_history: list[PlayerAction] = []

    # 底池: SB + BB + open + 3bet + 4bet
    pot = small_blind + big_blind + open_amount + three_bet_amount + four_bet_amount

    for position in PREFLOP_ACTION_ORDER_6MAX:
        seat = _POSITION_TO_SEAT_6MAX[position]

        if position == hero_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"hero_{position.value.lower()}",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
        elif position == opener_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=opener_player_name,
                    stack=100.0 - open_amount,
                    bet=open_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=open_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == three_bettor_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=three_bettor_player_name,
                    stack=100.0 - three_bet_amount,
                    bet=three_bet_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=three_bet_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == four_bettor_position:
            players.append(
                Player(
                    seat_index=seat,
                    player_id=four_bettor_player_name,
                    stack=100.0 - four_bet_amount,
                    bet=four_bet_amount,
                    position=position,
                    is_button=(position == Position.BTN),
                )
            )
            action_history.append(
                PlayerAction(
                    player_index=seat,
                    action_type=ActionType.RAISE,
                    amount=four_bet_amount,
                    street=Street.PREFLOP,
                )
            )
        elif position == Position.SB:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position, four_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="sb_player",
                    stack=100.0 - small_blind,
                    bet=small_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        elif position == Position.BB:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position, four_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id="bb_player",
                    stack=100.0 - big_blind,
                    bet=big_blind,
                    position=position,
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )
        else:
            is_folded = _should_fold_in_multibet(
                position,
                opener_position,
                hero_position,
                extra_raisers=[three_bettor_position, four_bettor_position],
            )
            players.append(
                Player(
                    seat_index=seat,
                    player_id=f"{position.value.lower()}_player",
                    stack=100.0,
                    bet=0.0,
                    position=position,
                    is_button=(position == Position.BTN),
                    is_folded=is_folded,
                )
            )
            if is_folded:
                action_history.append(
                    PlayerAction(
                        player_index=seat,
                        action_type=ActionType.FOLD,
                        amount=0.0,
                        street=Street.PREFLOP,
                    )
                )

    table_id = (
        f"4bet_{hero_position.value.lower()}"
        f"_vs_{four_bettor_position.value.lower()}"
        f"_vs_{three_bettor_position.value.lower()}"
        f"_vs_{opener_position.value.lower()}_open"
    )

    return ObservedTableState(
        table_id=table_id,
        player_count=6,
        small_blind=small_blind,
        big_blind=big_blind,
        hand_id=f"4bet_hand_{state_version}",
        street=Street.PREFLOP,
        pot=pot,
        btn_seat=_POSITION_TO_SEAT_6MAX[Position.BTN],
        actor_seat=hero_seat,
        hero_seat=hero_seat,
        hero_cards=hero_cards,
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


def _should_fold_in_multibet(
    position: Position,
    opener_position: Position,
    hero_position: Position,
    *,
    extra_raisers: list[Position],
) -> bool:
    """判断某位置在多次加注场景中是否已 fold。

    在 3bet/4bet 场景中, 非 raiser 且非 hero 的玩家, 如果位于
    opener 之后且 hero 之前, 则视为已 fold。Raiser 自身不 fold。

    Args:
        position: 待判断的位置。
        opener_position: Opener 位置。
        hero_position: Hero 位置。
        extra_raisers: 额外的加注者位置列表 (3bettor, 4bettor 等)。

    Returns:
        True 表示该位置需要 fold。
    """

    if position in (opener_position, hero_position):
        return False
    if position in extra_raisers:
        return False

    order = PREFLOP_ACTION_ORDER_6MAX.index(position)
    opener_order = PREFLOP_ACTION_ORDER_6MAX.index(opener_position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_position)
    return opener_order < order < hero_order


def _should_fold_in_facing_3bet(
    position: Position,
    hero_opener_position: Position,
    three_bettor_position: Position,
) -> bool:
    """判断在 Hero 作为 opener 遭遇 3bet 场景中, 某位置是否已 fold。

    行动流程: Hero(opener) open -> 中间玩家 fold -> 3bettor 3bet
    -> 3bettor 之后的剩余玩家 fold -> 回到 Hero 决策。

    需要 fold 的玩家:
    1. hero_opener 和 3bettor 之间的玩家 (opener 之后, 3bettor 之前)
    2. 3bettor 之后、行动序列末尾的玩家 (还没到 hero 的回合就 fold 了)

    不需要 fold 的: hero_opener 自身, 3bettor 自身。

    Args:
        position: 待判断的位置。
        hero_opener_position: Hero (同时也是 opener) 位置。
        three_bettor_position: 3bettor 位置。

    Returns:
        True 表示该位置需要 fold。
    """

    if position in (hero_opener_position, three_bettor_position):
        return False

    order = PREFLOP_ACTION_ORDER_6MAX.index(position)
    hero_order = PREFLOP_ACTION_ORDER_6MAX.index(hero_opener_position)
    three_bettor_order = PREFLOP_ACTION_ORDER_6MAX.index(three_bettor_position)

    # hero_opener < 3bettor (按行动顺序)
    # fold 区间 1: hero_opener 之后到 3bettor 之前
    # fold 区间 2: 3bettor 之后到行动序列末尾
    return hero_order < order < three_bettor_order or order > three_bettor_order


# ---------------------------------------------------------------------------
# GTO+ 导出
# ---------------------------------------------------------------------------


def load_gtoplus_ranges_for_decision(
    *,
    engine: StrategyEngine,
    decision: RecommendationDecision,
    min_strategy: float,
) -> dict[str, str]:
    """根据推荐结果读取节点动作范围并导出 GTO+ 文本。

    优先使用 ``decision.adjusted_belief_ranges`` 中经对手激进度调整后的
    belief_range; 仅当该字段为空或某动作缺少调整范围时, 回退到数据库原始范围.

    Args:
        engine: StrategyEngine 实例。
        decision: Hero 推荐决策。
        min_strategy: GTO+ 导出阈值。

    Returns:
        ``action_code -> gtoplus_text`` 映射。

    Raises:
        AssertionError: 当决策缺失节点或节点动作为空时抛出。
    """

    if decision.selected_node_id is None:
        raise AssertionError("RecommendationDecision 缺少 selected_node_id。")

    adjusted = decision.adjusted_belief_ranges

    if adjusted:
        gtoplus_by_action: dict[str, str] = {}
        for action_code, preflop_range in adjusted.items():
            gtoplus_by_action[action_code] = preflop_range.to_gtoplus(
                min_strategy=min_strategy,
            )
        return gtoplus_by_action

    actions_by_node = engine._hero_resolver._repository_adapter.load_actions(
        (decision.selected_node_id,)
    )
    action_options = actions_by_node.get(decision.selected_node_id, ())
    if not action_options:
        raise AssertionError(
            f"节点动作为空, 无法导出 GTO+。node_id={decision.selected_node_id}"
        )

    gtoplus_by_action = {}
    for action_option in action_options:
        gtoplus_by_action[action_option.action_code] = (
            action_option.preflop_range.to_gtoplus(min_strategy=min_strategy)
        )
    return gtoplus_by_action


def write_gtoplus_exports(
    *,
    output_dir: Path,
    snapshot: HeroStrategySnapshot,
) -> None:
    """把单个玩家策略快照写出为 GTO+ 文本文件。

    Args:
        output_dir: 导出目录。
        snapshot: 策略快照。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    player_name_token = sanitize_filename(snapshot.player_name)
    for action_code, gtoplus_text in snapshot.gtoplus_by_action.items():
        action_token = sanitize_filename(action_code)
        file_path = output_dir / f"{player_name_token}_{action_token}.txt"
        file_path.write_text(gtoplus_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 打印 / 调试
# ---------------------------------------------------------------------------


def print_snapshot(snapshot: HeroStrategySnapshot) -> None:
    """打印单个玩家的策略快照摘要, 含 prior vs posterior 对比和 GTO+ 文本。

    Args:
        snapshot: 待打印的策略快照。
    """

    print("=" * 88)
    print(
        "玩家: "
        f"{snapshot.player_name}, hands={snapshot.total_hands}, "
        f"pfr_pct={snapshot.pfr_pct:.2f}"
    )
    print(
        "命中节点: "
        f"node_id={snapshot.selected_node_id}, source_id={snapshot.selected_source_id}, "
        f"sampling_random={snapshot.sampling_random:.6f}, sampled_action={snapshot.sampled_action_code}"
    )

    # -- prior vs posterior 动作分布对比 --
    all_actions = sorted(
        set(snapshot.prior_action_distribution) | set(snapshot.action_distribution)
    )
    print("动作分布 (prior -> posterior):")
    for action_code in all_actions:
        prior_freq = snapshot.prior_action_distribution.get(action_code, 0.0)
        posterior_freq = snapshot.action_distribution.get(action_code, 0.0)
        delta = posterior_freq - prior_freq
        delta_sign = "+" if delta >= 0 else ""
        print(
            f"  {action_code:<12s}  "
            f"prior={prior_freq:7.2%}  ->  posterior={posterior_freq:7.2%}  "
            f"({delta_sign}{delta:7.2%})"
        )

    # -- 对手范围调整明细 --
    if snapshot.opponent_aggression_details:
        aggregated_ratio = 1.0
        for d in snapshot.opponent_aggression_details:
            dr: float = float(d.get("dampened_ratio", d["ratio"]))  # type: ignore[arg-type]
            aggregated_ratio *= dr
        print("对手范围调整明细:")
        for d in snapshot.opponent_aggression_details:
            seat = d.get("seat", "?")
            player_id = d.get("player_id", "?")
            prior_f: float = float(d["prior_freq"])  # type: ignore[arg-type]
            posterior_f: float = float(d["posterior_freq"])  # type: ignore[arg-type]
            ratio: float = float(d["ratio"])  # type: ignore[arg-type]
            dampened: float = float(d.get("dampened_ratio", ratio))  # type: ignore[arg-type]
            print(
                f"  seat={seat} ({player_id})  "
                f"prior={prior_f:.4f}  posterior={posterior_f:.4f}  "
                f"raw_ratio={ratio:.4f}  dampened={dampened:.4f}"
            )
        print(f"  聚合 aggression_ratio={aggregated_ratio:.4f}")

    for action_code, gtoplus_text in sorted(snapshot.gtoplus_by_action.items()):
        print(f"[GTO+] action={action_code}")
        print(gtoplus_text)


def print_pairwise_range_comparison(snapshots: list[HeroStrategySnapshot]) -> None:
    """打印不同玩家之间的动作范围差异对比。

    Args:
        snapshots: 已生成的策略快照列表。
    """

    if len(snapshots) < 2:
        return

    baseline = snapshots[0]
    for current in snapshots[1:]:
        action_codes = sorted(
            set(baseline.gtoplus_by_action) | set(current.gtoplus_by_action)
        )
        changed_actions = [
            action_code
            for action_code in action_codes
            if baseline.gtoplus_by_action.get(action_code)
            != current.gtoplus_by_action.get(action_code)
        ]
        print("-" * 88)
        print(
            f"范围对比: base={baseline.player_name} vs target={current.player_name}, "
            f"changed_actions={changed_actions if changed_actions else '[]'}"
        )


# ---------------------------------------------------------------------------
# 快照构造
# ---------------------------------------------------------------------------


def build_snapshot_from_decision(
    *,
    player_row: PlayerPfrRow,
    decision: RecommendationDecision,
    engine: StrategyEngine,
    min_strategy: float = 0.001,
) -> HeroStrategySnapshot:
    """从 RecommendationDecision 构造 HeroStrategySnapshot。

    Args:
        player_row: 对手玩家统计行。
        decision: Hero 推荐决策。
        engine: StrategyEngine 实例。
        min_strategy: GTO+ 导出阈值。

    Returns:
        完整的 Hero 策略快照。
    """

    gtoplus_by_action = load_gtoplus_ranges_for_decision(
        engine=engine,
        decision=decision,
        min_strategy=min_strategy,
    )

    return HeroStrategySnapshot(
        player_name=player_row.player_name,
        total_hands=player_row.total_hands,
        pfr_pct=player_row.pfr_pct,
        selected_node_id=decision.selected_node_id,  # type: ignore[arg-type]
        selected_source_id=decision.selected_source_id,  # type: ignore[arg-type]
        action_distribution=dict(decision.action_distribution),
        prior_action_distribution=dict(decision.prior_action_distribution),
        opponent_aggression_details=list(decision.opponent_aggression_details),
        sampling_random=decision.sampling_random,  # type: ignore[arg-type]
        sampled_action_code=decision.action_code,
        gtoplus_by_action=gtoplus_by_action,
    )


# ---------------------------------------------------------------------------
# 通用断言
# ---------------------------------------------------------------------------


def assert_valid_recommendation(
    decision: object,
    *,
    label: str = "",
) -> RecommendationDecision:
    """校验 StrategyEngine 返回结果是合法的 RecommendationDecision。

    Args:
        decision: engine 返回值。
        label: 断言失败时的附加描述。

    Returns:
        类型收窄后的 RecommendationDecision。

    Raises:
        AssertionError: 不满足条件时抛出。
    """
    import pytest

    prefix = f"[{label}] " if label else ""
    assert isinstance(
        decision,
        RecommendationDecision,
    ), f"{prefix}期望 RecommendationDecision, 实际={type(decision).__name__}"

    # isinstance 后显式绑定, 帮助静态分析器完成类型窄化。
    rec: RecommendationDecision = decision

    assert rec.selected_node_id is not None, f"{prefix}selected_node_id 为 None"
    assert rec.selected_source_id is not None, f"{prefix}selected_source_id 为 None"
    assert rec.sampling_random is not None, f"{prefix}sampling_random 为 None"
    assert 0.0 <= rec.sampling_random < 1.0, (
        f"{prefix}sampling_random 范围异常: {rec.sampling_random}"
    )
    assert rec.action_distribution, f"{prefix}action_distribution 为空"
    assert pytest.approx(1.0, abs=1e-6) == sum(rec.action_distribution.values()), (
        f"{prefix}action_distribution 概率之和不为 1"
    )
    return rec


# ---------------------------------------------------------------------------
# 合法 RFI 组合枚举
# ---------------------------------------------------------------------------

# 所有合法的 (opener_position, hero_position) RFI 组合 (6-max)。
# opener 必须在 hero 之前行动。
ALL_RFI_COMBINATIONS_6MAX: list[tuple[Position, Position]] = [
    (opener, hero)
    for i, opener in enumerate(PREFLOP_ACTION_ORDER_6MAX)
    for hero in PREFLOP_ACTION_ORDER_6MAX[i + 1 :]
]
"""全部 15 种合法 RFI 位置组合 (opener, hero), 6-max。"""

# 所有合法的 (opener, 3bettor, hero) 3-Bet 组合 (6-max)。
# 行动顺序: opener < 3bettor < hero。
ALL_3BET_COMBINATIONS_6MAX: list[tuple[Position, Position, Position]] = [
    (opener, three_bettor, hero)
    for i, opener in enumerate(PREFLOP_ACTION_ORDER_6MAX)
    for j, three_bettor in enumerate(PREFLOP_ACTION_ORDER_6MAX[i + 1 :], start=i + 1)
    for hero in PREFLOP_ACTION_ORDER_6MAX[j + 1 :]
]
"""全部 20 种合法 3-Bet 位置组合 (opener, 3bettor, hero), 6-max。"""

# 所有合法的 (opener, 3bettor, 4bettor, hero) 4-Bet 组合 (6-max)。
# 行动顺序: opener < 3bettor < 4bettor < hero。
ALL_4BET_COMBINATIONS_6MAX: list[tuple[Position, Position, Position, Position]] = [
    (opener, three_bettor, four_bettor, hero)
    for i, opener in enumerate(PREFLOP_ACTION_ORDER_6MAX)
    for j, three_bettor in enumerate(PREFLOP_ACTION_ORDER_6MAX[i + 1 :], start=i + 1)
    for k, four_bettor in enumerate(PREFLOP_ACTION_ORDER_6MAX[j + 1 :], start=j + 1)
    for hero in PREFLOP_ACTION_ORDER_6MAX[k + 1 :]
]
"""全部 15 种合法 4-Bet 位置组合 (opener, 3bettor, 4bettor, hero), 6-max。"""

# 所有合法的 (hero_opener, 3bettor) Facing 3-Bet 组合 (6-max)。
# hero_opener < 3bettor (按行动顺序), hero 就是 opener。
ALL_FACING_3BET_COMBINATIONS_6MAX: list[tuple[Position, Position]] = [
    (hero_opener, three_bettor)
    for i, hero_opener in enumerate(PREFLOP_ACTION_ORDER_6MAX[:-1])
    for three_bettor in PREFLOP_ACTION_ORDER_6MAX[i + 1 :]
]
"""全部 15 种合法 Facing 3-Bet 位置组合 (hero_opener, 3bettor), 6-max。"""


# ---------------------------------------------------------------------------
# 合成 PlayerStats 构造
# ---------------------------------------------------------------------------


def make_synthetic_player_stats(
    *,
    player_name: str,
    total_hands: int,
    vpip_pct: float,
    pfr_pct: float,
    agg_pct: float = 0.35,
    wtp_pct: float = 0.55,
    table_type: TableType = TableType.SIX_MAX,
) -> PlayerStats:
    """根据指定的 VPIP/PFR/AGG/WTP 百分比构造可控的 PlayerStats 对象.

    本函数用于测试场景, 在不依赖真实数据库的情况下快速生成具有
    已知统计特征的玩家统计. 样本量在各 bin 间近似均匀分布.

    Args:
        player_name: 玩家名称.
        total_hands: 总手数, 作为各维度分配样本的基础.
        vpip_pct: VPIP 百分比 (0.0 ~ 1.0).
        pfr_pct: PFR 百分比 (0.0 ~ 1.0), 应 <= vpip_pct.
        agg_pct: 翻后激进因子百分比 (0.0 ~ 1.0), 默认 0.35.
        wtp_pct: Went To Pot 百分比 (0.0 ~ 1.0), 默认 0.55.
        table_type: 桌型, 默认 SIX_MAX.

    Returns:
        填充好各分桶样本的 PlayerStats 实例.
    """
    stats = PlayerStats(player_name=player_name, table_type=table_type)
    stats.vpip = StatValue(
        positive=round(total_hands * vpip_pct), total=total_hands
    )

    # -- preflop: 仅填充 previous_action == FOLD 的 bin (PFR 统计来源) --
    all_preflop_params = PreFlopParams.get_all_params(table_type)
    fold_indices: list[int] = [
        p.to_index()
        for p in all_preflop_params
        if p.previous_action == MetricsActionType.FOLD
    ]
    num_fold_bins = len(fold_indices)

    if num_fold_bins > 0:
        base_total, remainder = divmod(total_hands, num_fold_bins)
        for rank, idx in enumerate(fold_indices):
            bin_total = base_total + (1 if rank < remainder else 0)
            bin_raise = round(bin_total * pfr_pct)
            bin_call = max(0, round(bin_total * (vpip_pct - pfr_pct)))
            bin_fold = max(0, bin_total - bin_raise - bin_call)
            stats.preflop_stats[idx].raise_samples = bin_raise
            stats.preflop_stats[idx].check_call_samples = bin_call
            stats.preflop_stats[idx].fold_samples = bin_fold

    # -- postflop: 按 num_bets 区分强制/非强制行动 bin --
    all_postflop_params = PostFlopParams.get_all_params(table_type)
    forced_indices: list[int] = []
    unforced_indices: list[int] = []
    for p in all_postflop_params:
        if p.num_bets > 0:
            forced_indices.append(p.to_index())
        else:
            unforced_indices.append(p.to_index())

    # 强制行动 bin: 面对加注, 使用 agg/wtp 分配
    if forced_indices:
        base_total_f, remainder_f = divmod(total_hands, len(forced_indices))
        for rank, idx in enumerate(forced_indices):
            bin_total = base_total_f + (1 if rank < remainder_f else 0)
            bin_raise = round(bin_total * agg_pct)
            bin_call = max(0, round(bin_total * (wtp_pct - agg_pct)))
            bin_fold = max(0, bin_total - bin_raise - bin_call)
            stats.postflop_stats[idx].raise_samples = bin_raise
            stats.postflop_stats[idx].check_call_samples = bin_call
            stats.postflop_stats[idx].fold_samples = bin_fold

    # 非强制行动 bin: 无人加注, 仅分配 raise/call
    if unforced_indices:
        base_total_u, remainder_u = divmod(total_hands, len(unforced_indices))
        for rank, idx in enumerate(unforced_indices):
            bin_total = base_total_u + (1 if rank < remainder_u else 0)
            bin_raise = round(bin_total * agg_pct)
            bin_call = bin_total - bin_raise
            stats.postflop_stats[idx].raise_samples = bin_raise
            stats.postflop_stats[idx].check_call_samples = bin_call
            stats.postflop_stats[idx].fold_samples = 0

    return stats


# ---------------------------------------------------------------------------
# EstimatedAD 对比格式化
# ---------------------------------------------------------------------------


def format_estimated_ad_comparison(
    *,
    labels: list[str],
    ads: list[EstimatedAD],
    node_label: str = "",
) -> str:
    """将多个 EstimatedAD 格式化为 Markdown 对比表格.

    用于在测试报告或日志中直观比较不同来源/玩家的行动概率分布估计.

    Args:
        labels: 每行对应的标签名列表, 长度须与 ads 一致.
        ads: EstimatedAD 实例列表.
        node_label: 可选的表格标题, 非空时作为 ``###`` 级标题输出.

    Returns:
        包含完整 Markdown 表格的字符串.
    """
    lines: list[str] = []
    if node_label:
        lines.append(f"### {node_label}\n")

    header = (
        "| Label | BR mean | BR σ | CC mean | CC σ "
        "| FO mean | FO σ | prior_k | update_n |"
    )
    separator = (
        "|-------|---------|------|---------|------"
        "|---------|------|---------|----------|"
    )
    lines.append(header)
    lines.append(separator)

    for label, ad in zip(labels, ads):
        row = (
            f"| {label} "
            f"| {ad.bet_raise.mean:.4f} | {ad.bet_raise.sigma:.4f} "
            f"| {ad.check_call.mean:.4f} | {ad.check_call.sigma:.4f} "
            f"| {ad.fold.mean:.4f} | {ad.fold.sigma:.4f} "
            f"| {ad.prior_samples} | {ad.update_samples} |"
        )
        lines.append(row)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hero 范围 G5 报告写入
# ---------------------------------------------------------------------------


def write_hero_range_g5_report(
    *,
    output_path: Path,
    title: str,
    config_text: str,
    sections: list[tuple[str, str]],
) -> None:
    """将详细的 Markdown 报告写入磁盘.

    用于持久化 Hero 范围验证或 G5 分析结果, 便于后续 review.

    Args:
        output_path: 输出文件路径.
        title: 报告标题, 将作为一级标题写入.
        config_text: 配置描述文本, 写入 ``## 配置`` 小节.
        sections: ``(小节标题, 小节内容)`` 列表, 依次写入二级标题.

    Returns:
        None. 文件写入到 output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {title}\n\n")
    lines.append(f"## 配置\n\n{config_text}\n\n")
    for section_title, section_content in sections:
        lines.append(f"## {section_title}\n\n{section_content}\n\n")

    output_path.write_text("".join(lines), encoding="utf-8")
