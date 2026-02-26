# services/cleanup_service.py
import threading
import time
from typing import Optional
from datetime import datetime
from sqlalchemy import delete, select, create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Token
from shared.logger.logger import logger



class TokenCleanupService:
    """
    Сервис для фоновой очистки истекших токенов
    Запуск в отдельном поток синхронный SQLAlchemy
    """
    
    def __init__(
        self,
        database_url: str, 
        interval_minutes: int = 60,
        batch_size: int = 1000,
        name: str = "TokenCleanup"
    ):
        self.database_url = database_url
        self.interval = interval_minutes * 60
        self.batch_size = batch_size
        self.name = name
        # Синхронный engine для фонового потока
        self.sync_engine = None
        self.SyncSessionLocal = None
        # Состояние сервиса
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self._stats = {
            'total_deleted': 0,
            'last_run': None,
            'last_deleted': 0,
            'errors': 0,
            'runs': 0
        }
        self._lock = threading.Lock()
    
    def _init_sync_engine(self):
        """Инициализирует синхронный engine для потока"""
        if self.sync_engine is None:
            # Преобразуем asyncpg в psycopg2 для синхронного подключения
            sync_url = self.database_url.replace('postgresql+asyncpg', 'postgresql')
            self.sync_engine = create_engine(
                sync_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )
            self.SyncSessionLocal = sessionmaker(
                bind=self.sync_engine,
                expire_on_commit=False
            )
            logger.info(f"[{self.name}] Синхронный engine инициализирован")
    
    def _cleanup_batch_sync(self) -> int:
        """Синхронная очистка батча"""
        if not self.SyncSessionLocal:
            self._init_sync_engine()
        session = self.SyncSessionLocal()
        try:
            # Находим ID токенов для удаления
            token_ids = session.execute(
                select(Token.id).where(
                    Token.exp < datetime.utcnow()
                ).limit(self.batch_size)
            ).scalars().all()
            if not token_ids:
                return 0
            result = session.execute(
                delete(Token).where(Token.id.in_(token_ids))
            )
            session.commit()
            return result.rowcount
        except Exception as e:
            session.rollback()
            logger.error(f"[{self.name}] Ошибка в _cleanup_batch_sync: {e}")
            raise
        finally:
            session.close()
    
    def _run_cleanup_loop(self):
        """Основной цикл очистки (выполняется в отдельном потоке)"""
        self._init_sync_engine()
        logger.info(
            f"[{self.name}] 🚀 Поток очистки запущен "
            f"(интервал: {self.interval // 60} мин, поток: {threading.current_thread().name})"
        )
        while self.is_running:
            try:
                start_time = time.time()
                total_deleted = 0
                batches = 0
                logger.info(f"[{self.name}] 🧹 Начинаем очистку...")
                while self.is_running:
                    try:
                        deleted = self._cleanup_batch_sync()
                        if deleted == 0:
                            break
                        total_deleted += deleted
                        batches += 1
                        logger.debug(
                            f"[{self.name}] Удалено {deleted} токенов (батч #{batches})"
                        )
                        time.sleep(0.1)
                    except Exception as e:
                        logger.error(f"[{self.name}] Ошибка при удалении батча: {e}")
                        with self._lock:
                            self._stats['errors'] += 1
                        break
                duration = time.time() - start_time
                with self._lock:
                    self._stats['total_deleted'] += total_deleted
                    self._stats['last_run'] = datetime.utcnow()
                    self._stats['last_deleted'] = total_deleted
                    self._stats['last_batches'] = batches
                    self._stats['runs'] += 1
                
                if total_deleted > 0:
                    logger.info(
                        f"[{self.name}] ✅ Очистка завершена: "
                        f"удалено {total_deleted} токенов за {batches} батчей "
                        f"за {duration:.2f}с"
                    )
                else:
                    logger.info(f"[{self.name}] ✅ Истекших токенов не найдено")
                
            except Exception as e:
                logger.error(f"[{self.name}] ❌ Критическая ошибка в цикле: {e}")
                with self._lock:
                    self._stats['errors'] += 1
            if self.is_running:
                logger.debug(f"[{self.name}] Ожидание {self.interval // 60} мин...")
                for _ in range(self.interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
        if self.sync_engine:
            self.sync_engine.dispose()
            logger.info(f"[{self.name}] Соединения с БД закрыты")
        
        logger.info(f"[{self.name}] 👋 Поток очистки остановлен")
    
    def start(self):
        """Запускает фоновый процесс в отдельном потоке"""
        if self.is_running:
            logger.warning(f"[{self.name}] Сервис уже запущен")
            return
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_cleanup_loop,
            name=self.name,
            daemon=True
        )
        self.thread.start()
        logger.info(
            f"[{self.name}] ✅ Фоновый процесс запущен "
            f"(поток: {self.thread.name}, ID: {self.thread.ident})"
        )
    
    def stop(self):
        """Останавливает фоновый процесс"""
        if not self.is_running:
            logger.warning(f"[{self.name}] Сервис не запущен")
            return
        logger.info(f"[{self.name}] 🛑 Останавливаем фоновый процесс...")
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                logger.warning(f"[{self.name}] Поток не завершился за 10 секунд")
            else:
                logger.info(f"[{self.name}] Поток успешно завершен")
    
    async def get_stats(self) -> dict:
        """Возвращает статистику работы"""
        with self._lock:
            return {
                'name': self.name,
                'is_running': self.is_running,
                'thread_id': self.thread.ident if self.thread else None,
                'interval_minutes': self.interval // 60,
                'batch_size': self.batch_size,
                'stats': self._stats.copy()
            }
    
    def run_once_sync(self) -> dict:
        """Синхронная версия одноразовой очистки"""
        self._init_sync_engine()
        start_time = time.time()
        total_deleted = 0
        batches = 0
        try:
            while True:
                deleted = self._cleanup_batch_sync()
                if deleted == 0:
                    break
                total_deleted += deleted
                batches += 1
                if batches % 10 == 0:
                    logger.info(f"[{self.name}] Прогресс: удалено {total_deleted} токенов")
                time.sleep(0.1)
            
            duration = time.time() - start_time
            return {
                'deleted': total_deleted,
                'batches': batches,
                'duration': duration
            }
        except Exception as e:
            logger.error(f"[{self.name}] Ошибка в run_once_sync: {e}")
            raise