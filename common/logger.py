"""统一日志模块 — 打字对战平台
提供 setup_logger 和 get_logger 函数
使用 RotatingFileHandler，支持按日期命名和文件轮转
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

_loggers = {}


def get_app_base_dir():
    """获取应用所在目录，处理 PyInstaller 打包情况"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，使用 sys.executable 的目录作为 base
        # 用于存放日志文件
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 开发环境，使用 __file__ 的上级目录（即项目根目录）
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logger(name, log_file_base, logs_dir="logs"):
    """初始化并配置 logger

    Args:
        name: logger 名称
        log_file_base: 日志文件名前缀（不含日期和扩展名）
        logs_dir: 日志目录（相对于应用目录）

    Returns:
        logger: 配置好的 logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    base_dir = get_app_base_dir()
    logs_path = os.path.join(base_dir, logs_dir)

    try:
        os.makedirs(logs_path, exist_ok=True)
    except Exception:
        logs_path = base_dir

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(logs_path, f"{log_file_base}_{date_str}.log")

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # 文件 handler (使用 RotatingFileHandler)
    fh = RotatingFileHandler(
        log_file,
        encoding="utf-8",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    _loggers[name] = logger
    logger.info(f"Logger initialized, logs will go to: {log_file}")

    return logger


def get_logger(name):
    """获取已配置的 logger 实例

    Args:
        name: logger 名称

    Returns:
        logger: logger 实例，如未配置则返回 default logger
    """
    if name not in _loggers:
        return logging.getLogger(name)
    return _loggers[name]
