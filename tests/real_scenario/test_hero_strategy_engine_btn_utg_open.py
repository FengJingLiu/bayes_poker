"""真实场景: 验证 BTN 面对 UTG open 2.5bb 的 Hero 策略输出。"""

from __future__ import annotations

import asyncio
import csv
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from bayes_poker.domain.poker import ActionType, Street
from bayes_poker.domain.table import Player, PlayerAction, Position
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
    StrategyEngineConfig,
    build_strategy_engine,
)
from bayes_poker.strategy.strategy_engine.utg_open_ev_validation import (
    parse_percent_value,
    sanitize_filename,
)
from bayes_poker.table.observed_state import ObservedTableState

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STRATEGY_DB_PATH = _REPO_ROOT / "data" / "database" / "preflop_strategy.sqlite3"
_PLAYER_STATS_DB_PATH = _REPO_ROOT / "data" / "database" / "player_stats.db"
_PLAYER_CORE_STATS_CSV_PATH = _REPO_ROOT / "data" / "database" / "player_core_stats.csv"
_RUN_REAL_SCENARIO_ENV = "BAYES_POKER_RUN_REAL_SCENARIO_TESTS"


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
        action_distribution: Hero 动作分布。
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
    sampling_random: float
    sampled_action_code: str | None
    gtoplus_by_action: dict[str, str]


def _load_players_with_large_pfr_spread(
    *,
    csv_path: Path,
    min_hands: int,
    sample_count: int,
) -> list[PlayerPfrRow]:
    """按 PFR 差异挑选玩家样本。

    策略为: 先过滤 `SIX_MAX` 且 `total_hands > min_hands` 的玩家, 再按 PFR 升序等距取点,
    以确保样本之间的 PFR 差异尽可能大。

    Args:
        csv_path: 玩家核心统计 CSV 路径。
        min_hands: 最小总手数（严格大于）。
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
    spread_indexes = _build_even_spread_indexes(
        total_count=len(candidates),
        sample_count=sample_count,
    )
    return [candidates[index] for index in spread_indexes]


def _build_even_spread_indexes(*, total_count: int, sample_count: int) -> list[int]:
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


def _build_btn_vs_utg_open_state(
    *, utg_player_name: str, state_version: int
) -> ObservedTableState:
    """构造 BTN 面对 UTG open 2.5bb 的 preflop 快照。

    Args:
        utg_player_name: UTG 玩家名。
        state_version: 状态版本号。

    Returns:
        可直接喂给 StrategyEngine 的观察状态。
    """

    players = [
        Player(
            seat_index=0,
            player_id="hero_btn",
            stack=100.0,
            bet=0.0,
            position=Position.BTN,
            is_button=True,
        ),
        Player(
            seat_index=1,
            player_id="sb_player",
            stack=99.5,
            bet=0.5,
            position=Position.SB,
        ),
        Player(
            seat_index=2,
            player_id="bb_player",
            stack=99.0,
            bet=1.0,
            position=Position.BB,
        ),
        Player(
            seat_index=3,
            player_id=utg_player_name,
            stack=97.5,
            bet=2.5,
            position=Position.UTG,
        ),
        Player(
            seat_index=4,
            player_id="mp_folded_player",
            stack=100.0,
            bet=0.0,
            position=Position.MP,
            is_folded=True,
        ),
        Player(
            seat_index=5,
            player_id="co_folded_player",
            stack=100.0,
            bet=0.0,
            position=Position.CO,
            is_folded=True,
        ),
    ]

    action_history = [
        PlayerAction(
            player_index=3,
            action_type=ActionType.RAISE,
            amount=2.5,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=4,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        ),
        PlayerAction(
            player_index=5,
            action_type=ActionType.FOLD,
            amount=0.0,
            street=Street.PREFLOP,
        ),
    ]

    return ObservedTableState(
        table_id="real_scenario_btn_vs_utg_open",
        player_count=6,
        small_blind=0.5,
        big_blind=1.0,
        hand_id=f"real_hand_{state_version}",
        street=Street.PREFLOP,
        pot=4.0,
        btn_seat=0,
        actor_seat=0,
        hero_seat=0,
        hero_cards=("As", "Kh"),
        players=players,
        action_history=action_history,
        state_version=state_version,
    )


def _load_gtoplus_ranges_for_decision(
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
        `action_code -> gtoplus_text` 映射。

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
            f"节点动作为空，无法导出 GTO+。node_id={decision.selected_node_id}"
        )

    gtoplus_by_action: dict[str, str] = {}
    for action_option in action_options:
        gtoplus_by_action[action_option.action_code] = (
            action_option.preflop_range.to_gtoplus(min_strategy=min_strategy)
        )
    return gtoplus_by_action


def _write_gtoplus_exports(
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


def _print_snapshot(snapshot: HeroStrategySnapshot) -> None:
    """打印单个玩家的策略快照摘要和 GTO+ 文本。

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
    print(f"动作分布: {snapshot.action_distribution}")
    for action_code, gtoplus_text in sorted(snapshot.gtoplus_by_action.items()):
        print(f"[GTO+] action={action_code}")
        print(gtoplus_text)


