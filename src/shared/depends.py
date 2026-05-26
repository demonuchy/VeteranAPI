from typing import Annotated, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from utils.jwt_manager import PyJWTTokenManager, TokenStorage
from utils.minio_manger import MinioManager, AsyncMinIOManager
from utils.elasticsearch_manager import NewsElasticsearchManager
from utils.redis_manager import RedisManager
from utils.mail_service import MailService
from database.repository import UserRepository, TokenRepository, NewsRepository, NewsImagesRepository, CommentRepository, NewsLikeRepository
from services.auth import AuthService
from services.news import NewsService
from services.user import UserService

from database.engine import session_factory
from shared.logger.logger import logger
 

@asynccontextmanager
async def _get_session() -> AsyncGenerator[AsyncSession, None]:
    """Транзакция"""
    logger.debug("Open transaction ...")
    async with session_factory() as session:
        try:
            yield session 
            await session.commit()
            logger.debug("Commit")
        except Exception as e:
            logger.warn("Discard change rollback...")
            await session.rollback()
            raise
        finally:
            logger.debug("Session close")
            await session.close()
    

async def get_session():
    """Получаем сессию"""
    async with _get_session() as session:
        yield session


async def get_auth_service(session : AsyncSession = Depends(get_session)) -> AuthService:
    """DI сервиса"""
    return AuthService(
        session=session,
        mail_service=MailService,
        redis_manager=RedisManager,
        user_repository=UserRepository, 
        token_repository=TokenRepository,
        token_storage=TokenStorage,
        token_manager=PyJWTTokenManager
    )


async def get_news_service(session : AsyncSession = Depends(get_session)) -> AuthService:
    """DI сервиса"""
    return NewsService(
        session=session,
        news_repository=NewsRepository,
        image_repository=NewsImagesRepository,
        comment_repository=CommentRepository,
        news_like_repository=NewsLikeRepository,
        minio_manager=AsyncMinIOManager,
        elasticsearch_manager=NewsElasticsearchManager
    )


async def get_user_service(session : AsyncSession = Depends(get_session)) -> AuthService:
    """DI сервиса"""
    return UserService(
       user_repository=UserRepository(session)
    )

AuthServiceDep = Annotated[AuthService , Depends(get_auth_service)]
NewsServiceDep = Annotated[NewsService, Depends(get_news_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]