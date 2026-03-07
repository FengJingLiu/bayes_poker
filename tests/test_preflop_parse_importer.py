"""翻前策略 sqlite 导入测试。"""

from __future__ import annotations

from pathlib import Path

from bayes_poker.storage.preflop_strategy_repository import PreflopStrategyRepository
from bayes_poker.strategy.preflop_parse.importer import (
    import_strategy_directory_to_sqlite,
)
from bayes_poker.strategy.preflop_parse.loader import (
    build_preflop_strategy_db,
    open_preflop_strategy_repository,
)

_STRATEGY_VECTOR = "[" + ", ".join(["0.2"] * 169) + "]"
_EV_VECTOR = "[" + ", ".join(["0.0"] * 169) + "]"
_CALL_STRATEGY_VECTOR = "[" + ", ".join(["0.8"] * 169) + "]"
_CALL_EV_VECTOR = "[" + ", ".join(["0.1"] * 169) + "]"


def _create_strategy_fixture(root_dir: Path) -> Path:
    """创建最小可用的策略目录。

    Args:
        root_dir: 临时目录根路径。

    Returns:
        构造好的策略目录路径。
    """

    strategy_dir = root_dir / "Cash6m50zGeneral"
    strategy_dir.mkdir(parents=True, exist_ok=True)
    (strategy_dir / "Cash6m50zGeneral_100_R2-C.json").write_text(
        f"""
        {{
          "solutions": [
            {{
              "action": {{
                "code": "F",
                "position": "CO",
                "type": "FOLD",
                "next_position": "",
                "allin": false
              }},
              "total_frequency": 0.2,
              "total_ev": 0.0,
              "total_combos": 10.0,
              "strategy": {_STRATEGY_VECTOR},
              "evs": {_EV_VECTOR}
            }},
            {{
              "action": {{
                "code": "C",
                "position": "CO",
                "type": "CALL",
                "next_position": "",
                "allin": false
              }},
              "total_frequency": 0.8,
              "total_ev": 0.1,
              "total_combos": 30.0,
              "strategy": {_CALL_STRATEGY_VECTOR},
              "evs": {_CALL_EV_VECTOR}
            }}
          ]
        }}
        """,
        encoding="utf-8",
    )
    return strategy_dir


def test_import_strategy_directory_builds_sqlite_database(tmp_path: Path) -> None:
    """应能从策略目录导入 sqlite 数据库。"""

    strategy_dir = _create_strategy_fixture(tmp_path / "strategy_fixture")
    db_path = tmp_path / "strategy.db"

    import_strategy_directory_to_sqlite(
        strategy_dir=strategy_dir,
        db_path=db_path,
    )

    repo = PreflopStrategyRepository(db_path)
    repo.connect()

    assert repo.list_sources()
    assert repo.count_nodes() > 0
    assert repo.count_actions() > 0

    repo.close()


def test_loader_builds_and_opens_preflop_strategy_repository(
    tmp_path: Path,
) -> None:
    """应能通过高层 loader 构建并打开仓库。"""

    strategy_dir = _create_strategy_fixture(tmp_path / "strategy_fixture")
    db_path = build_preflop_strategy_db(
        strategy_dir=strategy_dir,
        db_path=tmp_path / "built.db",
    )
    repo = open_preflop_strategy_repository(db_path)

    assert db_path.exists()
    assert repo.list_sources()

    repo.close()
