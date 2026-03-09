# Логгер
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Создаем папку для логов если её нет
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Формат логов
LOG_FORMAT = "%(levelname)s: %(asctime)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class AppLogger:
    _initialized = False
    
    @classmethod
    def setup_logger(cls, 
                    name: str = "app",
                    level: str = "DEBUG",
                    log_to_file: bool = True,
                    max_file_size: int = 10 * 1024 * 1024,  # 10MB
                    backup_count: int = 5):
        """
        Настройка логгера
        
        Args:
            name: Имя логгера
            level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Записывать ли в файл
            max_file_size: Максимальный размер файла лога
            backup_count: Количество backup файлов
        """
        if cls._initialized:
            return logging.getLogger(name)
            
        logger = logging.getLogger(name)
        
        # Устанавливаем уровень
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(log_level)
        
        # Очищаем существующие handlers
        logger.handlers.clear()
        
        # Форматтер
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler (если включено)
        if log_to_file:
            log_file = LOG_DIR / f"{name}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        # Предотвращаем дублирование логов
        logger.propagate = False
        
        cls._initialized = True
        return logger
    
    @classmethod
    def get_logger(cls, name: str = None):
        """
        Получить логгер по имени модуля
        
        Args:
            name: Имя модуля (обычно __name__)
        """
        if not cls._initialized:
            cls.setup_logger()
        
        if name is None:
            return logging.getLogger("app")
        
        # Извлекаем имя модуля из пути
        module_name = name.split('.')[-1] if '.' in name else name
        return logging.getLogger(f"app.{module_name}")

# Создаем глобальный логгер по умолчанию
def setup_default_logger():
    """Настройка логгера по умолчанию при импорте"""
    return AppLogger.setup_logger()

def get_logger(name: str = None):
    """
    Функция для удобного импорта логгера в любом модуле
    
    Usage:
        from app.cors.logger import get_logger
        logger = get_logger(__name__)
    """
    return AppLogger.get_logger(name)

# Автоматическая настройка при импорте
setup_default_logger()

# Экспортируем основные методы logging для удобства
info = get_logger().info
warning = get_logger().warning
error = get_logger().error
debug = get_logger().debug
critical = get_logger().critical

logger = get_logger(__name__)