# src/schemas/user.py
from pydantic import BaseModel, field_serializer
from datetime import datetime
from database.fields import Role

class UserSchema(BaseModel):
    id: int
    username: str
    is_active : bool
    role : Role
    created_at: datetime
    updated_at : datetime

    class Config:
        from_attributes = True 

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat()
    
    @field_serializer('role')
    def serialize_role(self, role: datetime, _info):
        return str(role).split(".")[1].lower()