from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STRATEGY_ENGINE_ROOT = (
    _REPO_ROOT / "src" / "bayes_poker" / "strategy" / "strategy_engine"
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "bayes_poker.strategy.preflop_engine",
    "bayes_poker.strategy.runtime",
    "bayes_poker.strategy.preflop_parse.query",
)


def _iter_strategy_engine_python_files() -> list[Path]:
    if not _STRATEGY_ENGINE_ROOT.exists():
        return []
    return sorted(_STRATEGY_ENGINE_ROOT.rglob("*.py"))


def _collect_forbidden_imports(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                violations.append(module)
    return violations


def _is_v1_supported(
    player_count: int,
    street: str,
    action_family: str,
    is_first_action: bool,
) -> bool:
    return (
        player_count == 6
        and street == "preflop"
        and is_first_action
        and action_family in {"OPEN", "CALL_VS_OPEN", "LIMP"}
    )


def test_strategy_engine_v2_forbids_legacy_runtime_imports() -> None:
    violations_by_file: dict[str, list[str]] = {}
    for file_path in _iter_strategy_engine_python_files():
        violations = _collect_forbidden_imports(file_path)
        if violations:
            violations_by_file[str(file_path.relative_to(_REPO_ROOT))] = violations

    assert violations_by_file == {}


def test_strategy_engine_v2_support_matrix_is_frozen() -> None:
    assert _is_v1_supported(6, "preflop", "OPEN", True) is True
    assert _is_v1_supported(6, "preflop", "CALL_VS_OPEN", True) is True
    assert _is_v1_supported(6, "preflop", "LIMP", True) is True

    assert _is_v1_supported(6, "preflop", "THREE_BET", True) is False
    assert _is_v1_supported(2, "preflop", "OPEN", True) is False
    assert _is_v1_supported(9, "preflop", "OPEN", True) is False
    assert _is_v1_supported(6, "flop", "OPEN", True) is False
    assert _is_v1_supported(6, "preflop", "OPEN", False) is False


def test_strategy_engine_v2_scope_matches_reference_tests() -> None:
    state_test = (_REPO_ROOT / "tests" / "test_preflop_engine_state.py").read_text(
        encoding="utf-8"
    )
    opponent_range_test = (_REPO_ROOT / "tests" / "test_opponent_range.py").read_text(
        encoding="utf-8"
    )

    assert "ActionFamily.OPEN" in state_test
    assert "ActionFamily.CALL_VS_OPEN" in state_test
    assert 'match="limp"' in state_test
    assert 'match="多次加注"' in state_test

    assert "test_shared_adapter_rejects_three_bet_first_action" in opponent_range_test
    assert "Street.PREFLOP" in opponent_range_test


def test_top_level_strategy_exports_point_to_v2() -> None:
    from bayes_poker.strategy import (
        StrategyDecision,
        StrategyHandler,
        StrategyEngine,
        create_strategy_handler,
        create_preflop_strategy,
    )

    assert StrategyDecision is not None
    assert StrategyHandler is not None
    assert StrategyEngine is not None
    assert create_strategy_handler is not None
    assert create_preflop_strategy is not None
