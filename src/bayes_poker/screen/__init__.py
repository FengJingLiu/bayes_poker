"""屏幕截图和窗口管理模块。"""

from bayes_poker.screen.capture import (
    MockScreenCapture,
    ScreenCapture,
    Win32ScreenCapture,
    get_screen_capture,
)
from bayes_poker.screen.window import (
    GG_POKER_WINDOW_CLASS,
    TrackedWindow,
    WindowDiscovery,
    WindowInfo,
    WindowManager,
)

__all__ = [
    "ScreenCapture",
    "Win32ScreenCapture",
    "MockScreenCapture",
    "get_screen_capture",
    "WindowInfo",
    "TrackedWindow",
    "WindowDiscovery",
    "WindowManager",
    "GG_POKER_WINDOW_CLASS",
]
