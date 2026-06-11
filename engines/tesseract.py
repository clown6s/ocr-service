"""Tesseract OCR 引擎 - 轻量经典方案"""

import logging
import pytesseract
from PIL import Image
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TesseractEngine:
    """Tesseract OCR 引擎封装"""

    def recognize(self, image_path: str, lang: str = "chi_sim+eng", **kwargs) -> Dict[str, Any]:
        try:
            img = Image.open(image_path)
        except Exception as e:
            logger.error(f"无法打开图片 {image_path}: {e}")
            raise ValueError(f"无法打开图片: {e}")

        try:
            data = pytesseract.image_to_data(
                img,
                lang=lang,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract 未安装。Windows 请从 "
                "https://github.com/UB-Mannheim/tesseract/wiki 下载安装"
            )
        except Exception as e:
            logger.error(f"Tesseract 识别失败: {e}")
            raise RuntimeError(f"识别失败: {e}")

        lines = []
        full_texts = []
        current_line = ""

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = data["conf"][i]
            line_num = data["line_num"][i]

            if conf == -1:  # 非文字区域
                continue

            if text:
                current_line += (" " if current_line else "") + text

            # 换行检测：下一个是不同行或已到最后
            next_is_new_line = (i + 1 >= len(data["text"]) or
                                data["line_num"][i + 1] != line_num)
            if next_is_new_line and current_line:
                lines.append({
                    "text": current_line,
                    "confidence": round(conf / 100.0, 4),
                    "box": None,
                })
                full_texts.append(current_line)
                current_line = ""

        return {
            "lines": lines,
            "full_text": "\n".join(full_texts),
        }

    def name(self) -> str:
        return "tesseract"
