"""应用配置管理"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ServerConfig:
    """服务配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class OCRConfig:
    """OCR 引擎配置"""
    default_engine: str = "paddle"  # paddle | tesseract
    tesseract_lang: str = "chi_sim"
    paddle_lang: str = "ch"
    enable_correction: bool = True  # 是否默认开启文本纠错


@dataclass
class UploadConfig:
    """上传配置"""
    max_file_size_mb: int = 20  # 单文件最大 MB
    max_batch_files: int = 50   # 批量最大文件数
    allowed_extensions: list = field(default_factory=lambda: [
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"
    ])


@dataclass
class RateLimitConfig:
    """限流配置"""
    enabled: bool = True
    requests_per_minute: int = 30  # 每分钟最大请求数
    requests_per_hour: int = 300   # 每小时最大请求数


@dataclass
class LogConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
    json_format: bool = False  # 是否使用 JSON 格式日志（适合生产环境）


@dataclass
class AppConfig:
    """全局配置"""
    server: ServerConfig = field(default_factory=ServerConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    upload: UploadConfig = field(default_factory=UploadConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    log: LogConfig = field(default_factory=LogConfig)

    # 运行时路径（根据项目根目录自动计算）
    _base_dir: Optional[Path] = None

    @property
    def base_dir(self) -> Path:
        if self._base_dir is None:
            # 自动检测：从当前文件往上找
            self._base_dir = Path(__file__).parent.resolve()
        return self._base_dir

    @property
    def upload_dir(self) -> Path:
        return self.base_dir / "uploads"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "outputs"


# 全局单例
_config: Optional[AppConfig] = None


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    加载配置，优先级：环境变量 > config.yaml > 默认值
    
    Args:
        config_path: 配置文件路径，默认为项目根目录下的 config.yaml
    """
    global _config

    cfg = AppConfig()

    # 1. 尝试加载 YAML 配置文件
    if config_path is None:
        config_path = os.environ.get("OCR_CONFIG_PATH")
    
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
        
        # 合并 server 配置
        if "server" in yaml_data:
            for k, v in yaml_data["server"].items():
                if hasattr(cfg.server, k):
                    setattr(cfg.server, k, v)
        
        # 合并 ocr 配置
        if "ocr" in yaml_data:
            for k, v in yaml_data["ocr"].items():
                if hasattr(cfg.ocr, k):
                    setattr(cfg.ocr, k, v)
        
        # 合并 upload 配置
        if "upload" in yaml_data:
            for k, v in yaml_data["upload"].items():
                if hasattr(cfg.upload, k):
                    setattr(cfg.upload, k, v)
        
        # 合并 rate_limit 配置
        if "rate_limit" in yaml_data:
            for k, v in yaml_data["rate_limit"].items():
                if hasattr(cfg.rate_limit, k):
                    setattr(cfg.rate_limit, k, v)
        
        # 合并 log 配置
        if "log" in yaml_data:
            for k, v in yaml_data["log"].items():
                if hasattr(cfg.log, k):
                    setattr(cfg.log, k, v)

    # 2. 环境变量覆盖（最高优先级）
    env_mappings = {
        ("SERVER_HOST", "host", "server"),
        ("SERVER_PORT", "port", "server"),
        ("DEBUG", "debug", "server"),
        ("OCR_DEFAULT_ENGINE", "default_engine", "ocr"),
        ("RATE_LIMIT_RPM", "requests_per_minute", "rate_limit"),
        ("RATE_LIMIT_RPH", "requests_per_hour", "rate_limit"),
        ("LOG_LEVEL", "level", "log"),
        ("UPLOAD_MAX_SIZE_MB", "max_file_size_mb", "upload"),
        ("UPLOAD_MAX_FILES", "max_batch_files", "upload"),
    }

    for env_key, attr_name, section in env_mappings:
        val = os.environ.get(env_key)
        if val is not None:
            section_obj = getattr(cfg, section)
            current_val = getattr(section_obj, attr_name)
            # 类型转换
            if isinstance(current_val, bool):
                val = val.lower() in ("1", "true", "yes", "on")
            elif isinstance(current_val, int):
                val = int(val)
            elif isinstance(current_val, float):
                val = float(val)
            setattr(section_obj, attr_name, val)

    _config = cfg
    return cfg


def get_config() -> AppConfig:
    """获取全局配置实例（必须先调用 load_config）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
