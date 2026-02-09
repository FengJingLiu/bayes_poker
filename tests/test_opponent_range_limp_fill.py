"""limp 频率填充与聚合玩家数据入口测试。"""

from __future__ import annotations

from dataclasses import dataclass

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import PlayerStats
from bayes_poker.strategy.preflop_parse.models import StrategyAction, StrategyNode
from bayes_poker.strategy.range import (
    RANGE_169_LENGTH,
    PreflopRange,
    get_hand_key_to_169_index,
)


@dataclass
class _RecordingRepo:
    """记录 get 调用参数的仓库替身。"""

    called_with: list[tuple[str, TableType]]

    def get(self, player_name: str, table_type: TableType) -> PlayerStats | None:
        """记录查询参数并返回空值。

        Args:
            player_name: 查询玩家名。
            table_type: 桌型。

        Returns:
            恒定返回空值。
        """
        self.called_with.append((player_name, table_type))
        return None


def _range_with_peak(hand_key: str, ev: float) -> PreflopRange:
    """创建指定手牌 EV 峰值向量。

    Args:
        hand_key: 手牌键。
        ev: 峰值 EV。

    Returns:
        对应的翻前范围。
    """
    strategy = [1.0] * RANGE_169_LENGTH
    evs = [0.0] * RANGE_169_LENGTH
    evs[get_hand_key_to_169_index()[hand_key]] = ev
    return PreflopRange(strategy=strategy, evs=evs)


def test_build_limp_calling_range_uses_min_raise_size_ev() -> None:
    """多个 raise 时应使用最小尺度 raise 的 EV 排序。"""
    from bayes_poker.strategy.opponent_range.frequency_fill import build_limp_calling_range

    node = StrategyNode(
        history_full="C",
        history_actions="C",
        history_token_count=1,
        acting_position="CO",
        source_file="test.json",
        actions=(
            StrategyAction(
                order_index=0,
                action_code="R2",
                action_type="RAISE",
                bet_size_bb=2.0,
                is_all_in=False,
                total_frequency=0.3,
                next_position="BTN",
                range=_range_with_peak("AKs", 100.0),
            ),
            StrategyAction(
                order_index=1,
                action_code="R6",
                action_type="RAISE",
                bet_size_bb=6.0,
                is_all_in=False,
                total_frequency=0.2,
                next_position="BTN",
                range=_range_with_peak("22", 200.0),
            ),
        ),
    )

    limp_call_range = build_limp_calling_range(
        node=node,
        raise_frequency=0.0,
        call_frequency=0.001,
    )

    aks = get_hand_key_to_169_index()["AKs"]
    pocket_twos = get_hand_key_to_169_index()["22"]
    assert limp_call_range.strategy[aks] > limp_call_range.strategy[pocket_twos]


def test_get_aggregated_player_stats_uses_fixed_sixmax_name() -> None:
    """sixmax 聚合统计应固定查询 aggregated_sixmax_100。"""
    from bayes_poker.strategy.opponent_range.stats_source import get_aggregated_player_stats

    repo = _RecordingRepo(called_with=[])
    _ = get_aggregated_player_stats(repo, TableType.SIX_MAX)
    assert repo.called_with == [("aggregated_sixmax_100", TableType.SIX_MAX)]
