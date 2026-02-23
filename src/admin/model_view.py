# admin/views.py
from sqladmin import ModelView
from starlette.requests import Request
from typing import Any, Optional
from datetime import datetime

from database.models import User, Token, News, NewsImages, Comment
from database.fields import Role, TokenType, ImageType
from shared.logger.logger import logger


class UserAdmin(ModelView, model=User):
    """Админ-панель для пользователей"""
    
    # Заголовки
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    
    # Список отображаемых колонок
    column_list = [
        User.id,
        User.username,
        User.role,
        User.is_active,
        User.created_at,
        User.updated_at,
    ]
    
    # Колонки, которые можно сортировать
    column_sortable_list = [
        User.id,
        User.username,
        User.role,
        User.is_active,
        User.created_at,
    ]
    
    # Колонки для поиска
    column_searchable_list = [
        User.username,
    ]
    
    # Фильтры - УБРАНЫ!
    column_filters = []
    
    # Детальный просмотр
    column_details_list = [
        User.id,
        User.username,
        User.hash_password,
        User.role,
        User.is_active,
        User.created_at,
        User.updated_at,
    ]
    
    # Формы создания/редактирования
    form_columns = [
        User.username,
        User.hash_password,
        User.role,
        User.is_active,
    ]
    
    # Переименование колонок для отображения
    column_labels = {
        User.id: "ID",
        User.username: "Имя пользователя",
        User.hash_password: "Хеш пароля",
        User.role: "Роль",
        User.is_active: "Активен",
        User.created_at: "Дата создания",
        User.updated_at: "Дата обновления",
    }
    
    # Форматирование значений
    column_formatters = {
        User.role: lambda m, a: m.role.value if m.role else "-",
        User.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "-",
        User.updated_at: lambda m, a: m.updated_at.strftime("%d.%m.%Y %H:%M") if m.updated_at else "-",
        User.is_active: lambda m, a: "✅" if m.is_active else "❌",
    }
    
    # Форматирование в детальном просмотре
    column_details_formatters = {
        User.hash_password: lambda m, a: "***hidden***",
    }
    
    # Можно скрыть поле пароля при создании (лучше использовать отдельную форму)
    form_widget_args = {
        User.hash_password: {
            "readonly": True,  # Только для чтения, чтобы не меняли пароль вручную
        },
    }
    
    async def on_model_change(self, data: dict, model: User, is_created: bool, request: Request) -> None:
        logger.debug(f"Detect change {data}")
        if not is_created:
            data["role"]
        


class TokenAdmin(ModelView, model=Token):
    """Админ-панель для токенов"""
    
    name = "Токен"
    name_plural = "Токены"
    icon = "fa-solid fa-key"
    
    column_list = [
        Token.id,
        Token.user_id,
        Token.jti,
        Token.token_type,
        Token.exp,
        Token.ip_address,
        Token.is_active,
        Token.is_rework,
        Token.created_at,
    ]
    
    column_sortable_list = [
        Token.id,
        Token.user_id,
        Token.token_type,
        Token.exp,
        Token.is_active,
        Token.created_at,
    ]
    
    column_searchable_list = [
        Token.jti,
        Token.ip_address,
    ]
    
    # Фильтры - УБРАНЫ!
    column_filters = []
    
    column_labels = {
        Token.id: "ID",
        Token.user_id: "ID пользователя",
        Token.jti: "JTI",
        Token.token_type: "Тип токена",
        Token.exp: "Истекает",
        Token.ip_address: "IP адрес",
        Token.is_active: "Активен",
        Token.is_rework: "Перевыпущен",
        Token.created_at: "Дата создания",
    }
    
    column_formatters = {
        Token.token_type: lambda m, a: m.token_type.value if m.token_type else "-",
        Token.exp: lambda m, a: m.exp.strftime("%d.%m.%Y %H:%M") if m.exp else "-",
        Token.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "-",
        Token.is_active: lambda m, a: "✅" if m.is_active else "❌",
        Token.is_rework: lambda m, a: "✅" if m.is_rework else "❌",
    }
    
    # Запрещаем создание/редактирование токенов вручную
    can_create = False
    can_edit = False
    can_delete = True  # Можно удалять просроченные/невалидные токены


