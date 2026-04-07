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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_path = os.path.join(current_dir, "my_templates")
        
        #print(f"Current file location: {current_dir}")
        #print(f"Templates path: {templates_path}")
        #print(f"Templates path exists: {os.path.exists(templates_path)}")
        #print(f"sqladmin subdir exists: {os.path.exists(os.path.join(templates_path, 'sqladmin'))}")
        #print(f"create.html exists: {os.path.exists(os.path.join(templates_path, 'sqladmin', 'create.html'))}")
        
        self.admin = Admin(
            app, 
            engine, 
            title="Veterans Admin", 
            base_url="/api/v2/admin", 
            authentication_backend=AuthBackend(secret_key=config.ADMIN_SECRET_TOKEN),
            templates_dir=templates_path
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
