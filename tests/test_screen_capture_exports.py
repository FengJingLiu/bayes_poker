"""屏幕模块导出兼容性测试。"""

from __future__ import annotations


def test_window_info_exported_from_capture() -> None:
    from bayes_poker.screen.capture import WindowInfo as CaptureWindowInfo
    from bayes_poker.screen.types import WindowInfo as TypesWindowInfo

    assert CaptureWindowInfo is TypesWindowInfo
