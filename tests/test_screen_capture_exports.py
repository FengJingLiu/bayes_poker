"""屏幕模块导出兼容性测试。"""

from __future__ import annotations


def test_screen_capture_exports() -> None:
    """测试 screen 模块的公共导出。"""
    from bayes_poker.screen import (
        MockScreenCapture,
        ScreenCapture,
        Win32ScreenCapture,
        get_screen_capture,
    )

    assert ScreenCapture is not None
    assert Win32ScreenCapture is not None
    assert MockScreenCapture is not None
    assert get_screen_capture is not None


def test_mock_screen_capture() -> None:
    """测试 MockScreenCapture 基本功能。"""
    import numpy as np

    from bayes_poker.screen import MockScreenCapture

    # 创建测试图像
    test_image = np.zeros((100, 200, 3), dtype=np.uint8)
    test_image[10:20, 30:50] = 255

    capture = MockScreenCapture(test_image)

    # 测试 get_desktop_size
    size = capture.get_desktop_size()
    assert size == (200, 100)

    # 测试 capture_region
    region = capture.capture_region(30, 10, 20, 10)
    assert region is not None
    assert region.shape == (10, 20, 3)
    assert region[0, 0, 0] == 255
