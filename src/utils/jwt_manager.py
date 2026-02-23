import jwt
import abc
import uuid
from datetime import datetime, timedelta
from typing import Literal, Tuple

from .redis_manager import AbstractRedisManager, redis_manager
from database.repository import TokenRepository
from shared.logger.logger import logger
from shared.config import config 
from schemas.auth import CreateToken, TokenPyload


class AbstractTokenManager(abc.ABC):
    def __init__(
            self, 
            kid : str,
            secret_key : str, 
            algorithm : str, 
            access_expire_minutes : int, 
            refresh_expire_minutes : int
            ):
        self.kid = kid
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_minutes = refresh_expire_minutes

    @abc.abstractmethod
    def _create_token(self,
            user_id: int, 
            token_type: Literal["access", "refresh"], 
            expire_minutes: int,
            **kwargs
            ) -> CreateToken:
        """
        Созданеие JWT токена 
        Args:
            user_id (int): id владельца токена.
            jti (UUID) : id токена
            token_type (str): тип токена access || refresh
            expire_minutes (int): время жизни токена
        Returns:
            payload: данные токена
            token: JWT токен.
        """
        pass
    
    @abc.abstractmethod
    def create_access_token(self,   
            user_id: int, 
            expire_minutes: int,
            **kwargs
            ) -> CreateToken:
         
        """
        Создание access токена 
        Args:
            user_id : id пользователя
            **kwargs : дополнителные данные для pyload
        Returns:
            payload: данные токена
            token: JWT токен.
        """
        pass

    @abc.abstractmethod
    def create_refresh_token(self,   
            user_id: int, 
            expire_minutes: int,
            **kwargs
            ) -> CreateToken:
        """
        Создание refresh токена
        Args:
            user_id : id пользователя
            **kwargs : дополнителные данные для pyload
        Returns:
            payload: данные токена
            token: JWT токен.
            
        """
        pass

    @abc.abstractmethod
    def create_token_pair(
        self, 
        user_id,  
        access_expire_minets, 
        refresh_expire_minets,
        **kwargs
        ) -> Tuple[CreateToken, CreateToken]:
        """Создание пары токенов"""
        pass

    @abc.abstractmethod
    def verify_token(self,
            token : str, 
            token_type : Literal["access", "refresh"],
            ) -> TokenPyload | None:  
        """
        Валидация JWT токена
        Args:
            token : токен
            type : тип токена
        Returns:
            pyload : если токен валиден
        """
        pass


class AbstractTokenStorage(abc.ABC):
    def __init__(self, redis_manager : AbstractRedisManager):
        self._redi_manager = redis_manager

    @property
    def redis_manager(self) -> AbstractRedisManager:
        return self._redi_manager

    @abc.abstractmethod
    async def accouting_token(self, key : str, pyload : dict, ttl : int) -> None:
        """
        Cохранение токена в редис
        Args:
            key
            payload
            ttl
        Returns:
            None
        """
        pass

    @abc.abstractmethod
    async def accouting_token_with_DTO(self, token_payload : TokenPyload) -> None:
        """
        Cохранение токена в редис
        Args:
            token
        Returns:
            None
        """
        pass

    @abc.abstractmethod
    async def get_token(self, key : str) -> dict | None:
        """
        Получение токена по ключу из редис
        Args:
            key
        Returns:
            dict | None
        """
        pass

    @abc.abstractmethod
    async def delete_token(self, key : str) -> None:
        """
        удаление токена по ключу из редис
        Args:
            key
        Returns:
             None
        """
        pass
    
    @abc.abstractmethod
    async def delete_by_pattern(self, pattern) -> int:
        """
        Удаление токена по паттерну из редис
        Args:
            pattern
        Returns:
             None
        """
        pass


class AbstractTokenService(abc.ABC):
    def __init__(
            self, 
            token_manager : AbstractTokenManager, 
            token_storage : AbstractTokenStorage, 
            token_repository : TokenRepository
            ):
        self._token_manager : AbstractTokenManager = token_manager
        self._token_storage : AbstractTokenStorage = token_storage
        self._token_repository : TokenRepository = token_repository

    @property
    def token_manager(self):
        return self._token_manager
    
    @property
    def token_storage(self):
        return self._token_storage
    
    @property
    def token_repository(self):
        return self._token_repository
    
    @abc.abstractmethod
    def create_access_token(self, user_id : int, **kwargs):
        pass
    
    @abc.abstractmethod
    def create_refresh_token(self, user_id : int, **kwargs):
        pass

    @abc.abstractmethod
    def create_token_pair(self, user_id : int, **kwargs):
        pass

    @abc.abstractmethod
    async def accouting_access_token(self, key: str, pyload: dict, ttl: int) -> None:
        pass

    @abc.abstractmethod
    async def accouting_refresh_token(self, key: str, pyload: dict) -> None:
        pass
        
       
