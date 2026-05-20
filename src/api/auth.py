from typing import Optional
from  fastapi import APIRouter, Depends, status, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from shared.depends import AuthServiceDep
from schemas.auth import RegisterRequest, LoginRequest
from shared.logger.logger import logger

security = HTTPBearer(auto_error=False)

async def get_token(
        request : Request, 
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
        ) -> str:
    """Получаем токен из запроса"""
    logger.debug("Get token ...")
    if credentials:
        return credentials.credentials
    token = request.session.get("access_token")
    if token:
        return token
    logger.debug("Token not foun")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token not found in Authorization header or session",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_device_id(
        request : Request, 
        device_id : Optional[str] = Header(None, alias="X-Device-Id")
        ) -> str:
    logger.debug("Get device id ...")
    if device_id:
        return device_id
    session_device_id = request.session.get("session_id")
    if session_device_id:
        return session_device_id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="X-Device-Id header or session_id required"
    )
    

auth_route = APIRouter(prefix="/api/v1/auth")


@auth_route.post("/register")
async def register(
    service : AuthServiceDep, 
    request : Request, 
    data : RegisterRequest, 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Регистрация пользователя"""
    res = await service.register(
        device_id=device_id, 
        ip_address=request.client.host, 
        **data.model_dump()
        )
    return JSONResponse(
        status_code = status.HTTP_201_CREATED, 
        content={
            "detail" : "User register", 
            "data" : {
                "user" : res.user.model_dump(),
                "access_token" : res.access_token,
                "refresh_token" : res.refresh_token,
                "token_type": "bearer"
                }
            }
        )


@auth_route.post("/login")
async def login(
    service : AuthServiceDep, 
    request : Request, 
    data : LoginRequest, 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Вход в систему"""
    res = await service.login(
        device_id=device_id, 
        ip_address=request.client.host, 
        **data.model_dump()
        )
    return JSONResponse(
        status_code = status.HTTP_200_OK, 
        content={
            "detail" : "User login", 
            "data" : {
                "user" : res.user.model_dump(),
                "access_token" : res.access_token,
                "refresh_token" : res.refresh_token,
                "token_type": "bearer"
                }
            }
        )


@auth_route.post("/verify")
async def verify(
    service : AuthServiceDep, 
    token: str = Depends(get_token), 
    device_id: str = Depends(get_device_id)
    ):
    """Верефикация запроса на приватные маршурты (Проверка сесси/токена )"""
    res = await service.verify(
        device_id=device_id, 
        access_token=token
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        headers={
            "X-User-Id" : str(res.user_id),
            "X-User_Role" : res.user_role
            },
        content={
            "detail" : "Access token is valid",
            "data": {
                "user" : {
                    "id" : res.user_id, 
                    "role" : res.user_role
                    }
                } 
            }
        )


@auth_route.post("/refresh")
async def refresh(
    request : Request, 
    service : AuthServiceDep, 
    token: str = Depends(get_token), 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Верефикация refresh токена"""
    access_token = await service.refresh(
        device_id=device_id,
        refresh_token=token, 
        ip_address=request.client.host
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "detail" : "Refresh token is valid",
            "data" : {
                "access_token" : access_token,
                "token_type": "bearer"
                }
            }
        )


@auth_route.post("/logout")
async def logout(
    service : AuthServiceDep, 
    user_id = Header(..., alias="X-User-Id"), 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Выход из системы"""
    await service.logout(user_id=int(user_id), device_id=device_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )

@auth_route.post("/logout-all")
async def logout(
    service : AuthServiceDep, 
    user_id = Header(..., alias="X-User-Id"), 
    ):
    """Выход из системы"""
    await service.logout_all(user_id=int(user_id))
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )


