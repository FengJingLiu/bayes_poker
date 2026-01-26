"""OCR 抽象接口定义。

定义 OCR 引擎的统一接口，支持不同的 OCR 后端实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class OCRMode(Enum):
    """OCR 识别模式。"""

    NUMBER = auto()  # 数字识别（筹码、下注量等）
    CARD_RANK = auto()  # 扑克牌点数识别（A, K, Q, J, T, 9-2）
    TEXT = auto()  # 通用文本识别（玩家 ID 等）


@dataclass(frozen=True)
class OCRResult:
    """OCR 识别结果。"""

    text: str  # 识别出的文本
    confidence: float = 1.0  # 置信度 (0.0 ~ 1.0)

    def to_number(self) -> float:
        """将识别结果转换为数字。

        Returns:
            转换后的浮点数，如果无法解析则返回 0.0
        """
        import re

        # 移除逗号和空格
        cleaned = self.text.replace(",", "").replace(" ", "")
        # 提取数字部分
        match = re.search(r"([\d.]+)", cleaned)
        if match:
            try:
                result = match.group(1)
                # 处理末尾的点
                if result.endswith("."):
                    result = result[:-1]
                return float(result) if result else 0.0
            except ValueError:
                return 0.0
        return 0.0

    def to_card_rank(self) -> str:
        """将识别结果转换为扑克牌点数。

        Returns:
            标准化的点数字符串（A, K, Q, J, T, 9-2），无效返回空字符串
        """
        text = self.text.strip().upper()
        # 处理 10 -> T 的转换
        if text == "10":
            return "T"
        # 验证是否为有效点数
        if text in "AKQJT98765432":
            return text
        return ""


class OCREngine(ABC):
    """OCR 引擎抽象基类。"""

    @abstractmethod
    def recognize(self, image: np.ndarray, mode: OCRMode = OCRMode.TEXT) -> OCRResult:
        """识别图像中的文本。

        Args:
            image: OpenCV 格式图像 (BGR)
            mode: 识别模式

        Returns:
            OCR 识别结果
        """
        ...

    def recognize_number(self, image: np.ndarray) -> float:
        """识别数字（便捷方法）。"""
        return self.recognize(image, OCRMode.NUMBER).to_number()

    def recognize_card_rank(self, image: np.ndarray) -> str:
        """识别扑克牌点数（便捷方法）。"""
        return self.recognize(image, OCRMode.CARD_RANK).to_card_rank()

    def recognize_text(self, image: np.ndarray) -> str:
        """识别通用文本（便捷方法）。"""
        return self.recognize(image, OCRMode.TEXT).text
