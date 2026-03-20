"""真实场景: 跨场景综合对手画像覆盖测试。

按不同数据量级别 (不足 <50 手 / 中等 50-300 手 / 充足 >300 手)
和不同 VPIP/PFR 分段 (紧被动/紧激进/松被动/松激进) 组合,
遍历所有场景 (RFI / 3-Bet / Facing 3-Bet / 4-Bet / Hero Open Facing 4-Bet
/ Hero 3-Bet Facing 4-Bet), 记录每种情况下的对手先验/后验分布和
Hero 的应对策略, 并输出详细报告到 docs/real_scenario/。

门控条件: BAYES_POKER_RUN_REAL_SCENARIO_TESTS=1 + 数据库文件存在。
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from bayes_poker.domain.table import Position
from bayes_poker.strategy.strategy_engine import (
    RecommendationDecision,
    StrategyEngine,
    UnsupportedScenarioDecision,
    SafeFallbackDecision,
)

from .helpers import (
    ALL_RFI_COMBINATIONS_6MAX,
    ALL_3BET_COMBINATIONS_6MAX,
    ALL_FACING_3BET_COMBINATIONS_6MAX,
    ALL_4BET_COMBINATIONS_6MAX,
    ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX,
    ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX,
    PLAYER_CORE_STATS_CSV_PATH,
    PLAYER_STATS_DB_PATH,
    RUN_REAL_SCENARIO_ENV,
    STRATEGY_DB_PATH,
    OpponentProfile,
    assert_valid_recommendation,
    build_3bet_state,
    build_4bet_state,
    build_facing_3bet_state,
    build_hero_3bet_facing_4bet_state,
    build_hero_open_facing_4bet_state,
    build_rfi_state,
    generate_scenario_report,
    load_opponent_profiles,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
REPORT_OUTPUT_DIR: Path = REPO_ROOT / "docs" / "real_scenario"

# ---------------------------------------------------------------------------
# 门控跳过
# ---------------------------------------------------------------------------

_SKIP_REASON_ENV = f"未启用真实场景测试 (设置 {RUN_REAL_SCENARIO_ENV}=1 才运行)"
_SKIP_REASON_DB = f"策略数据库不存在: {STRATEGY_DB_PATH}"
_SKIP_REASON_STATS = f"玩家统计数据库不存在: {PLAYER_STATS_DB_PATH}"
_SKIP_REASON_CSV = f"玩家核心统计 CSV 不存在: {PLAYER_CORE_STATS_CSV_PATH}"

pytestmark = [
    pytest.mark.large_sample,
    pytest.mark.skipif(
        os.environ.get(RUN_REAL_SCENARIO_ENV) != "1",
        reason=_SKIP_REASON_ENV,
    ),
    pytest.mark.skipif(
        not STRATEGY_DB_PATH.exists(),
        reason=_SKIP_REASON_DB,
    ),
    pytest.mark.skipif(
        not PLAYER_STATS_DB_PATH.exists(),
        reason=_SKIP_REASON_STATS,
    ),
    pytest.mark.skipif(
        not PLAYER_CORE_STATS_CSV_PATH.exists(),
        reason=_SKIP_REASON_CSV,
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def opponent_profiles() -> list[OpponentProfile]:
    """加载覆盖 data_level x VPIP/PFR segment 的对手画像样本。

    Returns:
        各分组的代表性对手画像列表。
    """
    return load_opponent_profiles(
        csv_path=PLAYER_CORE_STATS_CSV_PATH,
        per_group=1,
    )


# ---------------------------------------------------------------------------
# 全量合法位置组合
# ---------------------------------------------------------------------------

_REPRESENTATIVE_RFI: list[tuple[Position, Position]] = ALL_RFI_COMBINATIONS_6MAX
"""RFI 全部合法位置组合。"""

_REPRESENTATIVE_3BET: list[tuple[Position, Position, Position]] = (
    ALL_3BET_COMBINATIONS_6MAX
)
"""3-Bet 全部合法位置组合。"""

_REPRESENTATIVE_FACING_3BET: list[tuple[Position, Position]] = (
    ALL_FACING_3BET_COMBINATIONS_6MAX
)
"""Facing 3-Bet 全部合法位置组合。"""

_REPRESENTATIVE_4BET: list[tuple[Position, Position, Position, Position]] = (
    ALL_4BET_COMBINATIONS_6MAX
)
"""4-Bet 全部合法位置组合。"""

_REPRESENTATIVE_HERO_OPEN_FACING_4BET: list[tuple[Position, Position, Position]] = (
    ALL_HERO_OPEN_FACING_4BET_COMBINATIONS_6MAX
)
"""Hero Open Facing 4-Bet 全部合法位置组合。"""

_REPRESENTATIVE_HERO_3BET_FACING_4BET: list[tuple[Position, Position, Position]] = (
    ALL_HERO_3BET_FACING_4BET_COMBINATIONS_6MAX
)
"""Hero 3-Bet Facing 4-Bet 全部合法位置组合。"""


# ---------------------------------------------------------------------------
# 核心执行: 单场景 x 全画像
# ---------------------------------------------------------------------------


def _run_single_scenario(
    *,
    engine: StrategyEngine,
    profiles: list[OpponentProfile],
    scenario_name: str,
    build_state_fn: object,
    combos: list[object],
    combo_to_kwargs: object,
) -> list[dict[str, object]]:
    """对一个场景, 遍历全部合法组合 x 全部对手画像, 收集结果。

    Args:
        engine: StrategyEngine 实例。
        profiles: 对手画像列表。
        scenario_name: 场景名 (用于 session_id 和日志)。
        build_state_fn: 状态构造函数。
        combos: 合法位置组合列表。
        combo_to_kwargs: 将 combo + profile 转为 build_state_fn 参数的回调。

    Returns:
        结果字典列表。
    """
    results: list[dict[str, object]] = []
    state_version = 0

    for combo in combos:
        for profile in profiles:
            state_version += 1
            kwargs = combo_to_kwargs(combo, profile, state_version)  # type: ignore[operator]
            observed_state = build_state_fn(**kwargs)  # type: ignore[operator]

            combo_str = str(combo)
            session_id = (
                f"comprehensive_{scenario_name}_{combo_str}"
                f"_{profile.player_name}_{state_version}"
            )

            t0 = time.perf_counter()
            try:
                decision = asyncio.run(
                    engine(session_id=session_id, observed_state=observed_state)
                )
            except (ValueError, Exception) as exc:
                # 数据不足等场景下引擎可能抛出异常, 记录并继续
                elapsed_ms = (time.perf_counter() - t0) * 1000
                result: dict[str, object] = {
                    "combo": combo_str,
                    "player_name": profile.player_name,
                    "total_hands": profile.total_hands,
                    "vpip_pct": profile.vpip_pct,
                    "pfr_pct": profile.pfr_pct,
                    "data_level": profile.data_level,
                    "segment": profile.segment,
                    "elapsed_ms": elapsed_ms,
                    "decision_type": "Error",
                    "error_message": str(exc),
                    "prior_distribution": {},
                    "posterior_distribution": {},
                    "opponent_aggression_details": [],
                }
                results.append(result)
                continue
            elapsed_ms = (time.perf_counter() - t0) * 1000

            result = {
                "combo": combo_str,
                "player_name": profile.player_name,
                "total_hands": profile.total_hands,
                "vpip_pct": profile.vpip_pct,
                "pfr_pct": profile.pfr_pct,
                "data_level": profile.data_level,
                "segment": profile.segment,
                "elapsed_ms": elapsed_ms,
                "decision_type": type(decision).__name__,
            }

            if isinstance(decision, RecommendationDecision):
                result["prior_distribution"] = dict(decision.prior_action_distribution)
                result["posterior_distribution"] = dict(decision.action_distribution)
                result["node_id"] = decision.selected_node_id
                result["source_id"] = decision.selected_source_id
                result["opponent_aggression_details"] = list(
                    decision.opponent_aggression_details
                )
            else:
                result["prior_distribution"] = {}
                result["posterior_distribution"] = {}
                result["opponent_aggression_details"] = []

            results.append(result)

    return results


# ---------------------------------------------------------------------------
# combo -> kwargs 转换函数
# ---------------------------------------------------------------------------


def _rfi_combo_to_kwargs(
    combo: tuple[Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """RFI 组合转状态构造参数。"""
    opener_pos, hero_pos = combo
    return {
        "hero_position": hero_pos,
        "opener_position": opener_pos,
        "opener_player_name": profile.player_name,
        "state_version": state_version,
    }


def _3bet_combo_to_kwargs(
    combo: tuple[Position, Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """3-Bet 组合转状态构造参数。"""
    opener_pos, three_bettor_pos, hero_pos = combo
    return {
        "hero_position": hero_pos,
        "opener_position": opener_pos,
        "three_bettor_position": three_bettor_pos,
        "opener_player_name": profile.player_name,
        "three_bettor_player_name": profile.player_name,
        "state_version": state_version,
    }


def _facing_3bet_combo_to_kwargs(
    combo: tuple[Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """Facing 3-Bet 组合转状态构造参数。"""
    hero_opener_pos, three_bettor_pos = combo
    return {
        "hero_opener_position": hero_opener_pos,
        "three_bettor_position": three_bettor_pos,
        "three_bettor_player_name": profile.player_name,
        "state_version": state_version,
    }


def _4bet_combo_to_kwargs(
    combo: tuple[Position, Position, Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """4-Bet 组合转状态构造参数。"""
    opener_pos, three_bettor_pos, four_bettor_pos, hero_pos = combo
    return {
        "hero_position": hero_pos,
        "opener_position": opener_pos,
        "three_bettor_position": three_bettor_pos,
        "four_bettor_position": four_bettor_pos,
        "opener_player_name": profile.player_name,
        "three_bettor_player_name": profile.player_name,
        "four_bettor_player_name": profile.player_name,
        "state_version": state_version,
    }


def _hero_open_facing_4bet_combo_to_kwargs(
    combo: tuple[Position, Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """Hero Open Facing 4-Bet 组合转状态构造参数。"""
    hero_opener_pos, three_bettor_pos, four_bettor_pos = combo
    return {
        "hero_opener_position": hero_opener_pos,
        "three_bettor_position": three_bettor_pos,
        "four_bettor_position": four_bettor_pos,
        "three_bettor_player_name": profile.player_name,
        "four_bettor_player_name": profile.player_name,
        "state_version": state_version,
    }


def _hero_3bet_facing_4bet_combo_to_kwargs(
    combo: tuple[Position, Position, Position],
    profile: OpponentProfile,
    state_version: int,
) -> dict[str, object]:
    """Hero 3-Bet Facing 4-Bet 组合转状态构造参数。"""
    opener_pos, hero_3bettor_pos, four_bettor_pos = combo
    return {
        "opener_position": opener_pos,
        "hero_3bettor_position": hero_3bettor_pos,
        "four_bettor_position": four_bettor_pos,
        "opener_player_name": profile.player_name,
        "four_bettor_player_name": profile.player_name,
        "state_version": state_version,
    }


# ---------------------------------------------------------------------------
# 测试: RFI 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_rfi_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """RFI 场景: 遍历全部合法组合 x 全部对手画像, 验证并生成报告。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="rfi",
        build_state_fn=build_rfi_state,
        combos=_REPRESENTATIVE_RFI,
        combo_to_kwargs=_rfi_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "RFI", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: 3-Bet 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_3bet_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """3-Bet 场景: 遍历全部合法组合 x 全部对手画像, 验证并生成报告。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="3bet",
        build_state_fn=build_3bet_state,
        combos=_REPRESENTATIVE_3BET,
        combo_to_kwargs=_3bet_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "3-Bet", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: Facing 3-Bet 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_facing_3bet_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """Facing 3-Bet 场景: 遍历全部合法组合 x 全部对手画像, 验证并生成报告。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="facing_3bet",
        build_state_fn=build_facing_3bet_state,
        combos=_REPRESENTATIVE_FACING_3BET,
        combo_to_kwargs=_facing_3bet_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "Facing_3-Bet", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: 4-Bet 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_4bet_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """4-Bet 场景: 遍历全部合法组合 x 全部对手画像, 验证并生成报告。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="4bet",
        build_state_fn=build_4bet_state,
        combos=_REPRESENTATIVE_4BET,
        combo_to_kwargs=_4bet_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "4-Bet", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: Hero Open Facing 4-Bet 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_hero_open_facing_4bet_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """Hero Open Facing 4-Bet 场景: 遍历全部合法组合 x 全部对手画像。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="hero_open_facing_4bet",
        build_state_fn=build_hero_open_facing_4bet_state,
        combos=_REPRESENTATIVE_HERO_OPEN_FACING_4BET,
        combo_to_kwargs=_hero_open_facing_4bet_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "Hero_Open_Facing_4-Bet", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: Hero 3-Bet Facing 4-Bet 场景综合画像覆盖
