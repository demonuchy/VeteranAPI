from elasticsearch_dsl import (
    AsyncDocument, Integer, Text, Keyword, Date, Boolean, 
    Float, Object, Nested, InnerDoc, Float, Long
)
from typing import Optional, Dict, Any, Type, List
from datetime import datetime


class ImageInnerDoc(InnerDoc):
    """Вложенный документ для изображения"""
    id = Integer()
    url = Keyword()  # URL изображения
    filename = Text()
    bucket_name = Keyword()
    content_type = Keyword()
    order = Integer()
    width = Integer()
    height = Integer()
    created_at = Date()


class CommentInnerDoc(InnerDoc):
    """Вложенный документ для комментария"""
    id = Integer()
    user_id = Integer()
    news_id = Integer()
    body = Text()
    like = Integer()
    order = Integer()
    created_at = Date()
    
    # Опционально: можно добавить информацию о пользователе
    user_name = Text()
    user_avatar = Keyword()


class BaseDocument(AsyncDocument):
    """Базовый класс для всех документов Elasticsearch"""
    
    class Meta:
        dynamic = True
    
    def to_dict_with_id(self) -> Dict[str, Any]:
        """Конвертирует документ в словарь с ID"""
        result = self.to_dict()
        if hasattr(self, 'meta') and self.meta and hasattr(self.meta, 'id'):
            result['id'] = self.meta.id
        return result


class NewsDocument(BaseDocument):
    """Документ новости с вложенными изображениями и комментариями"""
    
    # Основные поля
    id = Integer()
    user_id = Integer()
    title = Text(fields={"raw": Keyword(), "english": Text(analyzer="english")})
    body = Text(fields={"english": Text(analyzer="english")})
    views = Integer()
    like = Integer()
    created_at = Date()
    updated_at = Date()
    
    # Вложенные документы
    images = Nested(ImageInnerDoc, multi=True)  # Массив вложенных изображений
    comments = Nested(CommentInnerDoc, multi=True)  # Массив вложенных комментариев
    
    # Для обратной совместимости
    comment_ids = Keyword(multi=True)  # Можно оставить для быстрых запросов
    
    class Index:
        name = "news"
    
   
   
   