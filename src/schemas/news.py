# src/schemas/news.py
from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import List, Optional

class NewsImageSchema(BaseModel):
    id: int
    url: str
    filename: str
    bucket_name: str
    content_type: str
    order: int
    base64: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True  # для SQLAlchemy 2.0 (раньше было orm_mode=True)

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat()
    

class CommentShema(BaseModel):
    id : int
    user_id : int
    news_id : int 
    body : str
    like : int
    order : int 
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat()
    

class NewsSchema(BaseModel):
    id: int
    user_id: int
    title: str
    body: str
    views: int
    like : int 
    created_at: datetime
    updated_at: datetime
    images: List[NewsImageSchema] = []
    comments : List[CommentShema] = []

    class Config:
        from_attributes = True
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat()