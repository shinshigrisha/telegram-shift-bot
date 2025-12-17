from typing import Iterable

from aiogram import Bot

from config.settings import settings


class NotificationService:
    """Сервис для отправки уведомлений администраторам и в чаты."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def notify_admins(self, text: str) -> None:
        for admin_id in settings.ADMIN_IDS:
            try:
                await self.bot.send_message(admin_id, text)
            except Exception:
                # Не валим всё приложение из-за одного админа
                continue

    async def send_reminders(self) -> None:
        """Заглушка для рассылки напоминаний пользователям."""
        await self.notify_admins("⏰ Отправка напоминаний (заглушка).")


