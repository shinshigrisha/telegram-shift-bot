import logging
import traceback
import asyncio
from typing import Optional

from aiogram import Bot

from config.settings import settings


logger = logging.getLogger(__name__)


class ErrorHandler:
    def __init__(self, bot: Optional[Bot] = None) -> None:
        self.bot = bot

    async def handle_error(self, error: Exception, context: str = "") -> None:
        """Обработка ошибки."""
        error_msg = f"Ошибка в {context}: {error}\n{traceback.format_exc()}"
        logger.error(error_msg)

        if self.bot and settings.ADMIN_IDS and settings.ENABLE_ADMIN_NOTIFICATIONS:
            # Отправляем уведомления всем админам параллельно
            async def notify_admin(admin_id: int) -> None:
                try:
                    await self.bot.send_message(
                        admin_id,
                        f"🚨 Ошибка в {context}:\n{error}",
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to send error notification to admin %s: %s", admin_id, e)
            
            await asyncio.gather(
                *[notify_admin(admin_id) for admin_id in settings.ADMIN_IDS],
                return_exceptions=True
            )

    async def handle_warning(self, warning: str, context: str = "") -> None:
        """Обработка предупреждения."""
        warning_msg = f"Предупреждение в {context}: {warning}"
        logger.warning(warning_msg)


