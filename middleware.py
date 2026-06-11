"""统一错误处理 + 请求追踪中间件"""

import logging
import time
import uuid
import traceback

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求追踪 ID 中间件"""

    async def dispatch(self, request: Request, call_next):
        # 生成/传递请求 ID
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = (time.time() - start_time) * 1000  # ms
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.1f}ms"
        
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.0f}ms)"
        )
        
        return response


def setup_error_handlers(app: FastAPI):
    """注册全局错误处理"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"[{request_id}] HTTP {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                },
                "request_id": request_id,
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown")
        errors = []
        for err in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            })
        logger.warning(f"[{request_id}] 参数校验失败: {errors}")
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "参数校验失败",
                    "details": errors,
                },
                "request_id": request_id,
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"[{request_id}] 未处理的异常: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误，请稍后重试",
                },
                "request_id": request_id,
            }
        )


# 需要在这里 import，避免循环依赖
from starlette.responses import JSONResponse
