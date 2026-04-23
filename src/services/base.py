from abc import ABC
from sqlalchemy.ext.asyncio import AsyncSession
from weakref import WeakKeyDictionary

class BaseService(ABC):
    def __init__(self, session : AsyncSession, **kwargs):
        self._session = session
        self._depends_cache = WeakKeyDictionary()

    def _clear_cache(self):
        """Очистить кэш репозиториев"""
        self._depends_cache.clear()

    def _cache(self, depends_ref, *args):
        """Добавить в кеш зависимость"""
        if not callable(depends_ref):
            raise TypeError(f"{depends_ref} must be callable (class or function)")
        self._depends_cache[depends_ref] = depends_ref(*args)

    def _get_depends(self, depends_ref, *args):
        """Универсальный метод получения репозитория"""
        if depends_ref not in self._depends_cache:
            self._cache(depends_ref, *args)
        return self._depends_cache[depends_ref]


