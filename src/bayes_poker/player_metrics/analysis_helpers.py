"""Notebook 分析辅助函数。"""

from __future__ import annotations

from typing import Literal

import pandas as pd

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_total_hands,
    calculate_wtp,
)
from bayes_poker.player_metrics.models import ActionStats, PlayerStats
from bayes_poker.player_metrics.params import PostFlopParams, PreFlopParams

AnalysisScope = Literal["preflop", "postflop"]


def _format_value(positive: float, total: float) -> str:
    """格式化正例与总样本。

    Args:
        positive: 正例数量。
        total: 总样本数量。

    Returns:
        形如 ``positive/total`` 的字符串。
    """
    return f"{positive:g}/{total:g}"


def _format_percent(numerator: float, denominator: float) -> str:
    """格式化百分比字符串。

    Args:
        numerator: 分子。
        denominator: 分母。

    Returns:
        百分比字符串。若分母为 0, 返回 ``N/A``。
    """
    if denominator <= 0:
        return "N/A"
    return f"{numerator / denominator * 100:.1f}%"


def build_core_stats_comparison(
    raw_stats: PlayerStats,
    smoothed_stats: PlayerStats,
) -> pd.DataFrame:
    """构造核心指标对比表。

    Args:
        raw_stats: 未平滑的玩家统计。
        smoothed_stats: 按玩家池平滑后的玩家统计。

    Returns:
        用于 notebook 直接展示的核心指标对比 DataFrame。
    """
    raw_pfr_positive, raw_pfr_total = calculate_pfr(raw_stats)
    smoothed_pfr_positive, smoothed_pfr_total = calculate_pfr(smoothed_stats)

    raw_wtp_positive, raw_wtp_total = calculate_wtp(raw_stats)
    smoothed_wtp_positive, smoothed_wtp_total = calculate_wtp(smoothed_stats)

    raw_agg_positive, raw_agg_total = calculate_aggression(raw_stats)
    smoothed_agg_positive, smoothed_agg_total = calculate_aggression(smoothed_stats)

    rows = [
        {
            "指标": "总手数",
            "原始值": str(calculate_total_hands(raw_stats)),
            "平滑值": str(calculate_total_hands(smoothed_stats)),
            "原始百分比": "-",
            "平滑百分比": "-",
        },
        {
            "指标": "VPIP",
            "原始值": _format_value(raw_stats.vpip.positive, raw_stats.vpip.total),
            "平滑值": _format_value(smoothed_stats.vpip.positive, smoothed_stats.vpip.total),
            "原始百分比": _format_percent(raw_stats.vpip.positive, raw_stats.vpip.total),
            "平滑百分比": _format_percent(
                smoothed_stats.vpip.positive,
                smoothed_stats.vpip.total,
            ),
        },
        {
            "指标": "PFR",
            "原始值": _format_value(raw_pfr_positive, raw_pfr_total),
            "平滑值": _format_value(smoothed_pfr_positive, smoothed_pfr_total),
            "原始百分比": _format_percent(raw_pfr_positive, raw_pfr_total),
            "平滑百分比": _format_percent(smoothed_pfr_positive, smoothed_pfr_total),
        },
        {
            "指标": "WTP",
            "原始值": _format_value(raw_wtp_positive, raw_wtp_total),
            "平滑值": _format_value(smoothed_wtp_positive, smoothed_wtp_total),
            "原始百分比": _format_percent(raw_wtp_positive, raw_wtp_total),
            "平滑百分比": _format_percent(smoothed_wtp_positive, smoothed_wtp_total),
        },
        {
            "指标": "AGG",
            "原始值": _format_value(raw_agg_positive, raw_agg_total),
            "平滑值": _format_value(smoothed_agg_positive, smoothed_agg_total),
            "原始百分比": _format_percent(raw_agg_positive, raw_agg_total),
            "平滑百分比": _format_percent(smoothed_agg_positive, smoothed_agg_total),
        },
    ]
    return pd.DataFrame(rows)


def _describe_preflop_params(params: PreFlopParams) -> str:
    """生成 Preflop 节点描述。

    Args:
        params: Preflop 参数对象。

    Returns:
        紧凑的节点说明字符串。
    """
    return (
        f"{params.position.name} | raises={params.num_raises} | callers={params.num_callers} | "
        f"prev={params.previous_action.name} | flop_ip={'是' if params.in_position_on_flop else '否'}"
    )


