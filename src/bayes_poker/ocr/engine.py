"""OCR 引擎实现。

基于 CnOcr 的 OCR 引擎实现，针对扑克牌桌元素优化。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bayes_poker.ocr.interface import OCREngine, OCRMode, OCRResult

if TYPE_CHECKING:
    import numpy as np

LOGGER = logging.getLogger(__name__)


class CnOcrEngine(OCREngine):
    """基于 CnOcr 的 OCR 引擎。

    针对不同识别场景使用不同的字符候选集，提高识别准确率。
    """

    # 字符候选集
    _ALPHABET_NUMBER = r"1234567890.,B"  # 数字 + BB 后缀
    _ALPHABET_CARD = r"1234567890JQKA"  # 扑克牌点数

    def __init__(
        self,
        context: str = "cpu",
        model_name: str = "doc-densenet_lite_136-gru",
        det_model_name: str = "naive_det",
    ) -> None:
        """初始化 OCR 引擎。

        Args:
            context: 运行设备 ("cpu" 或 "gpu")
            model_name: 识别模型名称
            det_model_name: 检测模型名称
        """
        self._context = context
        self._model_name = model_name
        self._det_model_name = det_model_name

        # 延迟初始化 OCR 实例 (Any 类型因为 CnOcr 是运行时动态导入)
        self._ocr_number = None
        self._ocr_card = None
        self._ocr_text = None

    def _get_ocr_number(self):
        """获取数字 OCR 实例（延迟初始化）。"""
        if self._ocr_number is None:
            try:
                from cnocr import CnOcr  # type: ignore[import-not-found]
            except ImportError as e:
                raise ImportError("需要安装 cnocr: uv add cnocr") from e

            self._ocr_number = CnOcr(
                self._model_name,
                det_model_name=self._det_model_name,
                rec_model_backend="pytorch",
                context=self._context,
                cand_alphabet=self._ALPHABET_NUMBER,
            )
        return self._ocr_number

    def _get_ocr_card(self):
        """获取扑克牌点数 OCR 实例（延迟初始化）。"""
        if self._ocr_card is None:
            try:
                from cnocr import CnOcr  # type: ignore[import-not-found]
            except ImportError as e:
                raise ImportError("需要安装 cnocr: uv add cnocr") from e

            self._ocr_card = CnOcr(
                self._model_name,
                det_model_name=self._det_model_name,
                rec_model_backend="pytorch",
                context=self._context,
                cand_alphabet=self._ALPHABET_CARD,
            )
        return self._ocr_card

    def _get_ocr_text(self):
        """获取通用文本 OCR 实例（延迟初始化）。"""
        if self._ocr_text is None:
            try:
                from cnocr import CnOcr  # type: ignore[import-not-found]
            except ImportError as e:
                raise ImportError("需要安装 cnocr: uv add cnocr") from e

            self._ocr_text = CnOcr(
                self._model_name,
                det_model_name=self._det_model_name,
                rec_model_backend="pytorch",
                context=self._context,
            )
        return self._ocr_text

    def recognize(self, image: np.ndarray, mode: OCRMode = OCRMode.TEXT) -> OCRResult:
        """识别图像中的文本。

        Args:
            image: OpenCV 格式图像 (BGR)
            mode: 识别模式

        Returns:
            OCR 识别结果
        """
        match mode:
            case OCRMode.NUMBER:
                ocr = self._get_ocr_number()
            case OCRMode.CARD_RANK:
                ocr = self._get_ocr_card()
            case OCRMode.TEXT:
                ocr = self._get_ocr_text()
            case _:
                ocr = self._get_ocr_text()

        try:
            result = ocr.ocr_for_single_line(image)
            text = result.get("text", "")
            score = result.get("score", 1.0)
            return OCRResult(text=text, confidence=score)
        except Exception as e:
            LOGGER.warning("OCR 识别失败: %s", e)
            return OCRResult(text="", confidence=0.0)


# 全局单例（延迟初始化）
_default_engines: dict[str, CnOcrEngine] = {}


def get_ocr_engine(context: str = "cpu") -> CnOcrEngine:
    """获取默认 OCR 引擎实例。

    Args:
        context: 运行设备 ("cpu" 或 "gpu")

    Returns:
        CnOcrEngine 实例
    """
    engine = _default_engines.get(context)
    if engine is None:
        engine = CnOcrEngine(context=context)
        _default_engines[context] = engine
    return engine
