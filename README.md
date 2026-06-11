# OCR API Service

图片文字识别服务，支持 **PaddleOCR**（中文效果最佳）和 **Tesseract**（轻量级）双引擎。

## 功能特性

- 单张 / 批量图片识别
- 结果导出：TXT / Excel
- 自动文本纠错（混淆字校正）
- 请求限流 + 并发安全
- 请求追踪 ID 全链路日志
- Docker 一键部署
- Swagger API 文档

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# Windows (PowerShell)
.\venv\Scripts\pip install -r requirements.txt

# Linux / macOS
.venv/bin/pip install -r requirements.txt
```

### 2. Tesseract 引擎（可选）

如需使用 Tesseract 引擎，需额外安装可执行程序和中文语言包。

#### Windows

**下载安装包：**

1. 打开 https://github.com/UB-Mannheim/tesseract/wiki
2. 找到 **Download** 区域 → 下载 `tesseract-ocr-w64-setup-5.x.x.exe`（64 位）
   - 直接下载地址：https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe

**安装时勾选语言包：**

- ☑️ **Chinese (Simplified)** — chi_sim（简体中文）
- ☑️ **Chinese (Traditional)** — chi_tra（繁体中文）
- ☑️ **English**（英文）

**配置环境变量：**

将 Tesseract 安装目录添加到系统 PATH：

```
C:\Program Files\Tesseract-OCR\
```

> Windows 搜索栏输入「环境变量」→ 编辑系统环境变量 → 环境变量(N)... → 系统变量 → Path → 新建

**验证安装：**

```bash
tesseract --version
# 应输出: tesseract 5.x.x
```

> ⚠️ 修改 PATH 后需要**重启终端 / 重启 OCR 服务**才能生效。

#### Linux

```bash
apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra
```

#### macOS

```bash
brew install tesseract tesseract-lang
```

### 3. 启动服务

```bash
cd ocr-service

# 开发模式（热重载）
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

打开 http://localhost:8000/docs 查看 API 文档并在线测试。

### 4. Docker 部署

```bash
docker-compose up -d --build
```

访问 http://localhost:8000/health 检查健康状态。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/ocr/recognize` | 单张图片识别 |
| POST | `/api/v1/ocr/batch` | 批量识别（最多50张） |
| POST | `/api/v1/ocr/export` | 批量识别 + 导出文件下载 |
| GET | `/api/v1/ocr/engines` | 查看引擎状态 |
| GET | `/health` | 健康检查 |

### 通用参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| engine | string | `paddle` | 引擎选择: `paddle` / `tesseract` |
| lang | string | `chi_sim` | 语言（Tesseract 用） |
| correct | bool | `true` | 是否启用自动纠错 |

### 响应示例

```json
{
  "success": true,
  "data": {
    "filename": "photo.jpg",
    "engine": "paddle",
    "lines": [
      { "text": "识别出的文字", "confidence": 0.9868, "box": [...] }
    ],
    "full_text": "完整文本\n拼接结果",
    "corrections": [
      { "original": "怀态", "corrected": "怀念", "reason": "phrase_fix" }
    ]
  },
  "request_id": "a3f2b1c4"
}
```

## 配置说明

优先级：**环境变量 > config.yaml > 默认值**

### config.yaml

```yaml
server:
  port: 8000
  debug: false

ocr:
  default_engine: paddle
  enable_correction: true

upload:
  max_file_size_mb: 20
  max_batch_files: 50

rate_limit:
  enabled: true
  requests_per_minute: 30
  requests_per_hour: 300

log:
  level: INFO
```

### 环境变量

```bash
# 服务配置
SERVER_PORT=8000
DEBUG=false

# OCR 配置
OCR_DEFAULT_ENGINE=paddle
RATE_LIMIT_RPM=30
LOG_LEVEL=INFO

# 上传限制
UPLOAD_MAX_SIZE_MB=20
UPLOAD_MAX_FILES=50
```

## 项目结构

```
ocr-service/
├── main.py              # 应用入口（中间件/限流/健康检查）
├── config.py            # 配置管理
├── config.yaml          # 默认配置
├── .env                 # 环境变量模板（不提交）
├── middleware.py         # 请求追踪 + 统一错误处理
├── Dockerfile           # Docker 镜像构建
├── docker-compose.yml   # 容器编排
├── engines/
│   ├── __init__.py      # 线程安全的引擎工厂
│   ├── base.py          # 抽象基类
│   ├── paddle.py        # PaddleOCR 引擎
│   └── tesseract.py     # Tesseract 引擎
├── routers/
│   └── ocr.py           # API 路由
├── schemas/
│   └── models.py        # Pydantic 数据模型
├── utils/
│   ├── correction.py    # 文本纠错模块
│   └── exporter.py      # TXT/Excel 导出
├── uploads/             # 上传临时目录
├── outputs/             # 导出文件目录
├── tests/               # 测试用例
└── requirements.txt     # Python 依赖
```

## PaddleOCR 注意事项

- 首次调用会**自动下载模型**（约几百MB），之后缓存本地
- PaddleOCR **非线程安全**，项目已通过 threading.Lock 保证并发安全
- 返回格式为 tuple `(boxes, texts_scores, meta_dict)`，必须传入 numpy 数组

## 性能参考

| 引擎 | 首次加载 | 后续调用 | 中文准确率 |
|------|---------|---------|-----------|
| PaddleOCR | ~60s（下载模型） | ~0.5s/张 | 高（推荐） |
| Tesseract | 即时 | ~0.1s/张 | 中 |

## License

MIT
