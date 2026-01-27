"""屏幕截图模块。"""

from bayes_poker.screen.capture import (
    MockScreenCapture,
    ScreenCapture,
    Win32ScreenCapture,
    get_screen_capture,
)
from bayes_poker.screen.types import WindowInfo

__all__ = [
    "ScreenCapture",
    "Win32ScreenCapture",
    "MockScreenCapture",
    "get_screen_capture",
    "WindowInfo",
]
