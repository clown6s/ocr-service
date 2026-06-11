FROM python:3.12-slim

LABEL maintainer="ocr-service"
LABEL description="OCR API Service - PaddleOCR + Tesseract"

# 安装系统依赖（Tesseract）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra \
        libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要目录
RUN mkdir -p uploads outputs && \
    chmod 755 uploads outputs

# 非特权用户
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
