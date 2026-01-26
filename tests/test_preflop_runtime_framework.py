import asyncio
import json
import tempfile
from pathlib import Path

from bayes_poker.strategy.runtime.preflop import (
    PreflopLayer,
    create_preflop_strategy_from_directory,
    infer_preflop_layer,
)


def test_infer_preflop_layer() -> None:
    assert infer_preflop_layer("") == PreflopLayer.RFI
    assert infer_preflop_layer("C") == PreflopLayer.RFI
    assert infer_preflop_layer("F-R2") == PreflopLayer.THREE_BET
    assert infer_preflop_layer("F-R2-R6") == PreflopLayer.FOUR_BET


def test_create_preflop_strategy_from_directory_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        strategy_dir = Path(tmpdir) / "Cash6m50zGeneral"
        strategy_dir.mkdir(parents=True)

        data = {
            "solutions": [
                {
                    "action": {
                        "code": "F",
                        "position": "UTG",
                        "type": "FOLD",
                        "next_position": "HJ",
                        "allin": False,
                    },
                    "total_frequency": 1.0,
                    "total_ev": 0.0,
                    "total_combos": 0.0,
                    "strategy": [1.0] * 169,
                    "evs": [0.0] * 169,
                }
            ]
        }

        (strategy_dir / "Cash6m50zGeneral_100.json").write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        handler = create_preflop_strategy_from_directory(strategy_dir=strategy_dir)
        result = asyncio.run(
            handler(
                "s1",
                {
                    "street": "preflop",
                    "state_version": 1,
                    "stack_bb": 100,
                    "history": "",
                    "hero_cards": ["As", "Ks"],
                },
            )
        )

        assert result["state_version"] == 1
        assert "matched" in str(result.get("notes", ""))

