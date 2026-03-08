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

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.models import ActionStats, PlayerStats, StatValue
from bayes_poker.player_metrics.enums import ActionType
from bayes_poker.player_metrics.params import PreFlopParams
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
    """构造仓库平滑测试使用的最小玩家统计。"""

    stats = PlayerStats(player_name=player_name, table_type=TableType.SIX_MAX)
    stats.vpip = StatValue(positive=10, total=20)
    while len(stats.preflop_stats) <= preflop_index:
        stats.preflop_stats.append(ActionStats())
    target = stats.preflop_stats[preflop_index]
    target.fold_samples = fold_samples
    target.check_call_samples = check_call_samples
    target.raise_samples = raise_samples
    return stats


class TestPoolSmoothedGet:
    """测试仓库读取时的玩家池后验平滑。"""

    @pytest.fixture
    def db_path(self) -> Path:
        """创建临时数据库路径。"""

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    def test_get_can_return_pool_smoothed_binary_stats(self, db_path: Path) -> None:
        """二元节点应按 Beta 公式返回平滑后的 pseudo-count。"""

        params = PreFlopParams.get_all_params(TableType.SIX_MAX)[4]
        with PlayerStatsRepository(db_path) as repo:
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="Hero",
                    preflop_index=params.to_index(),
                    fold_samples=7,
                    check_call_samples=0,
                    raise_samples=3,
                ),
            )
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="aggregated_sixmax_100",
                    preflop_index=params.to_index(),
                    fold_samples=50,
                    check_call_samples=0,
                    raise_samples=50,
                ),
            )

            raw_stats = repo.get("Hero", TableType.SIX_MAX)
            smoothed_stats = repo.get(
                "Hero",
                TableType.SIX_MAX,
                smooth_with_pool=True,
                pool_prior_strength=20.0,
            )

        assert raw_stats is not None
        assert smoothed_stats is not None
        assert raw_stats.preflop_stats[params.to_index()].raise_samples == pytest.approx(3.0)
        assert raw_stats.preflop_stats[params.to_index()].fold_samples == pytest.approx(7.0)
        assert smoothed_stats.preflop_stats[params.to_index()].raise_samples == pytest.approx(
            13.0
        )
        assert smoothed_stats.preflop_stats[params.to_index()].fold_samples == pytest.approx(
            17.0
        )

    def test_get_can_return_pool_smoothed_multinomial_stats(self, db_path: Path) -> None:
        """三元节点应按 Dirichlet 公式返回平滑后的 pseudo-count。"""

        params = PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=PreFlopParams.get_all_params(TableType.SIX_MAX)[7].position,
            num_callers=0,
            num_raises=1,
            num_active_players=6,
            previous_action=ActionType.FOLD,
            in_position_on_flop=False,
        )
        index = params.to_index()
        with PlayerStatsRepository(db_path) as repo:
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="Hero",
                    preflop_index=index,
                    fold_samples=1,
                    check_call_samples=2,
                    raise_samples=1,
                ),
            )
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="aggregated_sixmax_100",
                    preflop_index=index,
                    fold_samples=6,
                    check_call_samples=3,
                    raise_samples=1,
                ),
            )

            smoothed_stats = repo.get(
                "Hero",
                TableType.SIX_MAX,
                smooth_with_pool=True,
                pool_prior_strength=10.0,
            )

        assert smoothed_stats is not None
        target = smoothed_stats.preflop_stats[index]
        assert target.fold_samples == pytest.approx(7.0)
        assert target.check_call_samples == pytest.approx(5.0)
        assert target.raise_samples == pytest.approx(2.0)

    def test_get_can_smooth_high_index_preflop_bucket(self, db_path: Path) -> None:
        """Rust 高索引 preflop 桶也应按显式动作空间规则平滑。"""

        index = 31
        with PlayerStatsRepository(db_path) as repo:
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="Hero",
                    preflop_index=index,
                    fold_samples=1,
                    check_call_samples=2,
                    raise_samples=1,
                ),
            )
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="aggregated_sixmax_100",
                    preflop_index=index,
                    fold_samples=6,
                    check_call_samples=3,
                    raise_samples=1,
                ),
            )

            smoothed_stats = repo.get(
                "Hero",
                TableType.SIX_MAX,
                smooth_with_pool=True,
                pool_prior_strength=10.0,
            )

        assert smoothed_stats is not None
        target = smoothed_stats.preflop_stats[index]
        assert target.fold_samples == pytest.approx(7.0)
        assert target.check_call_samples == pytest.approx(5.0)
        assert target.raise_samples == pytest.approx(2.0)

    def test_get_smoothed_stats_returns_raw_when_pool_missing(self, db_path: Path) -> None:
        """缺少玩家池统计时应直接回退 raw 结果。"""

        params = PreFlopParams.get_all_params(TableType.SIX_MAX)[4]
        with PlayerStatsRepository(db_path) as repo:
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="Hero",
                    preflop_index=params.to_index(),
                    fold_samples=7,
                    check_call_samples=0,
                    raise_samples=3,
                ),
            )

            raw_stats = repo.get("Hero", TableType.SIX_MAX)
            smoothed_stats = repo.get(
                "Hero",
                TableType.SIX_MAX,
                smooth_with_pool=True,
                pool_prior_strength=20.0,
            )

        assert raw_stats is not None
        assert smoothed_stats is not None
        assert smoothed_stats.preflop_stats[params.to_index()].raise_samples == pytest.approx(
            raw_stats.preflop_stats[params.to_index()].raise_samples
        )
        assert smoothed_stats.preflop_stats[params.to_index()].fold_samples == pytest.approx(
            raw_stats.preflop_stats[params.to_index()].fold_samples
        )

    def test_get_does_not_smooth_aggregated_player_row(self, db_path: Path) -> None:
        """聚合玩家行自身应始终返回 raw 结果。"""

        params = PreFlopParams.get_all_params(TableType.SIX_MAX)[4]
        with PlayerStatsRepository(db_path) as repo:
            _insert_player_stats(
                repo,
                _make_player_stats(
                    player_name="aggregated_sixmax_100",
                    preflop_index=params.to_index(),
                    fold_samples=50,
                    check_call_samples=0,
                    raise_samples=50,
                ),
            )

            aggregated_stats = repo.get(
                "aggregated_sixmax_100",
                TableType.SIX_MAX,
                smooth_with_pool=True,
                pool_prior_strength=20.0,
            )

        assert aggregated_stats is not None
        target = aggregated_stats.preflop_stats[params.to_index()]
        assert target.raise_samples == pytest.approx(50.0)
        assert target.fold_samples == pytest.approx(50.0)


