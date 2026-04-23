from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError, ConnectionError as ESConnectionError
from pydantic import BaseModel
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import asyncio

from shared.logger.logger import logger
from schemas.news import NewsSchema
from shared.config import config


T = TypeVar('T', bound=BaseModel)


class AbstractElasticsearchManager(ABC, Generic[T]):
    def __init__(self, url: str = config.ElasticsearchUrl, index_name: str = ""):
        self.url = url
        self.index_name = index_name
        self._client = None
        
    @retry(
        stop=stop_after_attempt(10),  # Максимум 10 попыток
        wait=wait_exponential(multiplier=1, min=2, max=30),  # Экспоненциальная задержка: 2, 4, 8, 16, 30...
        retry=retry_if_exception_type((ConnectionError, ESConnectionError, OSError)),
        reraise=True
    )
    async def _create_client(self):
        """Создает клиент с повторными попытками при ошибках подключения"""
        logger.info(f"Attempting to connect to Elasticsearch at {self.url}...")
        client = AsyncElasticsearch(
            self.url, 
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        if not await client.ping():
            raise ConnectionError(f"Failed to ping Elasticsearch at {self.url}")
        logger.info(f"✅ Successfully connected to Elasticsearch at {self.url}")
        return client

    @property
    async def client(self):
        """Ленивая инициализация клиента с retry"""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    @abstractmethod
    async def save_obj(self, obj: T, obj_id: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def get_obj(self, id: str) -> Optional[T]:
        pass

    @abstractmethod
    async def update_obj(self, id: str, obj: T) -> None:
        pass

    @abstractmethod
    async def delete_obj(self, id: str) -> None:
        pass
    
    async def close(self):
        """Закрываем соединение"""
        if self._client:
            await self._client.close()
            logger.info("Elasticsearch connection closed")


class ElasticsearchManager(AbstractElasticsearchManager[NewsSchema]):
    def __init__(self, index_name: str = "news"):
        logger.debug("Initializing Elasticsearch manager...")
        super().__init__(index_name=index_name)
    
    async def _ensure_index_exists(self):
        """Проверяет и создает индекс если нужно (с retry)"""
        client = await self.client
        try:
            if not await client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "user_id": {"type": "integer"},
                            "title": {
                                "type": "text", 
                                "fields": {"keyword": {"type": "keyword"}}
                            },
                            "body": {"type": "text"},
                            "images": {"type": "keyword"},
                            "created_at": {"type": "date"},
                            "updated_at": {"type": "date"}
                        }
                    }
                }
                await client.indices.create(index=self.index_name, body=mapping)
                logger.info(f"✅ Index '{self.index_name}' created")
            else:
                logger.debug(f"Index '{self.index_name}' already exists")
        except Exception as e:
            logger.error(f"Error ensuring index exists: {e}")
            raise

    async def save_obj(self, obj: NewsSchema, obj_id: str) -> str:
        """Сохраняет объект в Elasticsearch (с retry при ошибках сети)"""
        await self._ensure_index_exists()
        client = await self.client
        doc_dict = obj.model_dump()
        doc_dict.pop('id', None) 
        response = await client.index(
            index=self.index_name,
            id=obj_id,
            document=doc_dict
        )
        logger.info(f"✅ Object saved with ID: {response.get('_id')}")
        return response.get('_id')
    
    async def get_obj(self, id: str) -> Optional[NewsSchema]:
        """Получает объект из Elasticsearch (с retry при ошибках сети)"""
        await self._ensure_index_exists()
        client = await self.client
        try:
            response = await client.get(
                index=self.index_name,
                id=id
            )
            source_data = response.get('_source', {})
            source_data['id'] = id
            obj = NewsSchema(**source_data)
            logger.info(f"✅ Object with ID {id} retrieved")
            return obj
        except NotFoundError:
            logger.warning(f"⚠️  Object with ID {id} not found")
            return None
    
    async def update_obj(self, id: str, obj: NewsSchema) -> None:
        """Обновляет объект в Elasticsearch (с retry при ошибках сети)"""
        await self._ensure_index_exists()
        client = await self.client
        doc_dict = obj.model_dump(exclude_unset=True)
        doc_dict.pop('id', None)
        await client.update(
            index=self.index_name,
            id=id,
            doc=doc_dict
        )   
        logger.info(f"✅ Object with ID {id} updated")
    
    async def delete_obj(self, id: str) -> None:
        """Удаляет объект из Elasticsearch (с retry при ошибках сети)"""
        await self._ensure_index_exists()
        client = await self.client
        try:
            await client.delete(index=self.index_name, id=id)
            logger.info(f"✅ Object with ID {id} deleted")
        except NotFoundError:
            logger.warning(f"⚠️  Object with ID {id} not found for deletion")