def _print_pairwise_range_comparison(snapshots: list[HeroStrategySnapshot]) -> None:
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


@pytest.mark.large_sample
@pytest.mark.skipif(
    not _STRATEGY_DB_PATH.exists(),
    reason="策略数据库不存在",
)
@pytest.mark.skipif(
    not _PLAYER_STATS_DB_PATH.exists(),
    reason="玩家统计数据库不存在",
)
@pytest.mark.skipif(
    not _PLAYER_CORE_STATS_CSV_PATH.exists(),
    reason="player_core_stats.csv 不存在",
)
def test_real_scenario_btn_vs_utg_open_hero_strategy_ranges(tmp_path: Path) -> None:
    """验证真实场景 Hero 策略并输出 GTO+。

    该测试会在真实数据库上执行 `StrategyEngine`：
    - Hero 固定在 BTN。
    - 前缀动作为 UTG open 2.5bb，MP/CO fold，轮到 Hero。
    - 从 `player_core_stats.csv` 中挑选 `total_hands > 200` 且 PFR 差异较大的玩家。
    - 对比不同玩家下 Hero 命中节点与动作范围，并打印 GTO+ 文本。

    Args:
        tmp_path: pytest 临时目录。
    """

    if os.environ.get(_RUN_REAL_SCENARIO_ENV) != "1":
        pytest.skip(f"未启用真实场景测试（设置 {_RUN_REAL_SCENARIO_ENV}=1 才运行）。")

    selected_players = _load_players_with_large_pfr_spread(
        csv_path=_PLAYER_CORE_STATS_CSV_PATH,
        min_hands=200,
        sample_count=3,
    )
    pfr_values = [row.pfr_pct for row in selected_players]
    assert max(pfr_values) > min(pfr_values)

    engine = build_strategy_engine(
        StrategyEngineConfig(
            strategy_db_path=_STRATEGY_DB_PATH,
            player_stats_db_path=_PLAYER_STATS_DB_PATH,
            table_type=TableType.SIX_MAX,
            source_ids=(1, 2, 3, 4, 5),
        )
    )

    snapshots: list[HeroStrategySnapshot] = []
    for index, player_row in enumerate(selected_players, start=1):
        observed_state = _build_btn_vs_utg_open_state(
            utg_player_name=player_row.player_name,
            state_version=index,
        )
        decision = asyncio.run(
            engine(
                session_id=(
                    "real_btn_vs_utg_open_"
                    f"{sanitize_filename(player_row.player_name)}_{index}"
                ),
                observed_state=observed_state,
            )
        )

        assert isinstance(
            decision,
            RecommendationDecision,
        ), f"期望 RecommendationDecision，实际={type(decision).__name__}"
        assert decision.selected_node_id is not None
        assert decision.selected_source_id is not None
        assert decision.sampling_random is not None
        assert 0.0 <= decision.sampling_random < 1.0
        assert decision.action_distribution
        assert pytest.approx(1.0, abs=1e-6) == sum(
            decision.action_distribution.values()
        )

        gtoplus_by_action = _load_gtoplus_ranges_for_decision(
            engine=engine,
            decision=decision,
            min_strategy=0.001,
        )
        assert gtoplus_by_action

        snapshot = HeroStrategySnapshot(
            player_name=player_row.player_name,
            total_hands=player_row.total_hands,
            pfr_pct=player_row.pfr_pct,
            selected_node_id=decision.selected_node_id,
            selected_source_id=decision.selected_source_id,
            action_distribution=dict(decision.action_distribution),
            sampling_random=decision.sampling_random,
            sampled_action_code=decision.action_code,
            gtoplus_by_action=gtoplus_by_action,
        )
        snapshots.append(snapshot)

    assert len(snapshots) == 3

    export_dir = tmp_path / "real_scenario_gtoplus_btn_vs_utg_open"
    for snapshot in snapshots:
        _write_gtoplus_exports(output_dir=export_dir, snapshot=snapshot)
        _print_snapshot(snapshot)
    _print_pairwise_range_comparison(snapshots)
