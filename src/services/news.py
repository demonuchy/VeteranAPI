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
    
    async def _upload_images(
        self, 
        news_id: int, 
        upload_images: List[UploadFile], 
        bucket_name: str = "news-images"
    ) -> None:
        """Вспомогательный метод для загрузки изображений"""
        read_tasks = [image.read() for image in upload_images]
        files_content = await asyncio.gather(*read_tasks) 
        db_records = []
        minio_tasks = []
        current_max_order = await self.image_repository.get_max_order(news_id) or 0
        for order, (image, content) in enumerate(zip(upload_images, files_content), start=current_max_order + 1):
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
                    'news_id': news_id,
                    'bucket_name': bucket_name,
                    'filename': filename,
                    'url' : f"{news_id}/{filename}",
                    'content_type': image_type[image.content_type],
                    'order': order
                })
            except KeyError:
                logger.warning(f"Unsupported image type: {image.content_type}")
                continue
            object_path = f"{news_id}/{filename}"
            minio_tasks.append(
                asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self.minio_manager.save_obj_bytes_with_url,
                    bucket_name, 
                    f"{news_id}/{filename}",
                    content,
                    image.content_type
                )
            )
            logger.debug(f"Prepared to upload: {object_path}")
        if db_records:
            await self.image_repository.bulk_create(db_records)
            logger.debug(f"Added {len(db_records)} records to DB")
        if minio_tasks:
            await asyncio.gather(*minio_tasks)
            logger.debug(f"Uploaded {len(minio_tasks)} files to MinIO")
        for image in upload_images:
            await image.seek(0)

    
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
        if not upload_images:
            return news
        await self._upload_images(news_id=news.id, upload_images=upload_images)
        logger.debug(f"✅ Successfully uploaded {len(upload_images)}")
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
        news_id: int, 
        title: Optional[str], 
        body: Optional[str], 
        upload_images: Optional[List[UploadFile]]
    ) -> None:
        # 1. Обновляем текстовые поля новости
        await self.news_repository.update(news_id, title=title, body=body)
        if upload_images is not None:
            bucket_name = "news-images"
            current_file_paths = self.minio_manager.list_objects(bucket_name, prefix=f"{news_id}/")
            current_filenames = [os.path.basename(f) for f in current_file_paths]
            new_filenames = [file.filename for file in upload_images if file.filename]
            files_to_remove = [f for f in current_filenames if f not in new_filenames]
            files_to_add = [f for f in upload_images if f.filename and f.filename not in current_filenames]
            logger.debug(f"Current files: {current_filenames}")
            logger.debug(f"New files: {new_filenames}")
            logger.debug(f"Files to remove: {files_to_remove}")
            logger.debug(f"Files to add: {[f.filename for f in files_to_add]}")
            for filename in files_to_remove:
                object_path = f"{news_id}/{filename}"
                try:
                    self.minio_manager.delete_obj(bucket_name, object_path)
                    logger.debug(f"Removed from MinIO: {object_path}")
                    await self.image_repository.delete_by_filename(news_id, filename)
                    logger.debug(f"Deleted from DB: {filename}")
                except Exception as e:
                    logger.error(f"Error removing {filename}: {e}")
            if files_to_add:
                await self._upload_images(news_id, files_to_add, bucket_name)
        logger.debug(f"✅ News {news_id} updated successfully")

   


