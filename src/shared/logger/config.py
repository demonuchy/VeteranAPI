# настройки логирования
import os
from pathlib import Path

# Базовые настройки логирования
LOGGING_CONFIG = {
    "name": "app",
    "level": "DEBUG",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "log_to_file": True,
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

def update_logging_config(**kwargs):
    """Обновление конфигурации логирования"""
    global LOGGING_CONFIG
    LOGGING_CONFIG.update(kwargs)
    
    from logger import AppLogger
    AppLogger._initialized = False
    AppLogger.setup_logger(**LOGGING_CONFIG)