from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any, Type
from elasticsearch_dsl import async_connections, Q
from elasticsearch.exceptions import NotFoundError, ConnectionError as ESConnectionError
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
)

from shared.logger.logger import logger
from shared.config import config

# Правильные импорты
from schemas.elasticsearch import BaseDocument, NewsDocument

# Тип для документа Elasticsearch
DocumentType = TypeVar('DocumentType', bound=BaseDocument)


class AbstractElasticsearchManager(ABC):
    """Абстрактный менеджер для работы с Elasticsearch"""
    
    @abstractmethod
    async def save_obj(self, obj: Dict[str, Any], obj_id: Optional[str] = None) -> str:
        """Сохраняет объект в Elasticsearch"""
        pass

    @abstractmethod
    async def get_obj(self, id: str) -> Optional[Dict[str, Any]]:
        """Получает объект из Elasticsearch"""
        pass

    @abstractmethod
    async def update_obj(self, id: str, obj: Dict[str, Any]) -> None:
        """Обновляет объект в Elasticsearch"""
        pass

    @abstractmethod
    async def delete_obj(self, id: str) -> None:
        """Удаляет объект из Elasticsearch"""
        pass
    
    @abstractmethod
    async def search(self, query: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Поиск документов"""
        pass
    
    @abstractmethod
    async def close(self):
        """Закрывает соединение"""
        pass


class BaseElasticsearchManager(AbstractElasticsearchManager, Generic[DocumentType]):
    """Базовый менеджер с поддержкой Generic типа документа"""
    
    def __init__(
        self, 
        document_type: Type[DocumentType],
        url: str = None,
        index_name: str = None
    ):
        """
        Инициализация менеджера с указанием типа документа
        
        Args:
            document_type: Класс документа Elasticsearch (должен наследоваться от BaseDocument)
            url: URL Elasticsearch (опционально)
            index_name: Имя индекса (опционально, будет взят из класса документа)
        """
        self.document_type = document_type
        self.url = url or config.ElasticsearchUrl
        self.index_name = index_name or document_type.get_index_name()
        self._connected = False
        self._client = None
        
        logger.debug(f"Initialized {self.__class__.__name__} for index '{self.index_name}' with document type {document_type.__name__}")
    
    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, ESConnectionError, OSError)),
        reraise=True
    )
    async def _create_connection(self):
        """Создает подключение к Elasticsearch"""
        logger.info(f"Attempting to connect to Elasticsearch at {self.url}...")
        
        # Закрываем существующее соединение если есть
        try:
            if self._client:
                await self._client.close()
        except:
            pass
        
        # Создаем новое соединение
        self._client = async_connections.create_connection(
            hosts=[self.url],
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        # Проверяем соединение
        client = async_connections.get_connection()
        if not await client.ping():
            raise ConnectionError(f"Failed to ping Elasticsearch at {self.url}")
        
        logger.info(f"✅ Successfully connected to Elasticsearch at {self.url}")
        return client
    
    async def _ensure_connection(self):
        """Ленивая инициализация подключения"""
        if not self._connected:
            await self._create_connection()
            self._connected = True
    
    async def _ensure_index_exists(self):
        """Проверяет и создает индекс если нужно"""
        await self._ensure_connection()
        
        # Проверяем существует ли индекс
        client = async_connections.get_connection()
        exists = await client.indices.exists(index=self.index_name)
        
        if not exists:
            logger.info(f"Creating index '{self.index_name}'...")
            
            # Получаем маппинг из класса документа
            if hasattr(self.document_type, 'get_mapping'):
                mapping = self.document_type.get_mapping()
            else:
                # Дефолтный маппинг
                mapping = {
                    "mappings": {
                        "properties": {},
                        "dynamic": True
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
            
            await client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"✅ Index '{self.index_name}' created")
        else:
            logger.debug(f"Index '{self.index_name}' already exists")
    
    def _document_to_dict(self, doc: DocumentType) -> Dict[str, Any]:
        """Преобразует DSL документ в словарь"""
        if not doc:
            return {}
        
        return doc.to_dict_with_id()
    
    def _dict_to_document(self, data: Dict[str, Any], doc_id: str = None) -> DocumentType:
        """Преобразует словарь в DSL документ"""
        doc = self.document_type()
        
        if doc_id:
            doc.meta.id = doc_id
        
        # Заполняем поля, пропуская системные
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if hasattr(doc, key):
                try:
                    setattr(doc, key, value)
                except Exception as e:
                    logger.warning(f"Could not set attribute {key}: {e}")
        
        return doc
    
    async def save_obj(self, obj: Dict[str, Any], obj_id: Optional[str] = None) -> str:
        """Сохраняет объект в Elasticsearch"""
        try:
            await self._ensure_index_exists()
            
            if obj_id is None and 'id' in obj:
                obj_id = str(obj['id'])
            
            if not obj_id:
                raise ValueError("Object ID is required")
            
            # Используем прямой client.index вместо doc.save()
            client = async_connections.get_connection()
            
            # Подготавливаем данные
            doc_body = obj.copy()
            if 'id' in doc_body:
                del doc_body['id']  # Убираем id из тела документа
            
            # Сохраняем
            response = await client.index(
                index=self.index_name,
                id=obj_id,
                body=doc_body,
                refresh=True
            )
            
            if response.get('result') in ['created', 'updated']:
                logger.info(f"✅ Object saved with ID: {obj_id} in index {self.index_name}")
            else:
                logger.warning(f"⚠️ Unexpected response: {response}")
            
            return obj_id
            
        except Exception as e:
            logger.error(f"❌ Failed to save object: {e}", exc_info=True)
            raise
    
    async def get_obj(self, id: str) -> Optional[Dict[str, Any]]:
        """Получает объект из Elasticsearch"""
        try:
            await self._ensure_index_exists()
            
            client = async_connections.get_connection()
            response = await client.get(
                index=self.index_name,
                id=id
            )
            
            if response and response.get('found'):
                result = response.get('_source', {})
                result['id'] = response.get('_id')
                logger.info(f"✅ Object with ID {id} retrieved from {self.index_name}")
                return result
            
            logger.warning(f"⚠️ Object with ID {id} not found in {self.index_name}")
            return None
            
        except NotFoundError:
            logger.warning(f"⚠️ Object with ID {id} not found in {self.index_name}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get object {id}: {e}", exc_info=True)
            return None
    
    async def update_obj(self, id: str, obj: Dict[str, Any]) -> None:
        """Обновляет объект в Elasticsearch"""
        try:
            await self._ensure_index_exists()
            
            client = async_connections.get_connection()
            response = await client.update(
                index=self.index_name,
                id=id,
                body={"doc": obj}
            )
            
            logger.info(f"✅ Object with ID {id} updated in {self.index_name}")
            
        except NotFoundError:
            logger.warning(f"⚠️ Object with ID {id} not found for update in {self.index_name}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to update object {id}: {e}", exc_info=True)
            raise
    
    async def delete_obj(self, id: str) -> None:
        """Удаляет объект из Elasticsearch"""
        try:
            await self._ensure_index_exists()
            
            client = async_connections.get_connection()
            response = await client.delete(
                index=self.index_name,
                id=id,
                refresh=True
            )
            
            if response.get('result') == 'deleted':
                logger.info(f"✅ Object with ID {id} deleted from {self.index_name}")
            
        except NotFoundError:
            logger.warning(f"⚠️ Object with ID {id} not found for deletion in {self.index_name}")
        except Exception as e:
            logger.error(f"❌ Failed to delete object {id}: {e}", exc_info=True)
            raise
    
    async def search(
        self, 
        query: str = None, 
        fields: List[str] = None,
        filters: Dict[str, Any] = None,
        from_: int = 0,
        size: int = 10,
        sort_by: str = "created_at"
    ) -> List[Dict[str, Any]]:
        """Поиск документов"""
        try:
            await self._ensure_index_exists()
            
            # Строим запрос
            must_conditions = []
            filter_conditions = []
            
            # Текстовый поиск
            if query:
                search_fields = fields or ['title^3', 'body', 'content']
                must_conditions.append({
                    "multi_match": {
                        "query": query,
                        "fields": search_fields
                    }
                })
            else:
                must_conditions.append({"match_all": {}})
            
            # Фильтры
            if filters:
                for field, value in filters.items():
                    if isinstance(value, dict):
                        filter_conditions.append({
                            "range": {field: value}
                        })
                    elif isinstance(value, list):
                        filter_conditions.append({
                            "terms": {field: value}
                        })
                    else:
                        filter_conditions.append({
                            "term": {field: value}
                        })
            
            # Собираем bool запрос
            bool_query = {"bool": {"must": must_conditions}}
            if filter_conditions:
                bool_query["bool"]["filter"] = filter_conditions
            
            # Выполняем поиск
            client = async_connections.get_connection()
            response = await client.search(
                index=self.index_name,
                body={
                    "query": bool_query,
                    "from": from_,
                    "size": size,
                    "sort": [sort_by]
                }
            )
            
            # Преобразуем результаты
            results = []
            for hit in response.get('hits', {}).get('hits', []):
                doc = hit.get('_source', {})
                doc['id'] = hit.get('_id')
                doc['_score'] = hit.get('_score')
                results.append(doc)
            
            total = response.get('hits', {}).get('total', {})
            total_count = total.get('value', 0) if isinstance(total, dict) else total
            
            logger.info(f"✅ Search completed in {self.index_name}. Found {len(results)} of {total_count} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}", exc_info=True)
            return []
    
    async def refresh_index(self):
        """Принудительно обновляет индекс"""
        try:
            await self._ensure_connection()
            client = async_connections.get_connection()
            await client.indices.refresh(index=self.index_name)
            logger.debug(f"Index '{self.index_name}' refreshed")
        except Exception as e:
            logger.error(f"Failed to refresh index: {e}")
    
    async def count(self, filters: Dict[str, Any] = None) -> int:
        """Подсчет количества документов"""
        try:
            await self._ensure_index_exists()
            
            # Строим фильтры
            filter_conditions = []
            if filters:
                for field, value in filters.items():
                    if isinstance(value, dict):
                        filter_conditions.append({
                            "range": {field: value}
                        })
                    elif isinstance(value, list):
                        filter_conditions.append({
                            "terms": {field: value}
                        })
                    else:
                        filter_conditions.append({
                            "term": {field: value}
                        })
            
            # Собираем запрос
            if filter_conditions:
                query = {"bool": {"filter": filter_conditions}}
            else:
                query = {"match_all": {}}
            
            # Выполняем подсчет
            client = async_connections.get_connection()
            response = await client.count(
                index=self.index_name,
                body={"query": query}
            )
            
            count = response.get('count', 0)
            logger.debug(f"Count in {self.index_name}: {count}")
            return count
            
        except Exception as e:
            logger.error(f"❌ Count failed: {e}", exc_info=True)
            return 0
    
    async def clear_index(self):
        """Очищает индекс (удаляет все документы)"""
        try:
            await self._ensure_index_exists()
            await self.delete_by_query({"match_all": {}})
            logger.info(f"✅ Index '{self.index_name}' cleared")
        except Exception as e:
            logger.error(f"❌ Failed to clear index: {e}")
    
    async def delete_by_query(self, query: Dict[str, Any]) -> int:
        """Удаляет документы по запросу"""
        try:
            await self._ensure_index_exists()
            
            client = async_connections.get_connection()
            response = await client.delete_by_query(
                index=self.index_name,
                body={"query": query},
                refresh=True
            )
            
            deleted_count = response.get('deleted', 0)
            logger.info(f"✅ Deleted {deleted_count} documents from {self.index_name}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Delete by query failed: {e}", exc_info=True)
            return 0
    
    async def search_nested(
        self,
        path: str,
        nested_query: Dict[str, Any],
        main_query: str = None,
        filters: Dict[str, Any] = None,
        inner_hits: Dict[str, Any] = None,
        from_: int = 0,
        size: int = 10,
        sort_by: str = "-created_at"
    ) -> List[Dict[str, Any]]:
        """Поиск с nested запросами"""
        try:
            await self._ensure_index_exists()
            
            # Строим основной запрос
            must_conditions = []
            filter_conditions = []
            
            # Добавляем nested запрос
            nested_full_query = {
                "nested": {
                    "path": path,
                    "query": nested_query
                }
            }
            
            if inner_hits:
                nested_full_query["nested"]["inner_hits"] = inner_hits
            
            must_conditions.append(nested_full_query)
            
            # Добавляем текстовый поиск
            if main_query:
                must_conditions.append({
                    "multi_match": {
                        "query": main_query,
                        "fields": ["title^3", "body", "content"]
                    }
                })
            
            # Добавляем фильтры
            if filters:
                for field, value in filters.items():
                    if isinstance(value, dict):
                        filter_conditions.append({
                            "range": {field: value}
                        })
                    elif isinstance(value, list):
                        filter_conditions.append({
                            "terms": {field: value}
                        })
                    else:
                        filter_conditions.append({
                            "term": {field: value}
                        })
            
            # Собираем bool запрос
            bool_query = {"bool": {"must": must_conditions}}
            if filter_conditions:
                bool_query["bool"]["filter"] = filter_conditions
            
            # Выполняем поиск
            client = async_connections.get_connection()
            response = await client.search(
                index=self.index_name,
                body={
                    "query": bool_query,
                    "from": from_,
                    "size": size,
                    "sort": [sort_by]
                }
            )
            
            # Преобразуем результаты
            results = []
            for hit in response.get('hits', {}).get('hits', []):
                doc = hit.get('_source', {})
                doc['id'] = hit.get('_id')
                
                if 'inner_hits' in hit:
                    doc['inner_hits'] = hit['inner_hits']
                
                results.append(doc)
            
            logger.info(f"✅ Nested search completed in {self.index_name}. Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Nested search failed: {e}", exc_info=True)
            return []
    
    async def close(self):
        """Закрывает соединение"""
        if self._connected and self._client:
            try:
                client = async_connections.get_connection()
                await client.close()
            except:
                pass
            self._connected = False
            logger.info(f"Elasticsearch connection closed for index {self.index_name}")
    
    def get_client(self):
        """Возвращает клиент Elasticsearch для прямых запросов"""
        return async_connections.get_connection()
    
    async def bulk_save(self, objects: List[tuple[Dict[str, Any], str]]) -> List[str]:
        """Массовое сохранение объектов"""
        try:
            await self._ensure_index_exists()
            
            from elasticsearch.helpers import async_bulk
            
            client = async_connections.get_connection()
            
            def generate_actions():
                for obj_dict, obj_id in objects:
                    # Убираем id из источника
                    source = obj_dict.copy()
                    source.pop('id', None)
                    
                    yield {
                        '_index': self.index_name,
                        '_id': obj_id,
                        '_source': source
                    }
            
            success, failed = await async_bulk(client, generate_actions())
            logger.info(f"✅ Bulk save completed: {success} succeeded, {failed} failed")
            return [obj_id for _, obj_id in objects if obj_id]
            
        except Exception as e:
            logger.error(f"❌ Bulk save failed: {e}", exc_info=True)
            return []


class NewsElasticsearchManager(BaseElasticsearchManager[NewsDocument]):
    """Менеджер для работы с новостями"""
    
    def __init__(self, url: str = None, index_name: str = "news"):
        super().__init__(
            document_type=NewsDocument, 
            url=url, 
            index_name=index_name
        )

    async def search_by_title(self, title : str, size : int = 100):
        return await self.search(
            query=title,
            fields=['title^3', 'title.raw^2'],
            size=size,
            sort_by="created_at"
        )