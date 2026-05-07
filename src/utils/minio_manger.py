import io
import asyncio
import threading
import os
import uuid
from functools import wraps
from datetime import timedelta
from abc import ABC, abstractmethod
from minio import Minio
from minio.error import S3Error
from typing import BinaryIO, AsyncGenerator, Optional, List, Callable
from aiobotocore.session import get_session, ClientCreatorContext
from botocore.exceptions import ClientError
from contextlib import asynccontextmanager
from fastapi import HTTPException, status, UploadFile
from concurrent.futures import ThreadPoolExecutor


from shared.logger.logger import logger
from shared.config import config

class AbstractMinioManager(ABC):
    def __init__(
        self,
        endpoint: str = f"{config.MinioHost}:9000",
        access_key: str = config.MINIO_USERNAME,
        secret_key: str = config.MINIO_PASSWORD,
        secure: bool = False
    ):
        """
        Инициализация Minio клиента
        
        Args:
            endpoint: Адрес Minio сервера
            access_key: Ключ доступа
            secret_key: Секретный ключ
            secure: Использовать HTTPS
        """
        self._client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
    
    @property
    def client(self) -> Minio:
        """Геттер для Minio клиента"""
        return self._client
    
    @abstractmethod
    def save_obj(
        self, 
        bucket_name: str, 
        object_name: str, 
        source_file: str
        ) -> bool:
        """
        Сохранение объекта в Minio
        
        Args:
            bucket_name: Имя бакета
            object_name: Имя файла в Minio
            source_file: Путь к исходному файлу
            
        Returns:
            bool: Успешно ли сохранение
        """
        pass

    @abstractmethod
    def save_obj_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """
        Сохранение объекта в Minio
        
        Args:
            bucket_name: Имя бакета
            object_name: Имя файла в Minio
            source_file: Путь к исходному файлу
            data : Байты
            content_type : Тип
            
        Returns:
            bool: Успешно ли сохранение
        """
        pass
    
    @abstractmethod
    def get_obj(self, bucket_name: str, object_name: str) -> bytes:
        """
        Получение объекта из Minio
        
        Args:
            bucket_name: Имя бакета
            object_name: Имя объекта в Minio
            file_path: Путь для сохранения файла
            
        Returns:
            bool: Успешно ли получение
        """
        pass

    @abstractmethod
    def delete_obj(self, bucket_name: str, object_name: str) -> bool:
        pass

    @abstractmethod
    def delete_objects_by_prefix(self, bucket_name: str, prefix: str) -> int:
        """
        Удаление всех объектов с определенным префиксом (папкой)
        
        Args:
            bucket_name: Имя бакета (например "news-images")
            prefix: Префикс (например "15/" для удаления папки 15)
        
        Returns:
            int: Количество удаленных объектов
        """


