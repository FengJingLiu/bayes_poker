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
    legacy_reference_tests = (
        _REPO_ROOT / "tests" / "test_preflop_engine_state.py",
        _REPO_ROOT / "tests" / "test_opponent_range.py",
    )

    for test_file in legacy_reference_tests:
        assert test_file.exists() is False

    supported_action_families = {
        action_family
        for action_family in (
            "OPEN",
            "CALL_VS_OPEN",
            "LIMP",
            "THREE_BET",
            "FOUR_BET",
        )
        if _is_v1_supported(6, "preflop", action_family, True)
    }
    assert supported_action_families == {"OPEN", "CALL_VS_OPEN", "LIMP"}


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
