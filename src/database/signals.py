from sqlalchemy import event
from .models import User
from shared.logger.logger import logger


@event.listens_for(User, 'after_update')
def news_before_update(mapper, connection, target):
    """
    Срабатывает перед обновлением новости
    target - экземпляр News который будет обновлен
    """
    logger.debug(f"🔄 News before_update: ID={target.id}, Title={target.title}")
    