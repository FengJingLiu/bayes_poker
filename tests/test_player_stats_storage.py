"""PlayerStats 存储模块测试。

测试覆盖：
- 二进制反序列化
- 累加合并
- 手牌去重
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest

from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_pfr,
    calculate_wtp,
)
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.serialization import merge_player_stats
from bayes_poker.storage import PlayerStatsRepository


class TestMergePlayerStats:
    """累加合并测试。"""

    def test_merge_vpip(self) -> None:
        """测试 VPIP 累加。"""
        target = PlayerStats(player_name="Player", table_type=TableType.SIX_MAX)
        target.vpip = StatValue(positive=10, total=20)

        source = PlayerStats(player_name="Player", table_type=TableType.SIX_MAX)
        source.vpip = StatValue(positive=5, total=10)

        merge_player_stats(target, source)

        assert target.vpip.positive == 15
        assert target.vpip.total == 30

    def test_merge_preflop_stats(self) -> None:
        """测试翻前统计累加。"""
        target = PlayerStats(player_name="Player", table_type=TableType.SIX_MAX)
        target.preflop_stats[0].fold_samples = 10

        source = PlayerStats(player_name="Player", table_type=TableType.SIX_MAX)
        source.preflop_stats[0].fold_samples = 5

        merge_player_stats(target, source)

        assert target.preflop_stats[0].fold_samples == 15

    def test_merge_table_type_mismatch(self) -> None:
        """测试桌型不匹配时抛出异常。"""
        target = PlayerStats(player_name="Player", table_type=TableType.SIX_MAX)
        source = PlayerStats(player_name="Player", table_type=TableType.HEADS_UP)

        with pytest.raises(ValueError, match="table_type 不匹配"):
            merge_player_stats(target, source)


class TestHandDeduplication:
    """手牌去重测试。"""

    @pytest.fixture
    def db_path(self) -> Path:
        """创建临时数据库路径。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    def test_is_hand_processed(self, db_path: Path) -> None:
        """测试单个手牌检查。"""
        hand_hash = "h" * 32
        with PlayerStatsRepository(db_path) as repo:
            assert not repo.is_hand_processed(hand_hash)

            repo.mark_hand_processed(hand_hash)

            assert repo.is_hand_processed(hand_hash)

    def test_get_processed_hand_hashes(self, db_path: Path) -> None:
        """测试批量检查。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])

            processed = repo.get_processed_hand_hashes(["a" * 32, "b" * 32, "d" * 32])

        assert processed == {"a" * 32, "b" * 32}

    def test_mark_hands_processed_idempotent(self, db_path: Path) -> None:
        """测试重复标记不报错。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.mark_hands_processed(["a" * 32, "b" * 32])
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])  # 包含已存在的

            count = repo.get_processed_hands_count()

        assert count == 3

    def test_get_stats(self, db_path: Path) -> None:
        """测试统计信息。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])

            stats = repo.get_stats()

        assert stats["player_count"] == 0
        assert stats["processed_hands_count"] == 3

    def test_clear(self, db_path: Path) -> None:
        """测试清空数据。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])

            repo.clear()

            stats = repo.get_stats()

        assert stats["player_count"] == 0
        assert stats["processed_hands_count"] == 0


def _serialize_action_stats(action_stats: ActionStats) -> bytes:
    """序列化单个 `ActionStats` 供仓库测试写库使用。"""

    return struct.pack(
        "<7i",
        int(action_stats.bet_0_40),
        int(action_stats.bet_40_80),
        int(action_stats.bet_80_120),
        int(action_stats.bet_over_120),
        int(action_stats.raise_samples),
        int(action_stats.check_call_samples),
        int(action_stats.fold_samples),
    )


def _serialize_player_stats(stats: PlayerStats) -> bytes:
    """按 Rust 二进制格式序列化 `PlayerStats`。"""

    name_bytes = stats.player_name.encode("utf-8")
    payload = bytearray()
    payload.extend(struct.pack("<I", len(name_bytes)))
    payload.extend(name_bytes)
    payload.extend(struct.pack("<B", int(stats.table_type)))
    payload.extend(struct.pack("<2i", stats.vpip.positive, stats.vpip.total))
    payload.extend(struct.pack("<I", len(stats.preflop_stats)))
    for action_stats in stats.preflop_stats:
        payload.extend(_serialize_action_stats(action_stats))
    payload.extend(struct.pack("<I", len(stats.postflop_stats)))
    for action_stats in stats.postflop_stats:
        payload.extend(_serialize_action_stats(action_stats))
    return bytes(payload)


