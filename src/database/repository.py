from typing import Any, List
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload, contains_eager
from .models import User, News, NewsImages, Comment, Token
from .base import BaseSQLAlchemyRepository
from .fields import TokenType
from schemas.auth import TokenPyload
from shared.logger.logger import logger

class TokenRepository(BaseSQLAlchemyRepository[Token]):
    def __init__(self, session):
        super().__init__(session=session, model=Token)

    async def accouting_rfresh_token_with_DTO(self, token_payload : TokenPyload):

        print("Token pyload", token_payload)
        token_data = token_payload.for_db()
        print("Token pyload after serialize", token_data)
        token_data['created_at'] = token_data.pop('iat')
        await self.create(**token_data)
    
    async def accouting_refresh_token(
            self, 
            user_id, 
            jti, 
            exp, 
            ip_address,
            user_role,
            device_id,
            token_type = TokenType.REFRESH, 
            ) -> None:
         await self.create(
            user_id = user_id, 
            jti=jti,
            exp=exp,
            device_id=device_id,
            token_type=token_type,
            user_role=user_role,
            ip_address=ip_address
            )
        
    async def get_token(self, user_id, jti, device_id):
        return await self.filter(user_id=user_id, jti=jti, device_id=device_id)
    
    async def delete_by_fields(self, **fields) -> bool:
        stmt = delete(self.model)
        for field_name, field_value in fields.items():
            if hasattr(self.model, field_name):
                stmt = stmt.where(getattr(self.model, field_name) == field_value)
            else:
                logger.warning(f"Field '{field_name}' not found in model {self.model.__name__}")
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

class UserRepository(BaseSQLAlchemyRepository[User]):
    def __init__(self, session):
        super().__init__(session=session, model=User)


class NewsRepository(BaseSQLAlchemyRepository[News]):
    def __init__(self, session):
        super().__init__(session=session, model=News)

    async def get_all_with_image(self, order):
        stmt = select(self.model
                    ).options(
                        selectinload(self.model.images.and_(NewsImages.order == order))
                        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_with_image(self, id):
        stmt = select(self.model).where(self.model.id == id).options(selectinload(self.model.images))
        result = await self.session.execute(stmt)
        return result.scalar_one()


class NewsImagesRepository(BaseSQLAlchemyRepository[NewsImages]):
    def __init__(self, session):
        super().__init__(session=session, model=NewsImages)

    async def bulk_create(self, records: List[dict]):
        """Пакетное создание записей (один запрос к БД)"""
        objects = [self.model(**rec) for rec in records]
        self.session.add_all(objects)
        await self.session.flush()
        return objects
    

class CommentRepository(BaseSQLAlchemyRepository[Comment]):
    def __init__(self, session):
        super().__init__(session=session, model=Comment)
        
