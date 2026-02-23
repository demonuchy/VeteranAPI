from fastapi import HTTPException, status
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger.logger import logger
from shared.config import config
from schemas.auth import ServiceLoginResponce, ServiceRegisteResponce, ServiceVerifyResponce, TokenPyload
from utils.jwt_manager import AbstractTokenManager, AbstractTokenStorage
from utils.password_hash import hash_password, is_password_valid
from database.base import BaseSQLAlchemyRepository
from database.repository import TokenRepository


class AuthService:
    """Сервисный слой (бизнес логика регистрация/вход/верефикация сесси/логаут)"""
    def __init__(
            self,
            user_repository : BaseSQLAlchemyRepository, 
            token_storage : AbstractTokenStorage,
            token_manager : AbstractTokenManager,
            token_repository : TokenRepository
            ):
        self._user_repository : BaseSQLAlchemyRepository = user_repository
        self._token_repository : TokenRepository = token_repository
        self._token_storage : AbstractTokenStorage = token_storage
        self._token_manager : AbstractTokenManager = token_manager

    @property
    def user_repository(self):
        return self._user_repository
    
    @property
    def token_repository(self):
        return self._token_repository
    
    @property
    def token_storage(self):
        return self._token_storage
    
    @property
    def token_manager(self):
        return self._token_manager
       
    async def register(
            self, 
            username : str, 
            password : str, 
            ip_address : str, 
            device_id :str, 
            is_admin : bool
            ) -> ServiceRegisteResponce:
        """регистрация"""
        logger.debug(f"Register attemp {username} - {password}")
        is_user_exists = await self.user_repository.exists_by_field("username", username)
        if is_user_exists:
            logger.warn("Error user already exists")
            raise HTTPException(
                detail="user already exists", 
                status_code=status.HTTP_409_CONFLICT
                )
        logger.debug("Create user ...")
        user = await self.user_repository.create(
            username=username, 
            hash_password=hash_password(password)
            ) 
        logger.debug("Create token pair ...")
        access_token, refresh_token = self.token_manager.create_token_pair(
            user_id=user.id, 
            user_role = user.role.value, 
            device_id = device_id,
            ip_address=ip_address
            )
        logger.debug("Accouting refresh token")
        await self.token_repository.accouting_rfresh_token_with_DTO(refresh_token.payload)
        logger.debug("Accouting access token")
        await self.token_storage.accouting_token_with_DTO(access_token.payload)
        logger.debug(f"User register")
        return ServiceRegisteResponce(
            user=user,
            access_token=access_token.token, 
            refresh_token=refresh_token.token
            )

    async def login(
            self, 
            username : str, 
            password : str, 
            ip_address : str, 
            device_id: str, 
            is_admin : bool
            ) -> ServiceLoginResponce:
        """Вход"""
        logger.debug(f"Login attemp {username} - {password}")
        logger.debug("Check login attemmp ...")
        # ...
        logger.debug("Check user ...")
        user = await self.user_repository.get_by_field("username", username)
        if not user or not is_password_valid(password, user.hash_password):
            logger.warn("Error user invalid credentials")
            raise HTTPException(detail="User invalid credentials", status_code=status.HTTP_401_UNAUTHORIZED)
        logger.debug("Check tokens")
        logger.debug("Revoking the refresh token")
        await self.token_repository.delete_by_fields(user_id = user.id, device_id = device_id)
        logger.debug("Revoking the access token")
        revork_count = await self.token_storage.delete_by_pattern(f"{user.id}:*:{device_id}")
        logger.debug(f"Revork {revork_count} tokens")
        logger.debug("calculate expire ...")
        refresh_expire_minutes=config.JWT_REFRESH_EXPIRE_MINUTES
        if is_admin:
            refresh_expire_minutes=60
        logger.debug(f"exoire {refresh_expire_minutes}")
        logger.debug("Create token pair ...")
        access_token, refresh_token = self.token_manager.create_token_pair(
            user_id=user.id, 
            user_role = user.role.value,
            device_id=device_id,
            ip_address=ip_address,
            refresh_expire_minets=refresh_expire_minutes
            )
        logger.debug("Accouting refresh token")
        await self.token_repository.accouting_rfresh_token_with_DTO(refresh_token.payload)
        logger.debug("Accouting access token")
        await self.token_storage.accouting_token_with_DTO(access_token.payload)
        logger.debug("User login")
        return ServiceLoginResponce(
            user=user,
            access_token=access_token.token, 
            refresh_token=refresh_token.token
            )

    async def verify(self, access_token : str, device_id : str) -> ServiceVerifyResponce:
        logger.debug("Verefy access token")
        payload = self.token_manager.verify_token(token=access_token, token_type="access")
        if not payload:
            logger.warn("Error invalid token")
            raise HTTPException(detail="Invalid token", status_code=status.HTTP_401_UNAUTHORIZED)
        logger.debug("Verification of access token registration")
        current_access_token = await self.token_storage.get_token(f"{payload.user_id}:{payload.jti}:{device_id}")
        if not current_access_token:
            logger.warn("Token not found")
            raise HTTPException(detail="Invalid token", status_code=status.HTTP_401_UNAUTHORIZED)
        logger.debug("serialize token payload ...")
        serialize_token_payload = TokenPyload(**current_access_token)
        logger.debug(f"Payload : {serialize_token_payload}")
        logger.debug("Access token is valid")
        return ServiceVerifyResponce(
            user_id=serialize_token_payload.user_id, 
            user_role=serialize_token_payload.user_role
            )

    async def refresh(self, refresh_token : str, ip_address : str, device_id : str) -> str:
        logger.debug("Verefy refresh token")
        payload = self.token_manager.verify_token(token=refresh_token, token_type="refresh")
        if not payload:
            logger.warn("Error invalid token")
            raise HTTPException(detail="Invalid token", status_code=status.HTTP_401_UNAUTHORIZED)
        logger.debug("Verification of refresh token registration")
        current_refresh_token = await self.token_repository.get_token(
            user_id = payload.user_id, 
            jti = payload.jti, 
            device_id=device_id
            )
        if not current_refresh_token:
            logger.warn(f"Tokenr not found key : {payload.user_id}:{payload.jti}:{device_id}")
            raise HTTPException(detail="Invalid token", status_code=status.HTTP_401_UNAUTHORIZED)
        logger.debug("Revoking the access token")
        revork_count = await self.token_storage.delete_by_pattern(f"{payload.user_id}:*:{device_id}")
        logger.debug(f"Revork {revork_count} tokens")
        logger.debug("Create access token ...")
        access_token = self.token_manager.create_access_token(
            user_id=current_refresh_token.user_id, 
            user_role=current_refresh_token.user_role.value, 
            device_id = current_refresh_token.device_id,
            ip_address=ip_address
            )
        logger.debug("Accouting access token")
        await self.token_storage.accouting_token_with_DTO(access_token.payload)
        return access_token.token

    async def logout(self, user_id : int):
        logger.debug("Logout attemp")
        ...
        logger.debug("User logout")

    async def logout_all(self, use_id : int ):
        logger.debug("Logout all attemp")
        ...
        logger.debug("User logout all")
