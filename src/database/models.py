from typing import List
from datetime import datetime
from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs


from .fields import Role, ImageType, TokenType, PK, CreatedAt, UpdatedAt


class Base(AsyncAttrs, DeclarativeBase):
    """Абстрактная базовая модель"""
    __abstract__ = True


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id : Mapped[PK]

    username : Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hash_password :  Mapped[str] = mapped_column(String, unique=False, nullable=False)

    is_active : Mapped[bool] = mapped_column(Boolean, unique=False, nullable=False, default=True)
    role : Mapped['Role'] = mapped_column(Enum(Role), unique=False, nullable=False, default=Role.USER)

    created_at : Mapped[CreatedAt]
    updated_at : Mapped[UpdatedAt]


class Token(Base):
    """Модель для учета токена"""
    __tablename__ = "tokens"
    id : Mapped[PK]
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_role : Mapped['Role'] = mapped_column(Enum(Role), unique=False, nullable=False, default=Role.USER)

    jti : Mapped[str] = mapped_column(String, unique=True, nullable=False)
    exp : Mapped[datetime] = mapped_column(DateTime, unique=False, nullable=False)
    token_type : Mapped['TokenType'] = mapped_column(Enum(TokenType), unique=False, nullable=False)
    
    ip_address : Mapped[str] = mapped_column(String, unique=False, nullable=False)
    device_id : Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    is_active : Mapped[bool] = mapped_column(Boolean, unique=False, nullable=False, default=True)
    is_rework : Mapped[bool] = mapped_column(Boolean, unique=False, nullable=False, default=False)
    created_at : Mapped[CreatedAt]


class News(Base):
    """Модель новости"""
    __tablename__ = "news"

    id : Mapped[PK]
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title : Mapped[str] = mapped_column(String(200), unique=False, nullable=False)
    body : Mapped[str] = mapped_column(String, unique=False, nullable=False)
    views : Mapped[int] = mapped_column(Integer, unique=False, nullable=False, default=0)

    images: Mapped[List["NewsImages"]] = relationship(
        "NewsImages",
        back_populates="news",
        order_by="NewsImages.order",
        cascade="all, delete-orphan",
        lazy="selectin"  # Для быстрой загрузки при запросах
    )
    
    created_at : Mapped[CreatedAt]
    updated_at : Mapped[UpdatedAt]



class NewsImages(Base):
    """Модель для хранения изображений для новости"""
    __tablename__ = "news_images"

    id : Mapped[PK]
    news_id : Mapped[int] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), nullable=False, index=True)

    url : Mapped[str] = mapped_column(String, unique=False, nullable=False, default="/")
    filename : Mapped[str] = mapped_column(String, unique=True, nullable=False)
    bucket_name : Mapped[str] = mapped_column(String, unique=False, nullable=False)
    content_type : Mapped[ImageType] = mapped_column(Enum(ImageType), unique=False, nullable=False)

    width : Mapped[int] = mapped_column(Integer, unique=False, nullable=True)
    height : Mapped[int] = mapped_column(Integer, unique=False, nullable=True)

    order : Mapped[int] = mapped_column(Integer, unique=False, nullable=False, default=0)

    news: Mapped["News"] = relationship("News", back_populates="images")

    created_at : Mapped[CreatedAt]




class Comment(Base):
    """Модель коментария"""
    __tablename__ = "comments"

    id : Mapped[PK]
    new_id : Mapped[int] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), nullable=False)
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    body : Mapped[str] = mapped_column(String(1000), unique=False, nullable=False)

    created_at : Mapped[CreatedAt]