import os
import sys
from sqladmin import Admin, ModelView
from typing import List, Type


from .model_view import UserAdmin, TokenAdmin, NewsAdmin, NewsImagesAdmin, CommentAdmin
from .auth import AuthBackend
from shared.config import config

class AdminSetup:
    """Класс управления админ панелью и представлениями"""
    def __init__(self, app, engine):
        self.admin = Admin(
            app, 
            engine, 
            title="Veterans Admin", 
            base_url="/api/v2/admin", 
            authentication_backend=AuthBackend(secret_key=config.ADMIN_SECRET_TOKEN)
            )
        self._custom_views: List[Type[ModelView]] = [
            UserAdmin, 
            TokenAdmin, 
            NewsAdmin, 
            NewsImagesAdmin, 
            CommentAdmin
            ]
        self._setup_views()

    def _setup_views(self):
        """Настройка всех View для админки"""
        for view in self._custom_views:
            self.admin.add_view(view)
