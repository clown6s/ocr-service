"""OCR 引擎抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseOCREngine(ABC):
    """所有 OCR 引擎的基类"""

    @abstractmethod
    def recognize(self, image_path: str, **kwargs) -> Dict[str, Any]:
        """
        识别单张图片
        返回: {
            "lines": [{"text": str, "confidence": float, "box": list}],
            "full_text": str
        }
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass
