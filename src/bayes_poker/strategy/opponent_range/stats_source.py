"""对手范围预测使用的统计数据来源。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bayes_poker.player_metrics.enums import TableType

if TYPE_CHECKING:
    from bayes_poker.player_metrics.models import PlayerStats
    from bayes_poker.storage.player_stats_repository import PlayerStatsRepository


_AGGREGATED_PLAYER_NAMES: dict[TableType, str] = {
    TableType.SIX_MAX: "aggregated_sixmax_100",
}


def get_aggregated_player_name(table_type: TableType) -> str | None:
    """返回指定桌型的聚合玩家名。

    Args:
        table_type: 桌型。

    Returns:
        聚合玩家名, 不存在时返回 `None`。
    """
    return _AGGREGATED_PLAYER_NAMES.get(table_type)


def get_aggregated_player_stats(
    repo: "PlayerStatsRepository",
    table_type: TableType,
) -> "PlayerStats | None":
    """读取聚合玩家统计。

    Args:
        repo: 统计仓库。
        table_type: 桌型。

    Returns:
        聚合玩家统计, 不存在时返回 `None`。
    """
    player_name = get_aggregated_player_name(table_type)
    if not player_name:
        return None
    return repo.get(player_name, table_type, smooth_with_pool=False)
