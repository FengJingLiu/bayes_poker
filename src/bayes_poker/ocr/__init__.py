"""OCR 模块。

提供基于图像识别的牌桌元素解析功能。
"""

from bayes_poker.ocr.interface import OCREngine, OCRMode, OCRResult
from bayes_poker.ocr.schema import (
    Area,
    AreaColorCheck,
    Color,
    ColorCheckConfig,
    MultiPointColorCheck,
    Point,
    PointColorCheck,
    RelativeArea,
    RelativePoint,
    CARD_SUIT_COLORS,
)

__all__ = [
    "OCREngine",
    "OCRMode",
    "OCRResult",
    "Point",
    "RelativePoint",
    "Area",
    "RelativeArea",
    "Color",
    "ColorCheckConfig",
    "PointColorCheck",
    "MultiPointColorCheck",
    "AreaColorCheck",
    "CARD_SUIT_COLORS",
]