class MinioManager(AbstractMinioManager):
    def __init__(
        self,
        endpoint: str = f"{config.MinioHost}:9000",
        access_key: str = config.MINIO_USERNAME,
        secret_key: str = config.MINIO_PASSWORD,
        secure: bool = False
    ):
        super().__init__(endpoint, access_key, secret_key, secure)
    
    def save_obj(
        self,
        bucket_name: str,
        object_name: str,
        source_file: str,
        content_type: str = "application/octet-stream"
    ) -> bool:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.debug(f"Бакет '{bucket_name}' создан")
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=source_file,
                content_type=content_type
            )
            logger.debug(f"Файл '{source_file}' успешно загружен как '{object_name}' в бакет '{bucket_name}'")
            return True
        except S3Error as e:
            logger.warn(f"Ошибка при сохранении файла в Minio: {e}")
            raise
        except FileNotFoundError:
            logger.warn(f"Файл не найден: {source_file}")
            raise
        except Exception as e:
            logger.warn(f"Неизвестная ошибка: {e}")
            raise
    
    def get_obj(self, bucket_name: str, object_name: str) -> bytes:
        try:
            response = self.client.get_object(
            bucket_name=bucket_name,
            object_name=object_name
            )
            data = response.read()
            response.close()
            response.release_conn()
            logger.debug(f"Файл '{object_name}' успешно прочитан ({len(data)} байт)")
            return data
        except S3Error as e:
            logger.warn(f"Ошибка при получении файла из Minio: {e}")
            raise
        except Exception as e:
            logger.warn(f"Неизвестная ошибка: {e}")
            raise

    def get_image_url(self, bucket_name: str, news_id: int, filename: str) -> str:
        """Получение URL изображения"""
        try:
            object_path = f"{news_id}/{filename}"
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_path,
                expires=timedelta(hours=1)  # Ссылка действительна 1 час
            )
            return url
        except Exception as e:
            logger.error(f"Error getting image URL: {e}")
            return None

    def save_obj_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
            data_stream = io.BytesIO(data)
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.debug(f"Данные успешно загружены как '{object_name}' в бакет '{bucket_name}'")
            return True      
        except S3Error as e:
            logger.warn(f"Ошибка при сохранении байтов в Minio: {e}")
            raise
        except Exception as e:
            logger.warn(f"Неизвестная ошибка: {e}")
            raise

    def save_obj_bytes_with_url(
        self,
        bucket_name: str,
        object_path: str,  
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.debug(f"Created bucket: {bucket_name}")
            data_stream = io.BytesIO(data)
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_path, 
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.debug(f"✅ Successfully uploaded to {bucket_name}/{object_path}")
            return True
        except S3Error as e:
            logger.error(f"MinIO S3 error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error while saving to MinIO: {e}")
            raise
    
    def list_objects(self, bucket_name: str, prefix: str = "") -> list:
        try:
            if not self.client.bucket_exists(bucket_name):
                return []   
            objects = self.client.list_objects(bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.warn(f"Ошибка при получении списка объектов: {e}")
            raise
    
    def delete_obj(self, bucket_name: str, object_name: str) -> bool:
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.debug(f"Объект '{object_name}' удален из бакета '{bucket_name}'")
            return True
        except S3Error as e:
            logger.warn(f"Ошибка при удалении объекта: {e}")
            raise

    def delete_objects_by_prefix(self, bucket_name: str, prefix: str) -> int:
        """
        Удаление всех объектов с определенным префиксом (папкой)
        
        Args:
            bucket_name: Имя бакета (например "news-images")
            prefix: Префикс (например "15/" для удаления папки 15)
        
        Returns:
            int: Количество удаленных объектов
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                logger.warning(f"Bucket '{bucket_name}' does not exist")
                return 0
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            objects_to_remove = [obj.object_name for obj in objects]
            if objects_to_remove:
                self.client.remove_objects(bucket_name, objects_to_remove)
                logger.debug(f"Deleted {len(objects_to_remove)} objects from '{prefix}' in bucket '{bucket_name}'")
            else:
                logger.debug(f"No objects found with prefix '{prefix}'")
            return len(objects_to_remove)
        except S3Error as e:
            logger.error(f"Error deleting objects with prefix '{prefix}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

class AsyncMinIOManager:
    def __init__(
        self,
        bucket_name: str,
        endpoint: str = f"{config.MinioHost}:9000",
        access_key: str = config.MINIO_USERNAME,
        secret_key: str = config.MINIO_PASSWORD,
        secure: bool = False,
        region: str = "us-east-1"
    ):
        """
        Асинхронный менеджер для работы с MinIO используя aiobotocore
        
        Args:
            bucket_name: Имя бакета по умолчанию
            endpoint: Адрес Minio сервера
            access_key: Ключ доступа
            secret_key: Секретный ключ
            secure: Использовать HTTPS
            region: Регион (для совместимости с S3 API)
        """
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.region = region
        self.endpoint_url = f"{'https' if secure else 'http'}://{endpoint}"

    @staticmethod
    def with_client(func: Callable) -> Callable:
        """Декоратор для методов, которым нужен клиент"""
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if kwargs.get("client") is not None:
                return await func(self, *args, **kwargs)
            async with self._get_client() as client:
                return await func(self, client, *args, **kwargs)
        return wrapper
  
    def _get_session_config(self):
        """Получение конфигурации для сессии"""
        return {
            'aws_access_key_id': self.access_key,
            'aws_secret_access_key': self.secret_key,
            'endpoint_url': self.endpoint_url,
            'region_name': self.region,
        }
    
    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[ClientCreatorContext, None]:
        """Контекстный менеджер для получения S3 клиента"""
        session = get_session()
        async with session.create_client('s3', **self._get_session_config()) as client:
            yield client
    
    @with_client
    async def bucket_exists(self, client, bucket_name: Optional[str] = None) -> bool:
        """Проверка существования бакета"""
        bucket = bucket_name or self.bucket_name
        try:
            await client.head_bucket(Bucket=bucket)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            logger.error(f"Error checking bucket existence: {e}")
            raise
      
    @with_client
    async def make_bucket(self, client, bucket_name: Optional[str] = None):
        """Создание бакета"""
        bucket = bucket_name or self.bucket_name
        try:
            await client.create_bucket(Bucket=bucket)
            logger.debug(f"Bucket '{bucket}' created successfully")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.debug(f"Bucket '{bucket}' already exists")
            else:
                logger.error(f"Error creating bucket: {e}")
                raise

    @staticmethod
    async def generate_filename(file : UploadFile) -> None:
        if not file.filename:
            return f"{uuid.uuid4()}.jpg"
        name, ext = os.path.splitext(file.filename)
        return f"{name}_{uuid.uuid4()}{ext}"
    
    @with_client
    async def save_obj(
        self,
        client,
        object_name: str,
        source_file: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Сохранение файла в MinIO
        Args:
            object_name: Имя файла в MinIO
            source_file: Путь к исходному файлу
            bucket_name: Имя бакета (если не указан, используется default)
            content_type: MIME тип файла
        """
        bucket = bucket_name or self.bucket_name
        try:
            with open(source_file, 'rb') as file_data:
                await client.put_object(
                    Bucket=bucket,
                    Key=object_name,
                    Body=file_data,
                    ContentType=content_type
                )
            logger.debug(f"File '{source_file}' uploaded as '{object_name}' to bucket '{bucket}'")
        except ClientError as e:
            logger.error(f"Error saving file to MinIO: {e}")
            raise
        except FileNotFoundError:
            logger.error(f"File not found: {source_file}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

    @with_client
    async def save_obj_bytes(
        self,
        client,
        object_name: str,
        data: bytes,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Сохранение байтов в MinIO
        
        Args:
            object_name: Имя файла в MinIO
            data: Байты для сохранения
            bucket_name: Имя бакета (если не указан, используется default)
            content_type: MIME тип файла
        """
        bucket = bucket_name or self.bucket_name
        try:
            data_stream = io.BytesIO(data)
            await client.put_object(
                Bucket=bucket,
                Key=object_name,
                Body=data_stream,
                ContentType=content_type
            )
            logger.debug(f"Data uploaded as '{object_name}' to bucket '{bucket}' ({len(data)} bytes)")  
        except ClientError as e:
            logger.error(f"Error saving bytes to MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

    @with_client
    async def get_obj(
        self,
        client,
        object_name: str,
        bucket_name: Optional[str] = None
    ) -> bytes:
        """
        Получение объекта из MinIO
        
        Args:
            object_name: Имя объекта в MinIO
            bucket_name: Имя бакета (если не указан, используется default)
        
        Returns:
            bytes: Содержимое объекта
        """
        bucket = bucket_name or self.bucket_name
        try:
            response = await client.get_object(
                Bucket=bucket,
                Key=object_name
            )
            data = await response['Body'].read()
            await response['Body'].close()
            logger.debug(f"Object '{object_name}' retrieved from bucket '{bucket}' ({len(data)} bytes)")
            return data
        except ClientError as e:
            logger.error(f"Error getting object from MinIO: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

    @with_client
    async def delete_obj(
        self,
        client,
        object_name: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """
        Удаление объекта из MinIO
        
        Args:
            object_name: Имя объекта в MinIO
            bucket_name: Имя бакета (если не указан, используется default)
        """
        bucket = bucket_name or self.bucket_name 
        try:
            await client.delete_object(
                Bucket=bucket,
                Key=object_name
            )
            logger.debug(f"Object '{object_name}' deleted from bucket '{bucket}'")
            return True
        except ClientError as e:
            logger.error(f"Error deleting object: {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

    @with_client
    async def delete_objects_by_prefix(
        self,
        client,
        prefix: str,
        bucket_name: Optional[str] = None,
        batch_size = 1000
    ) -> int:
        """
        Удаление всех объектов с определенным префиксом
        
        Args:
            prefix: Префикс для удаления
            bucket_name: Имя бакета (если не указан, используется default)
        
        Returns:
            int: Количество удаленных объектов
        """
        bucket = bucket_name or self.bucket_name
        try:
            if not await self.bucket_exists(client=client, bucket_name=bucket):
                logger.warning(f"Bucket '{bucket}' does not exist")
                return 0
            objects_to_delete = []
            paginator = client.get_paginator('list_objects_v2')
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects_to_delete.append({'Key': obj['Key']})
            if objects_to_delete:
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i+1000]
                    await client.delete_objects(
                        Bucket=bucket,
                        Delete={'Objects': batch, 'Quiet': True}
                    )
                logger.debug(f"Deleted {len(objects_to_delete)} objects with prefix '{prefix}' from bucket '{bucket}'")
            else:
                logger.debug(f"No objects found with prefix '{prefix}'")
            return len(objects_to_delete)
        except ClientError as e:
            logger.error(f"Error deleting objects with prefix '{prefix}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            raise

    @with_client
    async def list_objects(
        self,
        client,
        prefix: str = "",
        bucket_name: Optional[str] = None
    ) -> List[str]:
        """
        Получение списка объектов в бакете
        
        Args:
            prefix: Префикс для фильтрации
            bucket_name: Имя бакета (если не указан, используется default)
        
        Returns:
            List[str]: Список имен объектов
        """
        bucket = bucket_name or self.bucket_name
        try:
            if not await self.bucket_exists(client, bucket):
                return []
            objects = []
            paginator = client.get_paginator('list_objects_v2')
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append(obj['Key'])
            
            logger.debug(f"Listed {len(objects)} objects in bucket '{bucket}' with prefix '{prefix}'")
            return objects
        except ClientError as e:
            logger.error(f"Error listing objects: {e}")
            raise

    async def stream_load_chunk(
        self,
        object_name: str,
        bucket_name: str | None = None,
        chunk_size: int = 60 * 1024  # 64 KB
    )-> AsyncGenerator[bytes, None]:
        """
        Асинхронный генератор для потокового чтения файла из MinIO.
          Args:
            object_name: Имя объекта в MinIO
            file_obj: Файловый объект (BinaryIO), открытый в режиме 'rb'
            bucket_name: Имя бакета (если не указан, используется default)
            chunk_size: Размер чанка
        Yield:
           chunk
        """
        bucket = bucket_name or self.bucket_name
        async with self._get_client() as client:
            response = await client.get_object(
                Bucket=bucket,
                Key=object_name
            )
            async for chunk in response['Body'].iter_chunks(chunk_size):
                yield chunk

    @with_client
    async def stream_upload_chunk(
        self,
        client,
        object_name: str,
        file_obj: BinaryIO,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Загрузка файла в MinIO с использованием встроенного метода upload_fileobj.
        Aiobotocore автоматически использует multipart upload для больших файлов.
        
        Args:
            object_name: Имя объекта в MinIO
            file_obj: Файловый объект (BinaryIO), открытый в режиме 'rb'
            bucket_name: Имя бакета (если не указан, используется default)
            content_type: MIME тип файла
        
        Returns:
           None
        """
        bucket = bucket_name or self.bucket_name
        file_content = file_obj.read()
        await client.put_object(
            Body=file_content,
            Bucket=bucket,
            Key=object_name,
            ContentType = content_type
        )
        logger.debug(f"File successfully uploaded to {bucket}/{object_name}")
   
  