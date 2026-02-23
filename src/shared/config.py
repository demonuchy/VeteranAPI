# config.py
import os
from pydantic import ConfigDict
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).parent.parent.parent
ENV_PATH = BASE_DIR/".env"

print(ENV_PATH)

class Config(BaseSettings):
    """
    Основне переменные окружения проекта
    """
    DB_NAME : str
    DB_USER : str
    DB_PASS : str
    DB_HOST : str
    DB_PORT : str
    DB_CONTAINER_NAME : str

    JWT_KID : str
    JWT_SECRET_KEY : str
    JWT_ALGORITHM : str 
    JWT_ACCESS_EXPIRE_MINUTES : int 
    JWT_REFRESH_EXPIRE_MINUTES : int 

    REDIS_HOST : str 
    REDIS_PORT : str 
    REDIS_PASS : str
    REDIS_CONTAINER_NAME : str 

    MINIO_HOST : str
    MINIO_CONTAINER_NAME : str
    MINIO_USERNAME : str
    MINIO_PASSWORD : str

    ADMIN_SECRET_TOKEN : str

    TOKEN_CEANUP_INTERVAL : int
    TOKEN_CLEANUP_BATCH : int
        
    @property
    def DatabaseUrl(self):
        host = self.DB_HOST
        if os.getenv('IN_DOCKER'):
            host = self.DB_CONTAINER_NAME
        return  f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{host}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def RedisHost(self):
        host = self.REDIS_HOST
        if os.getenv('IN_DOCKER'):
            host = self.REDIS_CONTAINER_NAME
        return host
    
    @property
    def MinioHost(self):
        host = self.MINIO_HOST
        if os.getenv('IN_DOCKER'):
            host = self.MINIO_CONTAINER_NAME
        return host
    
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False, 
        extra="ignore"
    )

config = Config()