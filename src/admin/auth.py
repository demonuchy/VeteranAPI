import httpx
import os
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from shared.logger.logger import logger
import uuid

class AuthBackend(AuthenticationBackend):
    """Аутентификация для SQLAdmin через ваши API эндпоинты"""
    
    def __init__(self, secret_key: str):
        super().__init__(secret_key)
        # URL вашего API (можно через переменные окружения)
        self.api_url = os.getenv("API_URL", "http://localhost:8000")
    
    async def login(self, request: Request) -> bool:
        """Вызывается при отправке формы входа в SQLAdmin"""
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        logger.debug(f"Admin login attemp username : {username}, password : {password}")
        if not username or not password:
            return False
        try:
            async with httpx.AsyncClient() as client:
                session_id = str(uuid.uuid4()).replace("-", "")
                response = await client.post(
                    f"{self.api_url}/api/v1/auth/login",
                    json={
                        "username": username, 
                        "password": password, 
                        "is_admin" : True
                        },
                    headers={
                        "Content-Type": "application/json",
                        "X-Device-Id" : f"{session_id}"
                        }
                )
                if response.status_code != 200:
                    logger.warn("Forbbiden")
                    return False
                logger.debug("Parse responce ... ")
                data = response.json()
               # logger.debug(f"Data : {data}")
                request.session.update(
                    {
                        "access_token": data["data"]["access_token"],
                        "refresh_token" : data["data"]["refresh_token"],
                        "session_id" : session_id
                        }
                    )
                return True
        except Exception as e:
            print(f"Login error: {e}")
            return False

    async def authenticate(self, request: Request) -> bool:
        """Проверяет, аутентифицирован ли пользователь"""
        logger.debug(f"session : {request.session}")
        access_token = request.session.get("access_token")
        if not access_token:
            logger.warn("access token not found")
            return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/v1/auth/verify",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Device-Id" : f"{request.session.get('session_id')}"
                        }
                )
                if response.status_code != 200:
                    logger.debug("Refresh access token")
                    refresh_token = request.session.get("refresh_token")
                    if not refresh_token:
                        logger.warn("Reresh token not found")
                        return False
                    logger.debug("Fetch...")
                    response = await client.post(
                        f"{self.api_url}/api/v1/auth/refresh",
                        headers={
                            "Authorization": f"Bearer {refresh_token}",
                            "X-Device-Id": f"{request.session.get('session_id')}"
                            }
                        )
                    if response.status_code != 200:
                        logger.warn("Refresh token is not valid")
                        return False
                    data = response.json()
                    logger.debug("Fetch new access token")
                    new_access_token = data['data']['access_token']
                    response = await client.post(
                    f"{self.api_url}/api/v1/auth/verify",
                    headers={
                        "Authorization": f"Bearer {new_access_token}",
                        "X-Device-Id" : f"{request.session.get('session_id')}"
                        }
                    )
                    if response.status_code != 200:
                        logger.warn("New accsess token is not valid")
                        return False
                    logger.debug("update session")
                    request.session.update({"access_token" : new_access_token})
                logger.debug("Check user role ...")
                data = response.json()
                if data["data"]["user"]["role"] != "root":
                    logger.warn(f"Forbbiden {data['data']['user']}")
                    return False
                return True
        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    async def logout(self, request: Request) -> bool:
        """Выход из системы"""
        token = request.session.get("token")
        if token:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{self.api_url}/api/v1/auth/logout",
                        headers={"Authorization": f"Bearer {token}"}
                    )
            except Exception as e:
                print(f"Logout error: {e}")
                request.session.clear()
                return True