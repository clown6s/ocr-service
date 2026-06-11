"""OCR API 路由"""

import os
import shutil
import uuid
import logging
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse

from schemas.models import (
    OCREngine, OCRRequest, BatchOCRRequest,
    OCRResult, OCRLineResult, BatchOCRResult,
    ExportFormat, ExportRequest,
)
from engines import get_engine, get_lock
from utils.exporter import export_results
from utils.correction import apply_corrections
from config import get_config

router = APIRouter()

cfg = get_config()
UPLOAD_DIR = cfg.upload_dir
OUTPUT_DIR = cfg.output_dir
logger = logging.getLogger(__name__)

# 限流器（从 main.py 获取，如果未配置则用空装饰器）
try:
    from main import limiter as app_limiter
except (ImportError, AttributeError):
    class _NoOpLimiter:
        def limit(self, *a, **kw):
            return lambda f: f
    app_limiter = _NoOpLimiter()


def _save_upload(file: UploadFile) -> str:
    """保存上传文件并返回路径"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    # 文件大小校验
    file.file.seek(0, 2)  # 移到末尾
    size_bytes = file.file.tell()
    file.file.seek(0)      # 回到开头
    
    max_size = cfg.upload.max_file_size_mb * 1024 * 1024
    if size_bytes > max_size:
        raise HTTPException(
            413,
            f"文件过大: {size_bytes / (1024*1024):.1f}MB，最大限制 {cfg.upload.max_file_size_mb}MB"
        )

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return path


@app_limiter.limit("10/minute")
@router.post("/recognize", response_model=OCRResult, summary="单张图片识别")
async def recognize_image(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    engine: OCREngine = Query(cfg.ocr.default_engine, description="OCR引擎"),
    lang: str = Query(None, description="语言(tesseract用)"),
    correct: bool = Query(cfg.ocr.enable_correction, description="是否启用自动纠错"),
):
    """上传单张图片进行文字识别"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # 校验文件类型
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in cfg.upload.allowed_extensions:
        raise HTTPException(
            400,
            f"不支持的文件类型: {ext}，允许: {cfg.upload.allowed_extensions}"
        )

    path = _save_upload(file)
    ocr_lock = get_lock(engine.value)
    
    try:
        # 加锁保证并发安全（PaddleOCR 非线程安全）
        with ocr_lock:
            ocr_engine = get_engine(engine.value)
            result = ocr_engine.recognize(
                path,
                lang=lang or cfg.ocr.tesseract_lang if engine.value == "tesseract" else None
            )

        # 应用文本纠错
        if correct:
            result = apply_corrections(result)

        logger.info(f"[{request_id}] 识别完成: {file.filename}, "
                     f"引擎={engine.value}, 行数={len(result['lines'])}, "
                     f"纠正={len(result.get('corrections', []))}")

        return OCRResult(
            filename=file.filename or "unknown",
            engine=engine.value,
            lines=[OCRLineResult(**line) for line in result["lines"]],
            full_text=result["full_text"],
            corrections=result.get("corrections"),
        )
    except Exception as e:
        logger.error(f"[{request_id}] 识别失败: {e}", exc_info=True)
        raise HTTPException(500, f"识别失败: {str(e)}")
    finally:
        if os.path.exists(path):
            os.remove(path)


