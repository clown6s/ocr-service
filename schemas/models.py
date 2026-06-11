"""Pydantic 请求/响应模型"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class OCREngine(str, Enum):
    paddle = "paddle"
    tesseract = "tesseract"


class OCRRequest(BaseModel):
    engine: OCREngine = OCREngine.paddle
    lang: str = "chi_sim"  # tesseract 用；paddle 忽略


class BatchOCRRequest(BaseModel):
    engine: OCREngine = OCREngine.paddle
    lang: str = "chi_sim"


class OCRLineResult(BaseModel):
    text: str
    confidence: float
    box: Optional[list] = None  # 文字区域坐标 [[x1,y1],[x2,y2],...]
    original_text: Optional[str] = None  # 纠错前的原始文本


class OCRResult(BaseModel):
    filename: str
    engine: str
    lines: list[OCRLineResult]
    full_text: str
    corrections: Optional[list] = None  # 纠错记录列表


class BatchOCRResult(BaseModel):
    total: int
    success: int
    failed: int
    results: list[OCRResult]


class ExportFormat(str, Enum):
    txt = "txt"
    excel = "xlsx"


class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.txt
