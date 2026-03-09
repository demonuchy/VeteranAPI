from  fastapi import APIRouter, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from shared.depends import AuthServiceDep
from schemas.auth import RegisterRequest, LoginRequest

security = HTTPBearer()
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
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Верефикация запроса на приватные маршурты (Проверка сесси/токена )"""
    access_token = credentials.credentials
    res = await service.verify(
        device_id=device_id, 
        access_token=access_token
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
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    device_id = Header(..., alias="X-Device-Id")
    ):
    """Верефикация refresh токена"""
    refresh_token = credentials.credentials
    access_token = await service.refresh(
        device_id=device_id,
        refresh_token=refresh_token, 
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


