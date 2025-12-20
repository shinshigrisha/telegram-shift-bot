from typing import Iterable
import asyncio
import logging

from aiogram import Bot

from config.settings import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений администраторам и в чаты."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def notify_admins(self, text: str) -> None:
        """Отправить уведомление всем админам параллельно."""
        if not settings.ADMIN_IDS:
            return
        
        async def send_to_admin(admin_id: int) -> None:
            """Отправить сообщение одному админу."""
            try:
                await self.bot.send_message(admin_id, text)
            except Exception as e:
                logger.warning("Failed to send notification to admin %s: %s", admin_id, e)
        
        # Отправляем всем админам параллельно
        await asyncio.gather(
            *[send_to_admin(admin_id) for admin_id in settings.ADMIN_IDS],
            return_exceptions=True
        )

    async def send_reminders(self) -> None:
        """Заглушка для рассылки напоминаний пользователям."""
        await self.notify_admins("⏰ Отправка напоминаний (заглушка).")


