import uuid
from enum import Enum
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from shared.logger.logger import logger
from shared.config import config
from schemas.auth import ServiceLoginResponce, ServiceRegisteResponce, ServiceVerifyResponce, TokenPyload
from utils.jwt_manager import AbstractTokenManager, AbstractTokenStorage
from utils.password_hash import hash_password, is_password_valid
from utils.mail_service import MailService
from utils.redis_manager import AbstractRedisManager
from database.base import BaseSQLAlchemyRepository
from database.repository import TokenRepository
from database.fields import Role
from .base import BaseService


class AuthService(BaseService):
    """Сервисный слой (бизнес логика регистрация/вход/верефикация сесси/логаут)"""
    def __init__(
            self,
            session : AsyncSession,
            user_repository : BaseSQLAlchemyRepository, 
            mail_service : MailService,
            redis_manager : AbstractRedisManager,
            token_storage : AbstractTokenStorage,
            token_manager : AbstractTokenManager,
            token_repository : TokenRepository
            ):
        super().__init__(session=session)
        self._redis_manager : AbstractRedisManager = redis_manager
        self._mail_service : MailService = mail_service 
        self._user_repository : BaseSQLAlchemyRepository = user_repository
        self._token_repository : TokenRepository = token_repository
        self._token_storage : AbstractTokenStorage = token_storage
        self._token_manager : AbstractTokenManager = token_manager

    @property
    def user_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._user_repository, self._session)
    
    @property 
    def mail_service(self) -> MailService:
        return self._get_depends(self._mail_service)
    
    @property 
    def redis_manager(self) -> AbstractRedisManager:
        return self._get_depends(self._redis_manager)
    
    @property
    def token_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._token_repository, self._session)
    
    @property
    def token_storage(self) -> AbstractTokenStorage:
        return self._get_depends(self._token_storage)
    
    @property
    def token_manager(self) -> AbstractTokenManager:
        return self._get_depends(self._token_manager)
    
    
    
    #новый сценарий регистрации
    async def register_with_mail_verification(self, username : str, password : str, ip_address : str, device_id : str):
        """
        Регистрация с подтверждением почты
        1 Проверяем существование пользователя в базе по mail
            if существует:
                выбрасываем 409
            else
                pass
        2 Создаем пользователя с is_active = false
        3 Генерируем код верефикации 
        4 отправляем на mail
        5 генерируем Code_session_id 
        6 сохраняем код в Redis подключем Code_session_id
        7 Генерируем коротко живущий токен с Code_session_id , mail, uid
        8 Отдаем токен пользователю
        """
        logger.debug("News sign in")
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
            hash_password=hash_password(password),
            is_active=False
            )
        logger.debug('generate code') 
        code = self.mail_service.generate_code()
        logger.debug('add background task')
        await self.mail_service.send_code(code, username)
        logger.debug('generate token id')
        session_id = str(uuid.uuid4())
        logger.debug(f'Save code session {session_id}')
        await self.redis_manager.save_with_ttl(session_id, {'code' : code, 'attemps' : 1}, ttl=300)
        logger.debug('Create code token')
        verefy_code_token = self.token_manager.create_access_token(
            user_id=user.id, 
            user_role = user.role.value if isinstance(user.role, Enum) else user.role,
            is_active = user.is_active,
            device_id = device_id,
            ip_address = ip_address,
            expire_minutes=5, 
            session_id=session_id, 
            mail=username
            )
        logger.debug('Success')
        return verefy_code_token


    async def verify_code(self, token : str, user_code : str):
        """
        Проверка кода верефикации
        1 Получаем и рассшифровываем токен
        2 Получаем Code_session_id из pyload
        3 Получаем код из Redis по Code_session_id
            if Code_session_id не существует в Redis(нет записи под этим ключем)
                Выбрасываем с ошибкой
        5 Получаем uid из payload
        4 Сверяем код с кодом пришедшим от пользователя 
            if код совпал:
                Активируем пользователя по uid
                Удалаем запись из Redis по Code_session_id
                Генерируем пару токенов access, refresh
                Отдаем токены пользователю
            else
                получаем счетчик попыток(attemps) из Redis по Code_session_id
                if attemps > max_attemps:
                    Удаляем запись из Redis по Code_session_id
                    Выбрасываем с ошибкой
                Инкрементируем счетчик попыток
                Выбрасываем с ошибкой
        
        """
        logger.debug(f'verefy code code: {user_code}')
        payload = self.token_manager.verify_token(token=token, token_type="access")
        if not payload:
            raise
        session_id = payload.session_id
        logger.debug('Get code session ogj')
        code_session_obj = await self.redis_manager.get(session_id)
        if not code_session_obj:
            logger.warn('Session not found')
            raise HTTPException(detail='Session expired', status_code=status.HTTP_400_BAD_REQUEST)
        code = code_session_obj.get('code')
        user_id = payload.user_id
        logger.debug('Compair code')
        if code != user_code:
            logger.debug('Compair failed')
            attemp_count = code_session_obj.get('attemps')
            logger.debug('Check attemps')
            if attemp_count > 3:
                await self.redis_manager.delete(session_id)
                logger.warn('Exceeded the limit attemps')
                raise HTTPException(detail='Exceeded the limit attemps', status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            logger.debug('Incriment attemps count')
            attemp_count += 1
            await self.redis_manager.update_preserve_ttl(session_id, {'code' : code, 'attemps' : attemp_count})
            logger.warn('Code is not valid')
            raise HTTPException(detail='Verefy code failed', status_code=status.HTTP_400_BAD_REQUEST)
        logger.debug('Activate user')
        await self.user_repository.update(user_id, is_active=True)
        logger.debug('Delete old session')
        await self.redis_manager.delete(session_id)
        logger.debug('Create token pair')
        access_token, refresh_token = self.token_manager.create_token_pair(
            user_id = user_id, 
            user_role = payload.user_role,
            is_active = payload.is_active,
            device_id = payload.device_id,
            ip_address= payload.ip_address
            )
        logger.debug("Accouting refresh token")
        await self.token_repository.accouting_rfresh_token_with_DTO(refresh_token.payload)
        logger.debug("Accouting access token")
        await self.token_storage.accouting_token_with_DTO(access_token.payload)
        return access_token, refresh_token
        
        
    async def get_new_code(self):
        """
        Повторная отправка кода
        1 Получаем и рассшифровываем токен
        2 Получаем mail из pyload
        3 Генерируем код верефикации 
        4 отправляем на mail
        5 генерируем Code_session_id 
        6 сохраняем код в Redis подключем Code_session_id
        7 Генерируем коротко живущий токен с Code_session_id , mail, uid
        8 Отдаем токен пользователю
        """
       
    async def register(
            self, 
            username : str, 
            password : str, 
            ip_address : str, 
            device_id :str, 
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
            user_role = user.role.value if isinstance(user.role, Enum) else user.role,
            is_active = user.is_active,
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
        if hasattr(user, 'is_active') and not user.is_active:
            logger.warn("User not is active")
            raise HTTPException(detail="User not is active. Please complete the verification", status_code=status.HTTP_403_FORBIDDEN)
        if hasattr(user, 'disable') and user.disable:
            logger.warn('Account has been blocked')
            raise HTTPException(detail="Account has been blocked", status_code=status.HTTP_403_FORBIDDEN)
        logger.debug("Check tokens")
        logger.debug("Revoking the access token")
        revork_count = await self.token_storage.delete_by_pattern(f"{user.id}:*:{device_id}")
        logger.debug("Revoking the refresh token")
        await self.token_repository.delete_by_fields(user_id = user.id, device_id = device_id)
        logger.debug(f"Revork {revork_count} tokens")
        logger.debug("calculate expire ...")
        refresh_expire_minutes=config.JWT_REFRESH_EXPIRE_MINUTES
        if is_admin:
            if user.role != Role.ROOT:
                logger.warn("Role is not root forbidden")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
            refresh_expire_minutes=config.JWT_ADMIN_REFRESH_EXPIRE_MINUTES
        logger.debug(f"exoire {refresh_expire_minutes}")
        logger.debug("Create token pair ...")
        access_token, refresh_token = self.token_manager.create_token_pair(
            user_id=user.id, 
            user_role = user.role.value if isinstance(user.role, Enum) else user.role,
            is_active = user.is_active,
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
        # logger.debug(f"Payload : {serialize_token_payload}")
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

    async def logout(self, user_id : int, device_id : str):
        logger.debug("Logout attemp")
        logger.debug("Revoking the refresh token")
        await self.token_repository.delete_by_fields(user_id = user_id, device_id = device_id)
        logger.debug("Revoking the access token")
        revork_count = await self.token_storage.delete_by_pattern(f"{user_id}:*:{device_id}")
        logger.debug(f"Revork {revork_count} tokens")
        logger.debug("User logout")

    async def logout_all(self, user_id : int ):
        logger.debug("Logout all attemp")
        logger.debug("Revoking the refresh token")
        await self.token_repository.delete_by_fields(user_id = user_id)
        logger.debug("Revoking the access token")
        revork_count = await self.token_storage.delete_by_pattern(f"{user_id}:*:*")
        logger.debug(f"Revork {revork_count} tokens")
        logger.debug("User logout all")