class NewsAdmin(ModelView, model=News):
    """Админ-панель для новостей"""
    
    name = "Новость"
    name_plural = "Новости"
    icon = "fa-solid fa-newspaper"
    
    column_list = [
        News.id,
        News.user_id,
        News.title,
        News.body,
        News.views,
        News.created_at,
        News.updated_at,
        "images_count",  # Кастомное поле
    ]
    
    column_sortable_list = [
        News.id,
        News.user_id,
        News.title,
        News.views,
        News.created_at,
        News.updated_at,
    ]
    
    column_searchable_list = [
        News.title,
        News.body,
    ]
    
    # Фильтры - УБРАНЫ!
    column_filters = []
    
    column_labels = {
        News.id: "ID",
        News.user_id: "ID автора",
        News.title: "Заголовок",
        News.body: "Текст",
        News.views: "Просмотры",
        News.images: "Изображения",
        News.created_at: "Дата создания",
        News.updated_at: "Дата обновления",
        "images_count": "Кол-во изображений",
    }
    
    # Кастомные форматеры
    column_formatters = {
        News.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "-",
        News.updated_at: lambda m, a: m.updated_at.strftime("%d.%m.%Y %H:%M") if m.updated_at else "-",
        "images_count": lambda m, a: len(m.images) if m.images else 0,
        News.body: lambda m, a: (m.body[:100] + "...") if len(m.body) > 100 else m.body,
    }
    
    # Детальный просмотр
    column_details_list = [
        News.id,
        News.user_id,
        News.title,
        News.body,
        News.views,
        News.images,
        News.created_at,
        News.updated_at,
    ]
    
    # Форма создания/редактирования
    form_columns = [
        News.user_id,
        News.title,
        News.body,
        News.views,
    ]
    
    # Экспорт данных
    can_export = True
    export_colums = [News.id, News.title, News.views, News.created_at]


class NewsImagesAdmin(ModelView, model=NewsImages):
    """Админ-панель для изображений новостей"""
    
    name = "Изображение"
    name_plural = "Изображения"
    icon = "fa-solid fa-image"
    
    column_list = [
        NewsImages.id,
        NewsImages.news_id,
        NewsImages.filename,
        NewsImages.bucket_name,
        NewsImages.content_type,
        NewsImages.width,
        NewsImages.height,
        NewsImages.order,
        NewsImages.created_at,
    ]
    
    column_sortable_list = [
        NewsImages.id,
        NewsImages.news_id,
        NewsImages.order,
        NewsImages.created_at,
        NewsImages.width,
        NewsImages.height,
    ]
    
    column_searchable_list = [
        NewsImages.filename,
        NewsImages.bucket_name,
    ]
    
    # Фильтры - УБРАНЫ!
    column_filters = []
    
    column_labels = {
        NewsImages.id: "ID",
        NewsImages.news_id: "ID новости",
        NewsImages.url: "URL",
        NewsImages.filename: "Имя файла",
        NewsImages.bucket_name: "Бакет",
        NewsImages.content_type: "Тип",
        NewsImages.width: "Ширина",
        NewsImages.height: "Высота",
        NewsImages.order: "Порядок",
        NewsImages.created_at: "Дата загрузки",
    }
    
    column_formatters = {
        NewsImages.content_type: lambda m, a: m.content_type.value if m.content_type else "-",
        NewsImages.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "-",
        NewsImages.url: lambda m, a: f"🔗 {m.url[:50]}..." if m.url and len(m.url) > 50 else m.url,
    }
    
    # Детальный просмотр
    column_details_list = [
        NewsImages.id,
        NewsImages.news_id,
        NewsImages.url,
        NewsImages.filename,
        NewsImages.bucket_name,
        NewsImages.content_type,
        NewsImages.width,
        NewsImages.height,
        NewsImages.order,
        NewsImages.created_at,
    ]
    
    # Форма создания/редактирования
    form_columns = [
        NewsImages.news_id,
        NewsImages.url,
        NewsImages.filename,
        NewsImages.bucket_name,
        NewsImages.content_type,
        NewsImages.width,
        NewsImages.height,
        NewsImages.order,
    ]


class CommentAdmin(ModelView, model=Comment):
    """Админ-панель для комментариев"""
    
    name = "Комментарий"
    name_plural = "Комментарии"
    icon = "fa-solid fa-comment"
    
    column_list = [
        Comment.id,
        Comment.new_id,
        Comment.user_id,
        Comment.body,
        Comment.created_at,
    ]
    
    column_sortable_list = [
        Comment.id,
        Comment.new_id,
        Comment.user_id,
        Comment.created_at,
    ]
    
    column_searchable_list = [
        Comment.body,
    ]
    
    # Фильтры - УБРАНЫ!
    column_filters = []
    
    column_labels = {
        Comment.id: "ID",
        Comment.new_id: "ID новости",
        Comment.user_id: "ID пользователя",
        Comment.body: "Текст",
        Comment.created_at: "Дата создания",
    }
    
    column_formatters = {
        Comment.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else "-",
        Comment.body: lambda m, a: (m.body[:100] + "...") if len(m.body) > 100 else m.body,
    }
    
    # Детальный просмотр
    column_details_list = [
        Comment.id,
        Comment.new_id,
        Comment.user_id,
        Comment.body,
        Comment.created_at,
    ]
    
    # Форма создания/редактирования
    form_columns = [
        Comment.new_id,
        Comment.user_id,
        Comment.body,
    ]


# Для удобства можно создать класс с настройками шаблонов
class AdminTheme:
    """Настройки темы для админ-панели"""
    
    # Настройки навигации
    navigation = [
        {"name": "Пользователи", "icon": "fa-users", "models": [UserAdmin]},
        {"name": "Контент", "icon": "fa-content", "models": [NewsAdmin, NewsImagesAdmin, CommentAdmin]},
        {"name": "Безопасность", "icon": "fa-shield", "models": [TokenAdmin]},
    ]