def _build_stats(
    *,
    player_name: str,
    preflop_raise: float,
    preflop_fold: float,
    postflop_raise: float,
    postflop_check_call: float,
) -> PlayerStats:
    """构造测试使用的玩家统计."""

    stats = PlayerStats(player_name=player_name, table_type=TableType.SIX_MAX)
    stats.preflop_stats[0].raise_samples = preflop_raise
    stats.preflop_stats[0].fold_samples = preflop_fold
    stats.postflop_stats[0].raise_samples = postflop_raise
    stats.postflop_stats[0].check_call_samples = postflop_check_call
    return stats


class _StubPlayerStatsRepository(PlayerStatsRepository):
    """基于内存字典的仓库替身."""

    def __init__(self, stats_by_key: dict[tuple[str, TableType], PlayerStats]) -> None:
        super().__init__(Path(":memory:"))
        self._stats_by_key = stats_by_key

    def _get_raw(self, player_name: str, table_type: TableType) -> PlayerStats | None:
        """返回预置的 raw 统计."""

        return self._stats_by_key.get((player_name, table_type))


class TestPoolSmoothedReads:
    """玩家池后验平滑读取测试."""

    def test_get_can_return_pool_smoothed_stats(self) -> None:
        """测试 `get(..., smooth_with_pool=True)` 返回后验平滑结果."""

        hero_stats = _build_stats(
            player_name="Hero",
            preflop_raise=3.0,
            preflop_fold=7.0,
            postflop_raise=6.0,
            postflop_check_call=4.0,
        )
        aggregated_stats = _build_stats(
            player_name="aggregated_sixmax_100",
            preflop_raise=40.0,
            preflop_fold=60.0,
            postflop_raise=20.0,
            postflop_check_call=80.0,
        )
        repo = _StubPlayerStatsRepository(
            {
                ("Hero", TableType.SIX_MAX): hero_stats,
                ("aggregated_sixmax_100", TableType.SIX_MAX): aggregated_stats,
            }
        )

        smoothed_stats = repo.get(
            "Hero",
            TableType.SIX_MAX,
            smooth_with_pool=True,
            pool_prior_strength=20.0,
        )

        assert smoothed_stats is not None
        assert smoothed_stats.preflop_stats[0].raise_samples == pytest.approx(11.0)
        assert smoothed_stats.preflop_stats[0].fold_samples == pytest.approx(19.0)
        assert smoothed_stats.preflop_stats[0].check_call_samples == pytest.approx(0.0)
        assert smoothed_stats.postflop_stats[0].raise_samples == pytest.approx(10.0)
        assert smoothed_stats.postflop_stats[0].check_call_samples == pytest.approx(20.0)
        assert smoothed_stats.postflop_stats[0].fold_samples == pytest.approx(0.0)

    def test_get_returns_raw_stats_when_pool_is_missing(self) -> None:
        """测试缺少聚合玩家时回退到 raw stats."""

        hero_stats = _build_stats(
            player_name="Hero",
            preflop_raise=3.0,
            preflop_fold=7.0,
            postflop_raise=6.0,
            postflop_check_call=4.0,
        )
        repo = _StubPlayerStatsRepository(
            {
                ("Hero", TableType.SIX_MAX): hero_stats,
            }
        )

        smoothed_stats = repo.get(
            "Hero",
            TableType.SIX_MAX,
            smooth_with_pool=True,
            pool_prior_strength=20.0,
        )

        assert smoothed_stats is hero_stats
