"""引擎工厂（线程安全）"""

import logging
import threading
from engines.base import BaseOCREngine
from engines.paddle import PaddleOCREngine
from engines.tesseract import TesseractEngine

logger = logging.getLogger(__name__)

_engines = {}
_locks = {}  # 每个引擎一个锁，保证并发安全
_factory_lock = threading.Lock()  # 引擎初始化锁


def get_engine(name: str) -> BaseOCREngine:
    """
    获取 OCR 引擎实例（单例，线程安全）
    name: "paddle" 或 "tesseract"
    """
    if name not in _engines:
        with _factory_lock:  # 防止并发初始化同一引擎
            if name not in _engines:
                if name == "paddle":
                    _engines[name] = PaddleOCREngine()
                elif name == "tesseract":
                    _engines[name] = TesseractEngine()
                else:
                    raise ValueError(f"不支持的引擎: {name}，可选: paddle, tesseract")
                _locks[name] = threading.Lock()
                logger.info(f"初始化引擎: {name}")
    
    return _engines[name]


def get_lock(engine_name: str) -> threading.Lock:
    """获取指定引擎的并发锁"""
    return _locks.get(engine_name, threading.Lock())