def _describe_postflop_params(params: PostFlopParams) -> str:
    """生成 Postflop 节点描述。

    Args:
        params: Postflop 参数对象。

    Returns:
        紧凑的节点说明字符串。
    """
    return (
        f"{params.street.name} | round={params.round} | prev={params.prev_action.name} | "
        f"bets={params.num_bets} | IP={'是' if params.in_position else '否'} | "
        f"players={params.num_players} | pot={params.preflop_pot_type.name} | "
        f"pfa={'是' if params.is_preflop_aggressor else '否'}"
    )


def _build_action_delta_row(
    index: int,
    description: str,
    raw_action: ActionStats,
    smoothed_action: ActionStats,
) -> dict[str, float | int | str]:
    """构造单个 action node 的对比行。

    Args:
        index: 节点索引。
        description: 节点描述。
        raw_action: 原始动作统计。
        smoothed_action: 平滑后动作统计。

    Returns:
        DataFrame 行字典。
    """
    raw_raise = raw_action.bet_raise_probability() * 100
    smoothed_raise = smoothed_action.bet_raise_probability() * 100
    raw_call = raw_action.check_call_probability() * 100
    smoothed_call = smoothed_action.check_call_probability() * 100
    raw_fold = raw_action.fold_probability() * 100
    smoothed_fold = smoothed_action.fold_probability() * 100
    delta = (
        abs(raw_raise - smoothed_raise)
        + abs(raw_call - smoothed_call)
        + abs(raw_fold - smoothed_fold)
    )

    return {
        "索引": index,
        "节点描述": description,
        "原始样本数": raw_action.total_samples(),
        "平滑样本数": round(smoothed_action.total_samples(), 2),
        "原始加注%": round(raw_raise, 1),
        "平滑加注%": round(smoothed_raise, 1),
        "原始跟注%": round(raw_call, 1),
        "平滑跟注%": round(smoothed_call, 1),
        "原始弃牌%": round(raw_fold, 1),
        "平滑弃牌%": round(smoothed_fold, 1),
        "L1差异": round(delta, 4),
    }


def build_node_delta_table(
    raw_stats: PlayerStats,
    smoothed_stats: PlayerStats,
    *,
    scope: AnalysisScope,
    top_n: int = 10,
) -> pd.DataFrame:
    """构造节点级概率差异表。

    Args:
        raw_stats: 未平滑的玩家统计。
        smoothed_stats: 按玩家池平滑后的玩家统计。
        scope: 对比范围, 仅支持 ``preflop`` 或 ``postflop``。
        top_n: 返回差异最大的前 N 个节点。

    Returns:
        排序后的节点差异 DataFrame。

    Raises:
        ValueError: 当 scope 不合法时抛出。
    """
    if top_n <= 0:
        raise ValueError("top_n 必须大于 0.")

    if scope == "preflop":
        params_list = PreFlopParams.get_all_params(raw_stats.table_type)
        raw_action_list = raw_stats.preflop_stats
        smoothed_action_list = smoothed_stats.preflop_stats
        describe = _describe_preflop_params
    elif scope == "postflop":
        params_list = PostFlopParams.get_all_params(raw_stats.table_type)
        raw_action_list = raw_stats.postflop_stats
        smoothed_action_list = smoothed_stats.postflop_stats
        describe = _describe_postflop_params
    else:
        raise ValueError(f"不支持的 scope: {scope}")

    max_items = min(len(params_list), len(raw_action_list), len(smoothed_action_list))

    rows: list[dict[str, float | int | str]] = []
    for index in range(max_items):
        params = params_list[index]
        raw_action = raw_action_list[index]
        smoothed_action = smoothed_action_list[index]
        if raw_action.total_samples() <= 0:
            continue
        rows.append(
            _build_action_delta_row(
                index=index,
                description=describe(params),
                raw_action=raw_action,
                smoothed_action=smoothed_action,
            )
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "索引",
                "节点描述",
                "原始样本数",
                "平滑样本数",
                "原始加注%",
                "平滑加注%",
                "原始跟注%",
                "平滑跟注%",
                "原始弃牌%",
                "平滑弃牌%",
                "L1差异",
            ]
        )

    result = pd.DataFrame(rows)
    return result.sort_values("L1差异", ascending=False).head(top_n).reset_index(drop=True)