def _insert_player_stats(repo: PlayerStatsRepository, stats: PlayerStats) -> None:
    """向测试数据库插入一条玩家统计记录。"""

    repo.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            table_type INTEGER NOT NULL,
            vpip_positive INTEGER NOT NULL DEFAULT 0,
            vpip_total INTEGER NOT NULL DEFAULT 0,
            stats_binary BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_name, table_type)
        )
        """
    )
    repo.conn.execute(
        """
        INSERT INTO player_stats (
            player_name,
            table_type,
            vpip_positive,
            vpip_total,
            stats_binary,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            stats.player_name,
            int(stats.table_type),
            stats.vpip.positive,
            stats.vpip.total,
            _serialize_player_stats(stats),
        ),
    )
    repo.conn.commit()


def _make_player_stats(
    *,
    player_name: str,
    preflop_index: int,
    fold_samples: int,
    check_call_samples: int,
    raise_samples: int,
) -> PlayerStats:
    """构造最小玩家统计。"""

    stats = PlayerStats(player_name=player_name, table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=10, total=20)
    while len(stats.preflop_stats) <= preflop_index:
        stats.preflop_stats.append(ActionStats())
    target = stats.preflop_stats[preflop_index]
    target.fold_samples = fold_samples
    target.check_call_samples = check_call_samples
    target.raise_samples = raise_samples
    return stats


def _make_dense_player_stats(
    *,
    player_name: str,
    total_hands: int = 40,
) -> PlayerStats:
    """构造用于 summary 表测试的致密玩家统计.

    Args:
        player_name: 玩家名.
        total_hands: 总手数.

    Returns:
        覆盖全部翻前和翻后节点的 `PlayerStats`.
    """

    stats = PlayerStats(player_name=player_name, table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=total_hands // 2, total=total_hands)

    for index, action_stats in enumerate(stats.preflop_stats):
        action_stats.raise_samples = 2 + (index % 3)
        action_stats.check_call_samples = 3 + (index % 2)
        action_stats.fold_samples = 1 + (index % 4)

    for index, action_stats in enumerate(stats.postflop_stats):
        action_stats.raise_samples = 1 + (index % 5)
        action_stats.check_call_samples = 2 + (index % 3)
        action_stats.fold_samples = index % 2

    return stats


class TestPlayerMetricsSummaryStorage:
    """`player_metrics_summary` 表构建与读取测试."""

    def test_build_metrics_summary_creates_rows(self, tmp_path: Path) -> None:
        """应写入 summary 行并返回轻量指标.

        Args:
            tmp_path: pytest 提供的临时目录.

        Returns:
            None.
        """

        alice = _make_dense_player_stats(player_name="alice", total_hands=48)
        bob = _make_dense_player_stats(player_name="bob", total_hands=64)

        with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
            _insert_player_stats(repo, alice)
            _insert_player_stats(repo, bob)

            written = repo.build_metrics_summary(TableType.SIX_MAX, batch_size=1)
            summaries = repo.load_summary_for_estimator(TableType.SIX_MAX)

        expected = {}
        for stats in (alice, bob):
            expected[stats.player_name] = {
                "total_hands": stats.vpip.total,
                "pfr": calculate_pfr(stats),
                "agg": calculate_aggression(stats),
                "wtp": calculate_wtp(stats),
            }

        assert written == 2
        assert len(summaries) == 2
        assert [summary.player_name for summary in summaries] == ["alice", "bob"]
        for summary in summaries:
            metric = expected[summary.player_name]
            assert summary.table_type == TableType.SIX_MAX
            assert summary.total_hands == metric["total_hands"]
            assert (summary.vpip_pos, summary.vpip_total) == (
                metric["total_hands"] // 2,
                metric["total_hands"],
            )
            assert (summary.pfr_pos, summary.pfr_total) == metric["pfr"]
            assert (summary.agg_pos, summary.agg_total) == metric["agg"]
            assert (summary.wtp_pos, summary.wtp_total) == metric["wtp"]

    def test_build_metrics_summary_excludes_aggregated(self, tmp_path: Path) -> None:
        """应跳过 `aggregated_*` 玩家.

        Args:
            tmp_path: pytest 提供的临时目录.

        Returns:
            None.
        """

        with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
            _insert_player_stats(
                repo,
                _make_dense_player_stats(
                    player_name="aggregated_sixmax_100",
                    total_hands=80,
                ),
            )
            _insert_player_stats(
                repo,
                _make_dense_player_stats(player_name="villain", total_hands=60),
            )

            written = repo.build_metrics_summary(TableType.SIX_MAX, batch_size=2)
            summaries = repo.load_summary_for_estimator(TableType.SIX_MAX)

        assert written == 1
        assert [summary.player_name for summary in summaries] == ["villain"]

    def test_load_summary_returns_empty_when_table_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """缺少 summary 表时应平稳降级为空列表.

        Args:
            tmp_path: pytest 提供的临时目录.

        Returns:
            None.
        """

        with PlayerStatsRepository(tmp_path / "player_stats.db") as repo:
            assert repo.summary_table_exists() is False
            assert repo.load_summary_for_estimator(TableType.SIX_MAX) == []
