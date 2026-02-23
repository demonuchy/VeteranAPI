from typing import Literal, Union
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_serializer
from .user import UserSchema
from database.fields import Role, TokenType

class LoginRequest(BaseModel):
    username : EmailStr
    password : str
    is_admin : bool = False


class RegisterRequest(LoginRequest):
    pass


class ServiceRegisteResponce(BaseModel):
    user : UserSchema
    access_token : str
    refresh_token : str


class ServiceLoginResponce(ServiceRegisteResponce):
    pass


class ServiceVerifyResponce(BaseModel):
    user_id : int
    user_role : str


class TokenPyload(BaseModel):
    """Единая модель для всех токенов"""
    user_id: int
    user_role: Union[Role, str]  
    iat: datetime
    jti: str
    exp: datetime
    token_type: Union[TokenType, str] 
    device_id: str
    ip_address: str
    is_rework : bool = False

    def for_db(self):
        data = self.model_dump()
        data['user_role'] = Role(data['user_role'])
        data['token_type'] = TokenType(data['token_type'])
        return data
    
    def for_redis(self):
        return self.model_dump()


class CreateToken(BaseModel):
    token : str
    payload : TokenPyload
