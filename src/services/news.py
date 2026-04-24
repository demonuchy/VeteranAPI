import os
from weakref import WeakKeyDictionary
import base64
import threading
import asyncio
import uuid
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Self

from concurrent.futures import ThreadPoolExecutor

from database.fields import ImageType
from database.base import BaseSQLAlchemyRepository
from utils.minio_manger import AbstractMinioManager
from utils.elasticsearch_manager import AbstractElasticsearchManager
from schemas.news import NewsSchema, CropedNewsShema
from shared.logger.logger import logger

from .base import BaseService


class NewsService(BaseService):    
    def __init__(self, 
                 session : AsyncSession,
                 news_repository : BaseSQLAlchemyRepository, 
                 image_repository : BaseSQLAlchemyRepository,
                 comment_repository : BaseSQLAlchemyRepository,
                 news_like_repository : BaseSQLAlchemyRepository,
                 minio_manager : AbstractMinioManager, 
                 elasticsearch_manager : AbstractElasticsearchManager
                 ):
        super().__init__(session=session)
        self._news_repository = news_repository
        self._comment_repository = comment_repository
        self._image_repository = image_repository
        self._news_like_repository = news_like_repository
        self._minio_manager = minio_manager
        self._elasticsearch_manager = elasticsearch_manager

    @property
    def news_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._news_repository, self._session)

    @property
    def image_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._image_repository, self._session)

    @property
    def minio_manager(self) -> AbstractMinioManager:
        return self._get_depends(self._minio_manager)
    
    @property
    def comment_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._comment_repository, self._session)

    @property
    def news_like_repository(self) -> BaseSQLAlchemyRepository:
        return self._get_depends(self._news_like_repository, self._session)
    
    @property
    def elasticsearch_manager(self) -> AbstractElasticsearchManager:
       return self._get_depends(self._elasticsearch_manager)
        
    async def _load_image(self, news) -> None:     
        for image in news.images:
            image_bytes = await asyncio.to_thread(
                self.minio_manager.get_obj,
                image.bucket_name,
                image.url,
            )
            logger.debug("Image loaded")
            image.base64 = f"data:{image.content_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"

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
                asyncio.to_thread(
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

    async def _delete_images(
            self, 
            files_name : List[str], 
            bucket_name : str = "news-images", 
            prefix : Optional[str] = "", 
            with_db : bool = False
            ) -> None:
        minio_task = []
        db_task = []
        for file in files_name:
            path = file
            if prefix:
                path = f"{prefix}/{file}"
            minio_task.append(asyncio.to_thread(
                self.minio_manager.delete_obj, 
                bucket_name,
                path
                ))
            if with_db:
                logger.debug(f"Delete image in database file : {file}")
                db_task.append(self.image_repository.delete_by_field("filename", file))
        await asyncio.gather(*minio_task)
        if db_task: await asyncio.gather(*db_task)

    async def delete_news(self, news_id) -> None:
        """Удаление новости"""
        logger.debug(f"Delete news {news_id}")
        news = await self.news_repository.get_with_image(news_id)
        logger.debug("Delete image from file storage")
        await self._delete_images(bucket_name="news-images", files_name=[file.url for file in news.images])
        logger.debug("Delete news..")
        await self.news_repository.delete(news_id)
        logger.debug("✅ News deleted...")
    
    async def create_news(
            self, 
            user_id, 
            title: str, 
            body: str, 
            upload_images: List[UploadFile], 
    ) -> None:
        """Создание новости"""
        try:
            logger.debug("Publish news...")
            news = await self.news_repository.create(
                user_id=user_id, 
                title=title, 
                body=body
            )
            logger.debug("Save to elasticsearch")
            if not upload_images:
                return news
            await self._upload_images(news_id=news.id, upload_images=upload_images)
            logger.debug(f"✅ Successfully uploaded {len(upload_images)}")
            return news
        except:
            logger.warn("Error rollback ...")
            raise

    async def stream_load_chunk(self, bucket_name: str, object_name: str):
        async def _stream():
            logger.debug(f"Начало стриминга изображения: {object_name}")
            queue = asyncio.Queue(maxsize=5)
            loop = asyncio.get_event_loop()
            def _read_and_put():
                logger.debug(f"Запущен поток чтения для: {object_name}")
                response = None
                try:
                    logger.debug(f"Получаем объект из MinIO: {bucket_name}/{object_name}")
                    response = self.client.get_object(bucket_name, object_name)
                    logger.debug(f"Объект получен, начинаем чтение чанками")
                    chunk_count = 0
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            logger.debug(f"Чтение завершено, прочитано {chunk_count} чанков")
                            break
                        chunk_count += 1
                        logger.debug(f"Прочитан чанк {chunk_count}, размер {len(chunk)} байт")
                        future = asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                        future.result()
                        logger.debug(f"Чанк {chunk_count} положен в очередь")
                except Exception as e:
                    logger.error(f"Ошибка при чтении: {e}")
                    asyncio.run_coroutine_threadsafe(queue.put(e), loop).result()
                finally:
                    if response:
                        response.close()
                        response.release_conn()
                        logger.debug(f"Соединение закрыто")
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
                    logger.debug(f"Отправлен сигнал завершения (None)")
            threading.Thread(target=_read_and_put, daemon=True).start()
            logger.debug(f"Поток чтения запущен, начинаем вычитывать из очереди")
            chunk_index = 0
            while True:
                chunk = await queue.get()
                if chunk is None:
                    logger.debug(f"Получен сигнал завершения, выходим из цикла")
                    break
                if isinstance(chunk, Exception):
                    logger.error(f"Получено исключение: {chunk}")
                    raise chunk
                chunk_index += 1
                logger.debug(f"Отдаем чанк {chunk_index}, размер {len(chunk)} байт")
                yield chunk
            logger.debug(f"Стриминг завершен, отправлено {chunk_index} чанков")
        return _stream

    async def get_all_news(self) -> List:
        news_list = await self.news_repository.get_all_with_image(order=1)
        if not news_list:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        serialize_news_list = []
        for news in news_list:
            await self._load_image(news)
            serialize_news = CropedNewsShema.model_validate(news).model_dump()
            serialize_news_list.append(serialize_news)
        return serialize_news_list
    
    async def get_all_news_with_stream(self, version_api = "v2") -> List:
        news_list = await self.news_repository.get_all_with_image_optimize()
        if not news_list:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        serialize_news_list = []
        for news in news_list:
            serialize_news = CropedNewsShema.model_validate(news)
            if serialize_news.images:
                serialize_news.images = serialize_news.images[:1]
                serialize_news.images[0].url = f"/api/{version_api}/news/{serialize_news.id}/image/{serialize_news.images[0].id}"
            serialize_news_list.append(serialize_news.model_dump())
        return serialize_news_list

    async def get_news(self, news_id) -> dict:
        logger.debug(f"Get news {news_id}")
        logger.debug("Get news ogj...")
        news = await self.news_repository.get_with_image_comment(news_id)
        if not news:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        await self._load_image(news)
        serialize_news = NewsSchema.model_validate(news).model_dump()
        return serialize_news
    
    async def get_news_with_stream(self, news_id, version_api = "v2") -> dict:
        logger.debug(f"Get news {news_id}")
        logger.debug("Get news ogj...")
        news = await self.news_repository.get_with_image_comment(news_id)
        if not news:
            logger.warn("News not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
        logger.debug("Load images ...")
        serialize_news = NewsSchema.model_validate(news)
        logger.debug(f"News {serialize_news.model_dump()}")
        for image in serialize_news.images:
            image.url = f"/api/{version_api}/news/{news_id}/image/{image.id}"
        return serialize_news.model_dump()
    
    async def update_news(
        self, 
        news_id: int, 
        title: Optional[str], 
        body: Optional[str], 
        upload_images: Optional[List[UploadFile]]
    ) -> None:
        logger.debug(f"Update news id : {news_id}")
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


    async def update_news_optimized(
            self, 
            news_id : int, 
            title : Optional[str], 
            body : Optional[str], 
            remove_images : Optional[List[str]], 
            upload_images : Optional[List[UploadFile]]
            ) -> None:
        logger.debug(f"Remove images : {remove_images}")
        if title is not None:
            await self.news_repository.update(news_id, title=title)
        if body is not None:
            await self.news_repository.update(news_id, body=body)
        if remove_images is not None:
            logger.debug("Remove exeting image")
            await self._delete_images(files_name=remove_images, prefix=str(news_id), with_db=True)
        if upload_images is not None:
            logger.debug("Upload image")
            await self._upload_images(news_id=news_id, upload_images=upload_images)

    async def leave_comment(
            self, 
            user_id : int, 
            news_id : int, 
            content : str
        ) -> None:
        logger.debug(f"Leave comment user {user_id}")
        await self.comment_repository.create(user_id=user_id, news_id=news_id, body=content)
        logger.debug(f"Leave comment sucsess")
        
    async def delete_comment(
            self, 
            user_id : int, 
            comment_id : int
        )-> None:
        logger.debug(f"Delete comment user {user_id} comment {comment_id}")
        await self.comment_repository.delete(id=comment_id)
        logger.debug(f"Delete comment sucsess")

    async def like_news(self, news_id : int, user_id : int) -> None:
        logger.debug(f"Like news id : {news_id}")
        await self.news_repository.increment_likes(news_id)
        await self .news_like_repository.create(news_id=news_id, user_id=user_id)
        logger.debug(f"News like success")

   



