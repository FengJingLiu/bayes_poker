"""PlayerStats 存储模块测试。

测试覆盖：
- 二进制反序列化
- 累加合并
- 手牌去重
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

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
