"""PaddleOCR 引擎 - 中文效果最好（适配 2.9.x）"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 延迟加载，避免启动时拉模型
_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            # 2.9.x: use_angle_cls 已废弃但兼容
            _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            logger.info("PaddleOCR 模型加载成功")
        except ImportError as e:
            logger.error(f"PaddleOCR 导入失败: {e}")
            raise RuntimeError(
                "PaddleOCR 未安装。请执行: pip install paddlepaddle paddleocr"
            )
    return _ocr_instance


class PaddleOCREngine:
    """PaddleOCR 引擎封装（适配 2.9.x，返回 tuple）"""

    def recognize(self, image_path: str, **kwargs) -> Dict[str, Any]:
        ocr = _get_ocr()

        from PIL import Image
        import numpy as np

        img = Image.open(image_path).convert("RGB")
        img_array = np.array(img)

        # 2.9.x 返回 tuple: (boxes_list, texts_scores_list, meta_dict)
        # result[0]: [[x,y,x,y...], ...]  坐标框
        # result[1]: [("text", confidence), ...]  文本和置信度
        raw = ocr(img_array)

        lines = []
        full_texts = []

        if isinstance(raw, tuple) and len(raw) >= 2:
            boxes = raw[0]
            texts_scores = raw[1]

            for i, ts in enumerate(texts_scores):
                text = ts[0].strip() if ts and len(ts) > 0 else ""
                confidence = float(ts[1]) if ts and len(ts) > 1 else 0.0
                box = boxes[i].tolist() if i < len(boxes) else None

                if text:
                    lines.append({
                        "text": text,
                        "confidence": round(confidence, 4),
                        "box": box,
                    })
                    full_texts.append(text)
        elif isinstance(raw, list) and len(raw) > 0:
            # 兼容旧版本：直接是 list 格式
            items = raw[0]
            for item in items:
                box_coords = item[0]
                text_info = item[1]
                text = text_info[0].strip() if text_info else ""
                confidence = float(text_info[1]) if text_info and len(text_info) > 1 else 0.0

                if text:
                    lines.append({
                        "text": text,
                        "confidence": round(confidence, 4),
                        "box": box_coords,
                    })
                    full_texts.append(text)

        return {
            "lines": lines,
            "full_text": "\n".join(full_texts),
        }

    def name(self) -> str:
        return "paddle"
