"""PlayerStats 存储模块测试。

测试覆盖：
- 序列化/反序列化
- 累加合并
- SQLite 仓库 CRUD
- 手牌去重
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.serialization import (
    action_stats_from_dict,
    action_stats_list_from_json,
    action_stats_list_to_json,
    action_stats_to_dict,
    merge_player_stats,
    player_stats_from_row,
    player_stats_to_row,
    stat_value_from_dict,
    stat_value_to_dict,
)
from bayes_poker.storage import PlayerStatsRepository


class TestStatValueSerialization:
    """StatValue 序列化测试。"""

    def test_roundtrip(self) -> None:
        """测试 StatValue 序列化往返。"""
        original = StatValue(positive=10, total=25)
        d = stat_value_to_dict(original)
        restored = stat_value_from_dict(d)

        assert restored.positive == original.positive
        assert restored.total == original.total


class TestActionStatsSerialization:
    """ActionStats 序列化测试。"""

    def test_to_dict(self) -> None:
        """测试转换为字典。"""
        stats = ActionStats(
            bet_0_40=1,
            bet_40_80=2,
            bet_80_120=3,
            bet_over_120=4,
            raise_samples=5,
            check_call_samples=6,
            fold_samples=7,
        )
        d = action_stats_to_dict(stats)

        assert d["bet_0_40"] == 1
        assert d["fold_samples"] == 7

    def test_from_dict(self) -> None:
        """测试从字典恢复。"""
        d = {
            "bet_0_40": 10,
            "bet_40_80": 20,
            "bet_80_120": 30,
            "bet_over_120": 40,
            "raise_samples": 50,
            "check_call_samples": 60,
            "fold_samples": 70,
        }
        stats = action_stats_from_dict(d)

        assert stats.bet_0_40 == 10
        assert stats.fold_samples == 70

    def test_list_roundtrip(self) -> None:
        """测试列表序列化往返。"""
        original = [
            ActionStats(bet_0_40=1, fold_samples=2),
            ActionStats(bet_40_80=3, check_call_samples=4),
        ]
        json_str = action_stats_list_to_json(original)
        restored = action_stats_list_from_json(json_str)

        assert len(restored) == 2
        assert restored[0].bet_0_40 == 1
        assert restored[1].bet_40_80 == 3


class TestPlayerStatsSerialization:
    """PlayerStats 序列化测试。"""

    def test_to_row(self) -> None:
        """测试转换为数据库行。"""
        stats = PlayerStats(player_name="TestPlayer", table_type=TableType.SIX_MAX)
        stats.vpip = StatValue(positive=50, total=100)

        row = player_stats_to_row(stats)

        assert row["player_name"] == "TestPlayer"
        assert row["table_type"] == 6
        assert row["vpip_positive"] == 50
        assert row["vpip_total"] == 100
        assert "preflop_stats_json" in row
        assert "postflop_stats_json" in row

    def test_roundtrip(self) -> None:
        """测试完整往返。"""
        original = PlayerStats(player_name="RoundTrip", table_type=TableType.HEADS_UP)
        original.vpip = StatValue(positive=25, total=50)
        original.preflop_stats[0].bet_0_40 = 5
        original.postflop_stats[0].fold_samples = 10

        row = player_stats_to_row(original)
        restored = player_stats_from_row(row)

        assert restored.player_name == original.player_name
        assert restored.table_type == original.table_type
        assert restored.vpip.positive == 25
        assert restored.vpip.total == 50
        assert restored.preflop_stats[0].bet_0_40 == 5
        assert restored.postflop_stats[0].fold_samples == 10


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


class TestPlayerStatsRepository:
    """SQLite 仓库测试。"""

    @pytest.fixture
    def db_path(self) -> Path:
        """创建临时数据库路径。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    def test_upsert_and_get(self, db_path: Path) -> None:
        """测试插入和查询。"""
        stats = PlayerStats(player_name="TestPlayer", table_type=TableType.SIX_MAX)
        stats.vpip = StatValue(positive=10, total=20)

        with PlayerStatsRepository(db_path) as repo:
            repo.upsert(stats)
            retrieved = repo.get("TestPlayer", TableType.SIX_MAX)

        assert retrieved is not None
        assert retrieved.player_name == "TestPlayer"
        assert retrieved.vpip.positive == 10

    def test_upsert_with_merge(self, db_path: Path) -> None:
        """测试累加更新。"""
        stats1 = PlayerStats(player_name="MergeTest", table_type=TableType.SIX_MAX)
        stats1.vpip = StatValue(positive=10, total=20)

        stats2 = PlayerStats(player_name="MergeTest", table_type=TableType.SIX_MAX)
        stats2.vpip = StatValue(positive=5, total=10)

        with PlayerStatsRepository(db_path) as repo:
            repo.upsert_with_merge(stats1)
            repo.upsert_with_merge(stats2)
            retrieved = repo.get("MergeTest", TableType.SIX_MAX)

        assert retrieved is not None
        assert retrieved.vpip.positive == 15
        assert retrieved.vpip.total == 30

    def test_get_all(self, db_path: Path) -> None:
        """测试批量查询。"""
        with PlayerStatsRepository(db_path) as repo:
            for i in range(5):
                stats = PlayerStats(player_name=f"Player{i}", table_type=TableType.SIX_MAX)
                repo.upsert(stats)

            all_stats = repo.get_all(TableType.SIX_MAX)

        assert len(all_stats) == 5

    def test_get_stats(self, db_path: Path) -> None:
        """测试统计信息。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.upsert(PlayerStats(player_name="P1", table_type=TableType.SIX_MAX))
            repo.upsert(PlayerStats(player_name="P2", table_type=TableType.HEADS_UP))
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])

            stats = repo.get_stats()

        assert stats["player_count"] == 2
        assert stats["processed_hands_count"] == 3


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

    def test_clear(self, db_path: Path) -> None:
        """测试清空数据。"""
        with PlayerStatsRepository(db_path) as repo:
            repo.upsert(PlayerStats(player_name="P1", table_type=TableType.SIX_MAX))
            repo.mark_hands_processed(["a" * 32, "b" * 32, "c" * 32])

            repo.clear()

            stats = repo.get_stats()

        assert stats["player_count"] == 0
        assert stats["processed_hands_count"] == 0
