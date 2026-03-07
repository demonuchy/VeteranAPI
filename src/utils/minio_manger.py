import io
from datetime import timedelta
from abc import ABC, abstractmethod
from minio import Minio
from minio.error import S3Error
from typing import BinaryIO
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