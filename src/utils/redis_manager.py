import json
import abc
from datetime import datetime, timedelta
from typing import AsyncGenerator, List
from contextlib import asynccontextmanager
import redis.asyncio as redis 

from shared.config import config as cfg
from shared.logger.logger import logger

class AbstractRedisManager(abc.ABC):
    def __init__(
            self, 
            host : str, 
            password : str, 
            max_connections : int, 
            db: int 
            ):
        self._pool = redis.ConnectionPool(
            host=host,
            password=password, 
            db=db,
            max_connections=max_connections,  
            decode_responses=True
            )
        
    @property
    def pool(self):
        return self._pool

    @abc.abstractmethod  
    @asynccontextmanager
    async def redis_session(self) -> AsyncGenerator[redis.Redis, None]:
        """
        Асинхронный контекстный менеджер для Redis сессии.
        
        Берет соединение из пула, выполняет операции, возвращает в пул.
        
        Пример:
            async with redis_session(db=0) as client:
                await client.set('key', 'value')
                result = await client.get('key')
        """
        pass
      
    @abc.abstractmethod
    async def save_with_ttl(self, key : str, value : dict, ttl : int) -> None:
        """
        Сохранение значения
        Args:
            key : ключ 
            value : значение
            ttl : время жизни записи
        Returns:
            None
        """
        pass

    @abc.abstractmethod
    async def delete(self, *key : str) -> None:
        """
        Удаление значения 
        Args:
            key : ключ 
        Returns:
            None
        """
        pass
    
    @abc.abstractmethod
    async def get(self, key) -> dict | None:
        """
        Получение значения
        Args:
            key : ключ 
        Returns:
            value че сохранил то и получил
        """
        pass
    
    @abc.abstractmethod
    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Получение всех ключей, соответствующих паттерну
        Args:
            pattern: паттерн поиска (например "18:*" или "*:device123")
        Returns:
            List[str]: список ключей
        """
        pass
    
    @abc.abstractmethod
    async def get_values_by_pattern(self, pattern: str) -> List[dict]:
        """
        Получение всех значений, соответствующих паттерну
        Args:
            pattern: паттерн поиска (например "18:*")
        Returns:
            List[dict]: список значений
        """
        pass
    
    @abc.abstractmethod
    async def delete_by_pattern(self, pattern: str) -> int:
        """
        Удаление всех ключей, соответствующих паттерну
        Args:
            pattern: паттерн поиска (например "18:*")
        Returns:
            int: количество удаленных ключей
        """
        pass
       

class RedisManager(AbstractRedisManager):
    def __init__(
            self, 
            host : str, 
            password : str, 
            max_connections : int, 
            db: int 
            ):
        super().__init__(
            host, 
            password, 
            max_connections, 
            db
            )
    
    @asynccontextmanager
    async def redis_session(self) -> AsyncGenerator[redis.Redis, None]:
        client = redis.Redis(connection_pool=self.pool)
        try:
            logger.debug(f"Redis session started")
            yield client
        except Exception as e:
            logger.error(f"Redis session error: {e}")
            raise
        finally:
            logger.debug(f"Redis session ended")

    async def save_with_ttl(self, key : str, value : dict, ttl : timedelta) -> None:
        async with self.redis_session() as client:
            serializable_payload = {}
            for k, v in value.items():
                if isinstance(v, datetime):
                    serializable_payload[k] = v.isoformat()  
                else:
                    serializable_payload[k] = v
            value_json = json.dumps(serializable_payload)
            await client.setex(name=key, time=ttl, value=value_json)
            logger.debug(f"saved to Redis: {key}, TTL: {ttl}s")

    async def delete(self, *key : str) -> None:
        async with self.redis_session() as client:
            result = await client.delete(*key)
            logger.debug(f"delete to Redis")

    async def get(self, key) -> dict | None:
        async with self.redis_session() as client:
            value_json = await client.get(key)
            if value_json is None:
                logger.debug(f"Value not found in Redis: {key}")
                return None
            value_dict = json.loads(value_json)
            logger.debug(f"Value retrieved from Redis: {key}")
            return value_dict
    
    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        async with self.redis_session() as client:
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            logger.debug(f"Found {len(keys)} keys matching pattern: {pattern}")
            return keys
    
    async def get_values_by_pattern(self, pattern: str) -> List[dict]:
        keys = await self.get_keys_by_pattern(pattern)
        values = []
        for key in keys:
            value = await self.get(key)
            if value:
                values.append(value)
        logger.debug(f"Retrieved {len(values)} values for pattern: {pattern}")
        return values
    
    async def delete_by_pattern(self, pattern: str) -> int:
        keys = await self.get_keys_by_pattern(pattern)
        if keys:
            async with self.redis_session() as client:
                deleted = await client.delete(*keys)
                logger.debug(f"Deleted {deleted} keys matching pattern: {pattern}")
                return deleted
        return 0


redis_manager = RedisManager(
    host=cfg.RedisHost, 
    password=cfg.REDIS_PASS, 
    max_connections=10,
    db=0
    )