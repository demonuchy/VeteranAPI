import enum
from typing import Annotated
from datetime import datetime
from sqlalchemy import String, BigInteger, Boolean, DateTime, Enum, func
from sqlalchemy.orm import mapped_column


class TokenType(enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class ImageType(enum.Enum):
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"


class Role(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    ROOT = "root"


PK = Annotated[int, mapped_column(BigInteger, primary_key=True, autoincrement=True)]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
UpdatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())]