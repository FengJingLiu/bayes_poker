"""UTG open 节点 EV 调整验证工具。"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import PlayerAction, Position
from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.range import PreflopRange
from bayes_poker.strategy.strategy_engine.core_types import (
    NodeContext,
    PlayerNodeContext,
)
from bayes_poker.strategy.strategy_engine.gto_policy import (
    GtoPriorAction,
    GtoPriorBuilder,
    GtoPriorPolicy,
)
from bayes_poker.strategy.strategy_engine.node_mapper import StrategyNodeMapper
from bayes_poker.strategy.strategy_engine.opponent_pipeline import (
    _adjust_belief_with_stats_and_ev,
    _resolve_action_prior_range,
    _select_matching_prior_action,
)
from bayes_poker.strategy.strategy_engine.repository_adapter import (
    StrategyRepositoryAdapter,
)
from bayes_poker.strategy.strategy_engine.stats_adapter import PlayerNodeStatsAdapter


@dataclass(frozen=True, slots=True)
class PlayerGapRow:
    """玩家 VPIP/PFR 差异行。"""

    player_name: str
    table_type: str
    total_hands: int
    vpip_pct: float
    pfr_pct: float
    vpip_pfr_gap_pct: float


@dataclass(frozen=True, slots=True)
class PlayerValidationResult:
    """单个玩家验证结果。"""

    player_name: str
    total_hands: int
    vpip_pct: float
    pfr_pct: float
    vpip_pfr_gap_pct: float
    source_kind: str
    stats_raise_probability: float
    prior_total_frequency: float
    posterior_total_frequency: float
    gto_action_name: str
    gto_action_type: str
    gto_action_bet_size_bb: float | None
    gto_source_id: int | None
    gto_node_id: int | None
    prior_gtoplus_path: str
    posterior_gtoplus_path: str


@dataclass(frozen=True, slots=True)
class ValidationOutput:
    """整体验证输出。"""

    summary_csv_path: Path
    prior_gtoplus_path: Path
    player_count: int


def run_utg_open_ev_validation(
    *,
    strategy_db_path: Path,
    player_stats_db_path: Path,
    player_core_csv_path: Path,
    output_dir: Path,
    source_ids: tuple[int, ...],
    top_n: int,
    min_hands: int,
    open_size_bb: float,
    big_blind: float,
    min_strategy: float,
) -> ValidationOutput:
    """执行 UTG open EV 调整验证。

    Args:
        strategy_db_path: 策略 SQLite 路径。
        player_stats_db_path: 玩家统计 SQLite 路径。
        player_core_csv_path: 玩家核心统计 CSV 路径。
        output_dir: 导出目录。
        source_ids: 策略源 ID 序列。
        top_n: 选取玩家数量。
        min_hands: 最小样本手数。
        open_size_bb: 验证使用的 open 尺度（BB）。
        big_blind: 大盲金额。
        min_strategy: 导出 GTO+ 的最小阈值。

    Returns:
        验证输出路径与数量信息。
    """

    if top_n <= 0:
        raise ValueError("top_n 必须大于 0。")
    if min_hands < 0:
        raise ValueError("min_hands 不能为负数。")
    if not source_ids:
        raise ValueError("source_ids 不能为空。")
    if big_blind <= 0:
        raise ValueError("big_blind 必须大于 0。")

    output_dir.mkdir(parents=True, exist_ok=True)
    gtoplus_dir = output_dir / "gtoplus"
    gtoplus_dir.mkdir(parents=True, exist_ok=True)

    selected_players = select_players_with_large_vpip_pfr_gap(
        csv_path=player_core_csv_path,
        table_type_name="SIX_MAX",
        top_n=top_n,
        min_hands=min_hands,
    )

    node_context = build_utg_open_player_node_context(table_type=TableType.SIX_MAX)
    observed_open_action = PlayerAction(
        player_index=node_context.actor_seat,
        action_type=ActionType.RAISE,
        amount=open_size_bb * big_blind,
        street=Street.PREFLOP,
    )

    adapter = StrategyRepositoryAdapter(strategy_db_path)
    stats_repo = PlayerStatsRepository(player_stats_db_path)
    adapter.connect()
    stats_repo.connect()
    try:
        mapped = StrategyNodeMapper(
            repository_adapter=adapter,
            source_id=source_ids,
            stack_bb=100,
        ).map_node_context(node_context.node_context)
        prior_policy = GtoPriorBuilder(repository_adapter=adapter).build_policy(mapped)
        matched_action = _select_matching_prior_action(
            prior_policy=prior_policy,
            action=observed_open_action,
            big_blind=big_blind,
        )
        prior_range = _resolve_action_prior_range(matched_action)

        prior_file_name = (
            f"utg_open_prior_{sanitize_filename(matched_action.action_name)}.txt"
        )
        prior_gtoplus_path = gtoplus_dir / prior_file_name
        prior_gtoplus_path.write_text(
            prior_range.to_gtoplus(min_strategy=min_strategy),
            encoding="utf-8",
        )

        stats_adapter = PlayerNodeStatsAdapter(stats_repo)
        results: list[PlayerValidationResult] = []
        for player_row in selected_players:
            node_stats = stats_adapter.load(
                player_name=player_row.player_name,
                table_type=TableType.SIX_MAX,
                node_context=node_context,
            )
            posterior_range = _adjust_belief_with_stats_and_ev(
                prior=prior_range,
                observed_action_type=ActionType.RAISE,
                node_stats=node_stats,
            )

            posterior_file_name = (
                "utg_open_posterior_"
                f"{sanitize_filename(player_row.player_name)}_"
                f"{sanitize_filename(matched_action.action_name)}.txt"
            )
            posterior_gtoplus_path = gtoplus_dir / posterior_file_name
            posterior_gtoplus_path.write_text(
                posterior_range.to_gtoplus(min_strategy=min_strategy),
                encoding="utf-8",
            )

            results.append(
                PlayerValidationResult(
                    player_name=player_row.player_name,
                    total_hands=player_row.total_hands,
                    vpip_pct=player_row.vpip_pct,
                    pfr_pct=player_row.pfr_pct,
                    vpip_pfr_gap_pct=player_row.vpip_pfr_gap_pct,
                    source_kind=node_stats.source_kind,
                    stats_raise_probability=node_stats.raise_probability,
                    prior_total_frequency=prior_range.total_frequency(),
                    posterior_total_frequency=posterior_range.total_frequency(),
                    gto_action_name=matched_action.action_name,
                    gto_action_type=matched_action.action_type or "",
                    gto_action_bet_size_bb=matched_action.bet_size_bb,
                    gto_source_id=matched_action.source_id,
                    gto_node_id=matched_action.node_id,
                    prior_gtoplus_path=str(prior_gtoplus_path),
                    posterior_gtoplus_path=str(posterior_gtoplus_path),
                )
            )
    finally:
        stats_repo.close()
        adapter.close()

    summary_csv_path = output_dir / "utg_open_ev_validation_summary.csv"
    write_validation_summary_csv(summary_csv_path=summary_csv_path, results=results)

    return ValidationOutput(
        summary_csv_path=summary_csv_path,
        prior_gtoplus_path=prior_gtoplus_path,
        player_count=len(results),
    )


def build_utg_open_player_node_context(table_type: TableType) -> PlayerNodeContext:
    """构造 UTG open 节点上下文。

    Args:
        table_type: 桌型。

    Returns:
        UTG 首次行动的玩家节点上下文。
    """

    if table_type is not TableType.SIX_MAX:
        raise ValueError("当前验证工具仅支持 SIX_MAX。")

    return PlayerNodeContext(
        actor_seat=3,
        actor_position=Position.UTG,
        action_order=(),
        node_context=NodeContext(
            actor_position=Position.UTG,
            aggressor_position=None,
            call_count=0,
            limp_count=0,
            raise_time=0,
            pot_size=1.5,
            raise_size_bb=None,
        ),
        params=PreFlopParams(
            table_type=table_type,
            position=MetricsPosition.UTG,
            num_callers=0,
            num_raises=0,
            num_active_players=6,
            previous_action=MetricsActionType.FOLD,
            in_position_on_flop=False,
        ),
    )


def select_players_with_large_vpip_pfr_gap(
    *,
    csv_path: Path,
    table_type_name: str,
    top_n: int,
    min_hands: int,
) -> list[PlayerGapRow]:
    """从核心统计 CSV 选择 VPIP/PFR 差异大的玩家。

    Args:
        csv_path: 核心统计 CSV 路径。
        table_type_name: 过滤桌型名称。
        top_n: 选取数量。
        min_hands: 最小样本手数。

    Returns:
        差异排序后的玩家行列表。
    """

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    selected: list[PlayerGapRow] = []
    for row in rows:
        current_table_type = (row.get("table_type") or "").strip().upper()
        if current_table_type != table_type_name.upper():
            continue

        player_name = (row.get("player_name") or "").strip()
        if not player_name or player_name.lower().startswith("aggregated_"):
            continue

        total_hands = int(float((row.get("total_hands") or "0").strip() or "0"))
        if total_hands < min_hands:
            continue

        vpip_pct = parse_percent_value(row.get("vpip_pct", ""))
        pfr_pct = parse_percent_value(row.get("pfr_pct", ""))
        if vpip_pct is None or pfr_pct is None:
            continue

        selected.append(
            PlayerGapRow(
                player_name=player_name,
                table_type=current_table_type,
                total_hands=total_hands,
                vpip_pct=vpip_pct,
                pfr_pct=pfr_pct,
                vpip_pfr_gap_pct=abs(vpip_pct - pfr_pct),
            )
        )

    selected.sort(
        key=lambda item: (
            -item.vpip_pfr_gap_pct,
            -item.total_hands,
            item.player_name,
        )
    )
    return selected[:top_n]


def write_validation_summary_csv(
    *,
    summary_csv_path: Path,
    results: list[PlayerValidationResult],
) -> None:
    """写出验证结果汇总 CSV。

    Args:
        summary_csv_path: 汇总 CSV 路径。
        results: 验证结果列表。
    """

    summary_csv_path.parent.mkdir(parents=True, exist_ok=True)
    headers = (
        "player_name",
        "total_hands",
        "vpip_pct",
        "pfr_pct",
        "vpip_pfr_gap_pct",
        "source_kind",
        "stats_raise_probability",
        "prior_total_frequency",
        "posterior_total_frequency",
        "gto_action_name",
        "gto_action_type",
        "gto_action_bet_size_bb",
        "gto_source_id",
        "gto_node_id",
        "prior_gtoplus_path",
        "posterior_gtoplus_path",
    )
    with summary_csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "player_name": result.player_name,
                    "total_hands": result.total_hands,
                    "vpip_pct": f"{result.vpip_pct:.1f}",
                    "pfr_pct": f"{result.pfr_pct:.1f}",
                    "vpip_pfr_gap_pct": f"{result.vpip_pfr_gap_pct:.1f}",
                    "source_kind": result.source_kind,
                    "stats_raise_probability": f"{result.stats_raise_probability:.6f}",
                    "prior_total_frequency": f"{result.prior_total_frequency:.6f}",
                    "posterior_total_frequency": f"{result.posterior_total_frequency:.6f}",
                    "gto_action_name": result.gto_action_name,
                    "gto_action_type": result.gto_action_type,
                    "gto_action_bet_size_bb": (
                        ""
                        if result.gto_action_bet_size_bb is None
                        else f"{result.gto_action_bet_size_bb:.3f}"
                    ),
                    "gto_source_id": ""
                    if result.gto_source_id is None
                    else result.gto_source_id,
                    "gto_node_id": ""
                    if result.gto_node_id is None
                    else result.gto_node_id,
                    "prior_gtoplus_path": result.prior_gtoplus_path,
                    "posterior_gtoplus_path": result.posterior_gtoplus_path,
                }
            )


def parse_percent_value(value: str) -> float | None:
    """解析 CSV 百分比字符串。

    Args:
        value: 百分比字符串，例如 `"41.9%"` 或 `"N/A"`。

    Returns:
        百分比浮点值；无法解析时返回 None。
    """

    normalized_value = value.strip()
    if not normalized_value or normalized_value.upper().startswith("N/A"):
        return None
    normalized_value = normalized_value.replace("%", "")
    try:
        return float(normalized_value)
    except ValueError:
        return None


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。

    Args:
        name: 原始名称。

    Returns:
        安全的文件名片段。
    """

    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return sanitized.strip("_") or "unknown"
