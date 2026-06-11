"""OCR API 服务 - 生产级（支持双引擎 + 限流 + 纠错）"""

import logging
import os
import shutil

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from config import load_config, get_config
from routers import ocr
from middleware import RequestIDMiddleware, setup_error_handlers

# ── 1. 加载配置 ────────────────────────
cfg = load_config()

# ── 2. 配置日志 ────────────────────────
log_cfg = cfg.log
logging.basicConfig(
    level=getattr(logging, log_cfg.level.upper(), logging.INFO),
    format=log_cfg.format,
)
logger = logging.getLogger(__name__)

# ── 3. 创建应用 ────────────────────────
app = FastAPI(
    title="OCR API Service",
    description="图片文字识别服务，支持 PaddleOCR 和 Tesseract 双引擎",
    version="1.0.0",
)

# 请求追踪 ID 中间件
app.add_middleware(RequestIDMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.server.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一错误处理
setup_error_handlers(app)

# 路由注册（限流在路由层处理）
app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["OCR"])

# ── 4. 请求限流 ────────────────────────
if cfg.rate_limit.enabled:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[
            f"{cfg.rate_limit.requests_per_minute}/minute",
            f"{cfg.rate_limit.requests_per_hour}/hour",
        ],
        storage_uri="memory://",
        enabled=cfg.rate_limit.enabled,
    )
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"[{request_id}] 触发限流: {exc.detail}")
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"请求过于频繁，请稍后重试。{exc.detail}",
                },
                "request_id": request_id,
            }
        )

else:
    # 限流关闭时提供一个空 limiter（路由装饰器不会报错）
    from contextlib import contextmanager

    class NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    limiter = NoOpLimiter()

# 需要在这里 import，避免循环依赖
from starlette.responses import JSONResponse


# ── 5. 健康检查（增强版）─────────────────
@app.get("/health", summary="健康检查")
async def health_check():
    """检查服务状态、引擎可用性、磁盘空间"""
    from datetime import datetime
    
    checks = {
        "status": "ok",
        "service": "ocr-api",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
    }
    
    # 磁盘空间检查
    try:
        total, used, free = shutil.disk_usage(cfg.base_dir)
        free_gb = free / (1024**3)
        disk_ok = free_gb > 0.5  # 至少剩 500MB
        checks["checks"]["disk_space"] = {
            "status": "pass" if disk_ok else "fail",
            "free_gb": round(free_gb, 2),
            "total_gb": round(total / (1024**3), 2),
            "used_percent": round(used / total * 100, 1),
        }
    except Exception as e:
        checks["checks"]["disk_space"] = {"status": "error", "detail": str(e)}
    
    # 引擎状态检查
    engines_status = []
    
    # PaddleOCR
    paddle = {"name": "paddle", "status": "unknown"}
    try:
        import paddleocr
        paddle["version"] = paddleocr.__version__
        
        # 检查模型是否已加载（不触发加载）
        from engines.paddle import _ocr_instance
        if _ocr_instance is not None:
            paddle["model_loaded"] = True
            paddle["status"] = "ready"
        else:
            paddle["model_loaded"] = False
            paddle["status"] = "not_initialized"
    except ImportError:
        paddle["status"] = "not_installed"
    except Exception as e:
        paddle["status"] = "error"
        paddle["detail"] = str(e)
    engines_status.append(paddle)
    
    # Tesseract
    tess = {"name": "tesseract", "status": "unknown"}
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        tess["version"] = str(version)
        tess["status"] = "ready"
    except ImportError:
        tess["status"] = "not_installed"
    except Exception as e:
        tess["status"] = "error"
        tess["detail"] = str(e)
    engines_status.append(tess)
    
    checks["checks"]["engines"] = engines_status
    
    # 上传/输出目录检查
    for name, path in [("uploads", cfg.upload_dir), ("outputs", cfg.output_dir)]:
        exists = path.exists() and path.is_dir()
        checks["checks"][f"dir_{name}"] = {
            "status": "pass" if exists else "fail",
            "path": str(path),
        }
    
    return checks


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    # 确保目录存在
    cfg.upload_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"OCR API 启动 | 引擎={cfg.ocr.default_engine} | "
                f"限流={'开启' if cfg.rate_limit.enabled else '关闭'} "
                f"({cfg.rate_limit.requests_per_minute}/min) | "
                f"纠错={'开启' if cfg.ocr.enable_correction else '关闭'}")