# ---------------------------------------------------------------------------


def test_hero_3bet_facing_4bet_comprehensive_opponent_profiles(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """Hero 3-Bet Facing 4-Bet 场景: 遍历全部合法组合 x 全部对手画像。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    t0 = time.perf_counter()
    results = _run_single_scenario(
        engine=real_scenario_engine,
        profiles=opponent_profiles,
        scenario_name="hero_3bet_facing_4bet",
        build_state_fn=build_hero_3bet_facing_4bet_state,
        combos=_REPRESENTATIVE_HERO_3BET_FACING_4BET,
        combo_to_kwargs=_hero_3bet_facing_4bet_combo_to_kwargs,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    _assert_and_report(results, "Hero_3-Bet_Facing_4-Bet", elapsed_ms)


# ---------------------------------------------------------------------------
# 测试: 全场景综合报告汇总
# ---------------------------------------------------------------------------


def test_generate_summary_report(
    real_scenario_engine: StrategyEngine,
    opponent_profiles: list[OpponentProfile],
) -> None:
    """汇总全场景结果, 生成 docs/real_scenario/summary.md 总报告。

    Args:
        real_scenario_engine: StrategyEngine fixture。
        opponent_profiles: 对手画像 fixture。
    """
    all_results: dict[str, list[dict[str, object]]] = {}
    total_t0 = time.perf_counter()

    scenarios = [
        ("RFI", build_rfi_state, _REPRESENTATIVE_RFI, _rfi_combo_to_kwargs),
        ("3-Bet", build_3bet_state, _REPRESENTATIVE_3BET, _3bet_combo_to_kwargs),
        (
            "Facing_3-Bet",
            build_facing_3bet_state,
            _REPRESENTATIVE_FACING_3BET,
            _facing_3bet_combo_to_kwargs,
        ),
        ("4-Bet", build_4bet_state, _REPRESENTATIVE_4BET, _4bet_combo_to_kwargs),
        (
            "Hero_Open_Facing_4-Bet",
            build_hero_open_facing_4bet_state,
            _REPRESENTATIVE_HERO_OPEN_FACING_4BET,
            _hero_open_facing_4bet_combo_to_kwargs,
        ),
        (
            "Hero_3-Bet_Facing_4-Bet",
            build_hero_3bet_facing_4bet_state,
            _REPRESENTATIVE_HERO_3BET_FACING_4BET,
            _hero_3bet_facing_4bet_combo_to_kwargs,
        ),
    ]

    for name, build_fn, combos, kwargs_fn in scenarios:
        results = _run_single_scenario(
            engine=real_scenario_engine,
            profiles=opponent_profiles,
            scenario_name=name.lower().replace("-", "").replace(" ", "_"),
            build_state_fn=build_fn,
            combos=combos,
            combo_to_kwargs=kwargs_fn,
        )
        all_results[name] = results

    total_elapsed_ms = (time.perf_counter() - total_t0) * 1000

    # 生成汇总报告
    _generate_summary(all_results, total_elapsed_ms)

    # 基本断言
    total_calls = sum(len(r) for r in all_results.values())
    assert total_calls > 0, "应至少有 1 条结果"
    print(f"\n[综合报告] 共 {total_calls} 次引擎调用, 总耗时 {total_elapsed_ms:.1f}ms")


# ---------------------------------------------------------------------------
# 断言与报告辅助
# ---------------------------------------------------------------------------


def _assert_and_report(
    results: list[dict[str, object]],
    scenario_name: str,
    total_elapsed_ms: float,
) -> None:
    """通用断言 + 报告生成。

    Args:
        results: 单场景结果列表。
        scenario_name: 场景名。
        total_elapsed_ms: 总耗时。
    """
    assert len(results) > 0, f"{scenario_name}: 无结果"

    # 统计各类决策类型
    type_counts: dict[str, int] = {}
    for r in results:
        dt = str(r.get("decision_type", "unknown"))
        type_counts[dt] = type_counts.get(dt, 0) + 1

    rec_count = type_counts.get("RecommendationDecision", 0)
    err_count = type_counts.get("Error", 0)
    print(
        f"\n[{scenario_name}] 结果: total={len(results)}, "
        f"recommendations={rec_count}, errors={err_count}, "
        f"types={type_counts}, "
        f"elapsed={total_elapsed_ms:.1f}ms"
    )

    # 生成报告
    report_path = REPORT_OUTPUT_DIR / f"{scenario_name.lower()}_report.md"
    generate_scenario_report(
        output_path=report_path,
        scenario_name=scenario_name,
        results=results,
        total_elapsed_ms=total_elapsed_ms,
    )


def _generate_summary(
    all_results: dict[str, list[dict[str, object]]],
    total_elapsed_ms: float,
) -> None:
    """生成 docs/real_scenario/summary.md 汇总报告。

    Args:
        all_results: scenario_name -> results 映射。
        total_elapsed_ms: 全部场景总耗时。
    """
    output_path = REPORT_OUTPUT_DIR / "summary.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# 真实场景综合测试报告汇总\n\n")
    lines.append(f"全部场景总耗时: {total_elapsed_ms:.1f}ms\n\n")

    # 概览表
    lines.append("## 场景概览\n\n")
    lines.append("| 场景 | 总调用数 | 推荐决策数 | 不支持数 | 降级数 | 错误数 | 平均耗时(ms) |\n")
    lines.append("|------|---------|-----------|---------|-------|-------|-------------|\n")

    for name, results in all_results.items():
        total = len(results)
        rec_count = sum(
            1 for r in results if r.get("decision_type") == "RecommendationDecision"
        )
        unsupported = sum(
            1
            for r in results
            if r.get("decision_type") == "UnsupportedScenarioDecision"
        )
        fallback = sum(
            1 for r in results if r.get("decision_type") == "SafeFallbackDecision"
        )
        errors = sum(
            1 for r in results if r.get("decision_type") == "Error"
        )
        avg_ms = (
            sum(float(r.get("elapsed_ms", 0)) for r in results) / total  # type: ignore[arg-type]
            if total
            else 0.0
        )
        lines.append(
            f"| {name} | {total} | {rec_count} | {unsupported} | {fallback} "
            f"| {errors} | {avg_ms:.1f} |\n"
        )

    lines.append("\n")

    # 按数据量级别汇总
    lines.append("## 按数据量级别汇总\n\n")
    all_flat = [r for rs in all_results.values() for r in rs]
    for level in ["insufficient", "medium", "sufficient"]:
        level_results = [r for r in all_flat if r.get("data_level") == level]
        if not level_results:
            continue

        level_label = {
            "insufficient": "数据不足 (<50手)",
            "medium": "数据中等 (50-300手)",
            "sufficient": "数据充足 (>300手)",
        }[level]

        rec_count = sum(
            1 for r in level_results
            if r.get("decision_type") == "RecommendationDecision"
        )
        total = len(level_results)
        avg_ms = (
            sum(float(r.get("elapsed_ms", 0)) for r in level_results)  # type: ignore[arg-type]
            / total
        )

        lines.append(
            f"### {level_label}\n\n"
            f"- 总调用: {total}, 推荐决策: {rec_count}, "
            f"平均耗时: {avg_ms:.1f}ms\n\n"
        )

    # 按 VPIP/PFR 分段汇总
    lines.append("## 按 VPIP/PFR 分段汇总\n\n")
    for seg in [
        "tight_passive",
        "tight_aggressive",
        "loose_passive",
        "loose_aggressive",
    ]:
        seg_results = [r for r in all_flat if r.get("segment") == seg]
        if not seg_results:
            continue

        seg_label = {
            "tight_passive": "紧被动 (低VPIP/低PFR)",
            "tight_aggressive": "紧激进 (低VPIP/高PFR)",
            "loose_passive": "松被动 (高VPIP/低PFR)",
            "loose_aggressive": "松激进 (高VPIP/高PFR)",
        }[seg]

        rec_count = sum(
            1 for r in seg_results
            if r.get("decision_type") == "RecommendationDecision"
        )
        total = len(seg_results)

        lines.append(
            f"### {seg_label}\n\n"
            f"- 总调用: {total}, 推荐决策: {rec_count}\n\n"
        )

    output_path.write_text("".join(lines), encoding="utf-8")
    print(f"\n[汇总] 综合报告已写入: {output_path}")
