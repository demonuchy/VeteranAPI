import os
import base64
import asyncio
import uuid
from fastapi import HTTPException, status, UploadFile
from typing import List, Optional

from concurrent.futures import ThreadPoolExecutor

from database.fields import ImageType
from database.base import BaseSQLAlchemyRepository
from utils.minio_manger import AbstractMinioManager
from schemas.news import NewsSchema
from shared.logger.logger import logger


class NewsService:
    def __init__(self, 
                 news_repository : BaseSQLAlchemyRepository, 
                 image_repository : BaseSQLAlchemyRepository,
                 minio_manager : AbstractMinioManager
                 ):
        self._executor = ThreadPoolExecutor(max_workers=10)  # Пул потоков
        self._news_repository = news_repository
        self._image_repository = image_repository
        self._minio_manager = minio_manager

    @property
    def news_repository(self):
        return self._news_repository

    @property
    def image_repository(self):
        return self._image_repository

    @property
    def minio_manager(self):
        return self._minio_manager
    
    async def _load_image(self, news):     
        for image in news.images:
            image_bytes = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self.minio_manager.get_obj,
                image.bucket_name,
                image.url,
            )
            logger.debug("Image loaded")
            image.base64 = base64.b64encode(image_bytes).decode('utf-8')
        return news
    
    async def delete_news(self, news_id) -> None:
        """Удаление новости"""
        logger.debug(f"Delete news {news_id}")
        news = await self.news_repository.get_with_image(news_id)
        logger.debug("Delete image from file storage")
        minio_task = []
        for image in news.images:
            minio_task.append(asyncio.get_event_loop().run_in_executor(
                self._executor, 
                self.minio_manager.delete_obj, 
                image.bucket_name,
                image.url
                ))
        await asyncio.gather(*minio_task)
        logger.debug("Delete news..")
        await self.news_repository.delete(news_id)
        logger.debug("✅ News deleted...")
    
    async def create_news(
            self, 
            user_id, 
            title: str, 
            body: str, 
            upload_images: List[UploadFile], 
            news_bucket_name: str = "news-images"
            ) -> None:
        """Создание новости"""
        logger.debug("Publish news...")
        news = await self.news_repository.create(
            user_id=user_id, 
            title=title, 
            body=body
        )
        news_folder = f"{news_bucket_name}/{news.id}"
        if not upload_images:
            return news
        read_tasks = [image.read() for image in upload_images]
        files_content = await asyncio.gather(*read_tasks)
        db_records = []
        minio_tasks = []
        for order, (image, content) in enumerate(zip(upload_images, files_content), start=1):
            if not image.filename:
                filename = f"{uuid.uuid4()}.jpg"
            else:
                name, ext = os.path.splitext(image.filename)
                filename = f"{name}_{uuid.uuid4()}{ext}"
            image_type = {
                "image/jpeg": ImageType.JPEG,
                "image/jpg": ImageType.JPEG,
                "image/png": ImageType.PNG,
                "image/webp": ImageType.WEBP
            }
            try:
                db_records.append({
                    'news_id': news.id,
                    'bucket_name': news_bucket_name,
                    'filename': filename,
                    'url' : f"{news.id}/{filename}",
                    'content_type': image_type[image.content_type],
                    'order': order
                })
            except KeyError:
                logger.warn(f"Unsupported image type: {image.content_type}")
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 
                    detail=f"Image type {image.content_type} is not supported. Supported types: JPEG, PNG, WEBP"
                )
            minio_tasks.append(
                asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self.minio_manager.save_obj_bytes_with_url,
                    news_bucket_name, 
                    f"{news.id}/{filename}",
                    content,
                    image.content_type
                )
            )
        await self.image_repository.bulk_create(db_records)
        await asyncio.gather(*minio_tasks)
        for image in upload_images:
            await image.seek(0)
        logger.debug(f"✅ Successfully uploaded {len(upload_images)} images to folder {news_folder}")
        return news

    async def get_all_news(self) -> List:
        news_list = await self.news_repository.get_all_with_image(order=1)
        if not news_list:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        serialize_news_list = []
        for news in news_list:
            news = await self._load_image(news)
            serialize_news = NewsSchema.model_validate(news).model_dump()
            serialize_news_list.append(serialize_news)
        return serialize_news_list

    async def get_news(self, news_id) -> dict:
        logger.debug(f"Get news {news_id}")
        logger.debug("Get news ogj...")
        news = await self.news_repository.get_with_image(news_id)
        if not news:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        await self._load_image(news)
        serialize_news = NewsSchema.model_validate(news).model_dump()
        return serialize_news
    
    async def update_news(
            self, 
            news_id : int, 
            title: Optional[str], 
            body: Optional[str], 
            upload_images: Optional[List[UploadFile]]
            ) -> None:
        logger.debug("Updated news ...")
        logger.debug(title)
        logger.debug(body)
        logger.debug(upload_images)
