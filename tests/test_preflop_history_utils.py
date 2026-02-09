"""preflop_history 工具测试。"""

from bayes_poker.strategy.runtime.preflop_history import (
    PreflopLayer,
    PreflopScenario,
    classify_preflop_scenario,
    count_limpers_in_history,
    infer_preflop_layer,
    is_open_no_limper,
)


def test_infer_preflop_layer_compatibility() -> None:
    """应保持与原 runtime 相同的分层推断行为。"""
    assert infer_preflop_layer("") == PreflopLayer.RFI
    assert infer_preflop_layer("C") == PreflopLayer.RFI
    assert infer_preflop_layer("F-R2") == PreflopLayer.THREE_BET
    assert infer_preflop_layer("F-R2-R6") == PreflopLayer.FOUR_BET


def test_count_limpers_in_history_ignores_raised_pot() -> None:
    """出现 raise 后 limper 计数应归零。"""
    assert count_limpers_in_history("C-C") == 2
    assert count_limpers_in_history("C-R2") == 0


def test_classify_preflop_scenario() -> None:
    """应基于前缀给出翻前场景。"""
    assert classify_preflop_scenario("C") == PreflopScenario.RFI_FACE_LIMPER
    assert classify_preflop_scenario("") == PreflopScenario.RFI_NO_LIMPER
    assert classify_preflop_scenario("F-R2") == PreflopScenario.THREE_BET
    assert classify_preflop_scenario("F-R2-R6") == PreflopScenario.FOUR_BET
    assert is_open_no_limper("F-F")
