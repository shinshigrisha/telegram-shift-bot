import logging
import traceback
from typing import Optional

from aiogram import Bot

from config.settings import settings


logger = logging.getLogger(__name__)


class ErrorHandler:
    def __init__(self, bot: Optional[Bot] = None) -> None:
        self.bot = bot

    async def handle_error(self, error: Exception, context: str = "") -> None:
        """Обработка ошибки."""
        error_msg = f"Error in {context}: {error}\n{traceback.format_exc()}"
        logger.error(error_msg)

        if self.bot and settings.ADMIN_IDS:
            for admin_id in settings.ADMIN_IDS:
                try:
                    await self.bot.send_message(
                        admin_id,
                        f"🚨 Ошибка в {context}:\n{error}",
                    )
                except Exception:  # noqa: BLE001
                    continue

    async def handle_warning(self, warning: str, context: str = "") -> None:
        """Обработка предупреждения."""
        warning_msg = f"Warning in {context}: {warning}"
        logger.warning(warning_msg)