@app_limiter.limit("20/minute")
@router.post("/batch", response_model=BatchOCRResult, summary="批量识别")
async def batch_recognize(
    request: Request,
    files: List[UploadFile] = File(..., description="多张图片"),
    engine: OCREngine = Query(cfg.ocr.default_engine, description="OCR引擎"),
    lang: str = Query(None, description="语言(tesseract用)"),
    correct: bool = Query(cfg.ocr.enable_correction, description="是否启用自动纠错"),
):
    """批量上传多张图片进行文字识别"""
    request_id = getattr(request.state, "request_id", "unknown")

    if len(files) > cfg.upload.max_batch_files:
        raise HTTPException(
            400,
            f"单次最多上传 {cfg.upload.max_batch_files} 张图片"
        )

    ocr_lock = get_lock(engine.value)
    ocr_engine = get_engine(engine.value)
    results = []
    success = 0
    failed = 0

    saved_paths = []
    for file in files:
        path = _save_upload(file)
        saved_paths.append((path, file.filename))

    try:
        for path, filename in saved_paths:
            try:
                with ocr_lock:
                    result = ocr_engine.recognize(
                        path,
                        lang=lang or cfg.ocr.tesseract_lang if engine.value == "tesseract" else None
                    )
                
                if correct:
                    result = apply_corrections(result)
                    
                results.append(OCRResult(
                    filename=filename or "unknown",
                    engine=engine.value,
                    lines=[OCRLineResult(**line) for line in result["lines"]],
                    full_text=result["full_text"],
                    corrections=result.get("corrections"),
                ))
                success += 1
            except Exception as e:
                logger.error(f"[{request_id}] {filename} 识别失败: {e}")
                failed += 1
        
        logger.info(f"[{request_id}] 批量识别完成: 总计={len(files)}, 成功={success}, 失败={failed}")
    finally:
        for path, _ in saved_paths:
            if os.path.exists(path):
                os.remove(path)

    return BatchOCRResult(
        total=len(files),
        success=success,
        failed=failed,
        results=results,
    )


@app_limiter.limit("20/minute")
@router.post("/export", summary="批量识别并导出结果")
async def recognize_and_export(
    request: Request,
    files: List[UploadFile] = File(..., description="多张图片"),
    engine: OCREngine = Query(cfg.ocr.default_engine, description="OCR引擎"),
    fmt: ExportFormat = Query(ExportFormat.txt, description="导出格式"),
    lang: str = Query(None, description="语言"),
):
    """批量识别后直接下载结果文件（TXT / Excel）"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    ocr_lock = get_lock(engine.value)
    ocr_engine = get_engine(engine.value)
    results = []
    saved_paths = []

    for file in files:
        path = _save_upload(file)
        saved_paths.append((path, file.filename))

    try:
        for path, filename in saved_paths:
            try:
                with ocr_lock:
                    result = ocr_engine.recognize(
                        path,
                        lang=lang or cfg.ocr.tesseract_lang if engine.value == "tesseract" else None
                    )
                results.append({
                    "filename": filename or "unknown",
                    "engine": engine.value,
                    "lines": result["lines"],
                    "full_text": result["full_text"],
                })
            except Exception as e:
                logger.error(f"[{request_id}] {filename} 识别失败: {e}")
                results.append({
                    "filename": filename or "unknown",
                    "engine": engine.value,
                    "lines": [],
                    "full_text": f"[识别失败: {e}]",
                })
            finally:
                if os.path.exists(path):
                    os.remove(path)

        export_path = await export_results(results, fmt.value, OUTPUT_DIR)
        
        logger.info(f"[{request_id}] 导出完成: {os.path.basename(export_path)}, 格式={fmt.value}")
        
        return FileResponse(
            export_path,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if fmt == ExportFormat.xlsx else "text/plain"
            ),
            filename=os.path.basename(export_path),
        )
    except Exception as e:
        logger.error(f"[{request_id}] 导出失败: {e}", exc_info=True)
        raise HTTPException(500, f"导出失败: {e}")


@router.get("/engines", summary="可用引擎列表")
async def list_engines():
    """列出当前可用的 OCR 引擎及状态"""
    info = []
    
    # PaddleOCR
    paddle_ok = False
    paddle_detail = ""
    try:
        import paddleocr
        paddle_ok = True
        paddle_detail = f"PaddleOCR {paddleocr.__version__}"
    except ImportError:
        paddle_detail = "未安装 (pip install paddlepaddle paddleocr)"
    except Exception as e:
        paddle_detail = f"异常: {str(e)}"
    
    info.append({
        "name": "paddle",
        "description": "PaddleOCR - 中文识别效果好",
        "installed": paddle_ok,
        "detail": paddle_detail,
    })

    # Tesseract
    tess_ok = False
    tess_detail = ""
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        tess_ok = True
        tess_detail = f"Tesseract {version}"
    except ImportError:
        tess_detail = "未安装 (pip install pytesseract)"
    except Exception as e:
        tess_detail = f"异常: {str(e)}"
    
    info.append({
        "name": "tesseract",
        "description": "Tesseract - 轻量级方案",
        "installed": tess_ok,
        "detail": tess_detail,
    })

    return {"engines": info}
