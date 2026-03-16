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
# GTO+ 导出
# ---------------------------------------------------------------------------


def load_gtoplus_ranges_for_decision(
    *,
    engine: StrategyEngine,
    decision: RecommendationDecision,
    min_strategy: float,
) -> dict[str, str]:
    """根据推荐结果读取节点动作范围并导出 GTO+ 文本。

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

    actions_by_node = engine._hero_resolver._repository_adapter.load_actions(
        (decision.selected_node_id,)
    )
    action_options = actions_by_node.get(decision.selected_node_id, ())
    if not action_options:
        raise AssertionError(
            f"节点动作为空, 无法导出 GTO+。node_id={decision.selected_node_id}"
        )

    gtoplus_by_action: dict[str, str] = {}
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
