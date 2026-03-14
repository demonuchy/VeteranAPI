from typing import Annotated, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from utils.jwt_manager import PyJWTTokenManager, TokenStorage
from utils.minio_manger import MinioManager
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
        user_repository=UserRepository(session), 
        token_repository=TokenRepository(session),
        token_storage=TokenStorage(),
        token_manager=PyJWTTokenManager()
    )


async def get_news_service(session : AsyncSession = Depends(get_session)) -> AuthService:
    """DI сервиса"""
    return NewsService(
        news_repository=NewsRepository(session),
        image_repository=NewsImagesRepository(session),
        comment_repository=CommentRepository(session),
        news_like_repository=NewsLikeRepository(session),
        minio_manager=MinioManager()
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