class PyJWTTokenManager(AbstractTokenManager):
    def __init__(
            self, 
            kid : str = config.JWT_KID,
            secret_key : str = config.JWT_SECRET_KEY, 
            algorithm : str = config.JWT_ALGORITHM, 
            access_expire_minutes : int =  config.JWT_ACCESS_EXPIRE_MINUTES, 
            refresh_expire_minutes : int =  config.JWT_REFRESH_EXPIRE_MINUTES,
            payload_scheme = TokenPyload
            ):
        super().__init__(
            kid=kid,
            secret_key=secret_key, 
            algorithm=algorithm, 
            access_expire_minutes=access_expire_minutes, 
            refresh_expire_minutes=refresh_expire_minutes
            )
        self.payload_scheme = payload_scheme

    def _create_token(
            self,
            user_id: int, 
            token_type: Literal["access", "refresh"], 
            expire_minutes: int,
            **kwargs
            ) -> CreateToken:
        exp = datetime.utcnow() + timedelta(minutes=expire_minutes)
        jti = uuid.uuid4()
        payload = {
            "exp": exp,
            "jti" : str(jti),
            "token_type": token_type,
            "user_id": user_id,
            "iat": datetime.utcnow()
        }
        payload.update(kwargs)
        self.payload_scheme.model_validate(payload)
        headers = {"kid": str(self.kid)}
        token = jwt.encode(
            payload=payload,
            key=self.secret_key, 
            algorithm=self.algorithm,  
            headers=headers
        )
        return CreateToken(
            payload=payload, 
            token=token
            )

    def create_access_token(
            self,
            user_id: int, 
            expire_minutes: int = config.JWT_ACCESS_EXPIRE_MINUTES,
            **kwargs
            ) -> CreateToken:
        res = self._create_token(
            user_id=user_id, 
            token_type="access", 
            expire_minutes=expire_minutes,
            **kwargs
            )
        return res
        
    def create_refresh_token( 
            self,   
            user_id: int, 
            expire_minutes: int=config.JWT_REFRESH_EXPIRE_MINUTES,
            **kwargs
            ) -> CreateToken:
        res = self._create_token(
            user_id=user_id, 
            token_type="refresh", 
            expire_minutes=expire_minutes,
            **kwargs
            )
        return res

    def create_token_pair(
            self, 
            user_id, 
            access_expire_minets=config.JWT_ACCESS_EXPIRE_MINUTES, 
            refresh_expire_minets=config.JWT_REFRESH_EXPIRE_MINUTES,
            **kwargs
            ) -> Tuple[CreateToken, CreateToken]:
        """Создание пары токенов"""
        access   = self.create_access_token(user_id, expire_minutes=access_expire_minets, **kwargs)
        refresh = self.create_refresh_token(user_id, expire_minutes=refresh_expire_minets, **kwargs)
        return access, refresh

    def verify_token(
            self,
            token : str, 
            token_type : Literal["access", "refresh"],
            ) -> TokenPyload | None:
        try:
            key = self.secret_key
            if isinstance(key, str):
                key = key.encode('utf-8')
            pyload = jwt.decode(
                jwt=token, 
                key=key, 
                algorithms=[self.algorithm]
                )
            if pyload.get("token_type") != token_type:
                return None
            return TokenPyload(**pyload)
        except jwt.InvalidSignatureError:
            logger.warn("Подпись недействительна!")
            return None
        except jwt.ExpiredSignatureError:
            logger.warn("Токен просрочен!")
            return None
        except jwt.InvalidIssuerError:
            logger.warn("Неверный издатель токена!")
            return None
        except Exception as e:
            logger.warn(f"Ошибка проверки токена: {e}")
            return None


class TokenStorage(AbstractTokenStorage):
    def __init__(self, redis_manager = redis_manager):
        super().__init__(redis_manager=redis_manager)

    async def accouting_token(
            self, 
            key: str, 
            pyload: dict, 
            ttl: timedelta = timedelta(minutes=config.JWT_ACCESS_EXPIRE_MINUTES)
            ) -> None:
        await self.redis_manager.save_with_ttl(key, pyload, ttl)

    async def accouting_token_with_DTO(self, token_payload: TokenPyload) -> None:
        payload = token_payload.model_dump()
        await self.accouting_token(
            key=f"{token_payload.user_id}:{token_payload.jti}:{token_payload.device_id}", 
            pyload=payload
            )
    
    async def delete_token(self, key: str) -> None:
        await self.redis_manager.delete(key)

    async def delete_by_pattern(self, pattern) -> int:
        return await self.redis_manager.delete_by_pattern(pattern)
    
    async def get_token(self, key: str) -> dict | None:
        return await self.redis_manager.get(key)
    
