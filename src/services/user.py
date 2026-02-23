from fastapi import HTTPException, status

from shared.logger.logger import logger
from schemas.user import UserSchema
from database.base import BaseSQLAlchemyRepository


class UserService:
    """Сервисный слой (бизнес логика регистрация/вход/верефикация сесси/логаут)"""
    def __init__(
            self,
            user_repository : BaseSQLAlchemyRepository, 
            ):
        self._user_repository : BaseSQLAlchemyRepository = user_repository
    
    @property
    def user_repository(self):
        return self._user_repository
    
    async def get_me(self, user_id):
        logger.debug(f"Get me ... id : {user_id}")
        user = await self.user_repository.get_by_id(int(user_id))
        logger.debug("Serialize ...")
        serialize_user = UserSchema.model_validate(user).model_dump()
        return serialize_user
