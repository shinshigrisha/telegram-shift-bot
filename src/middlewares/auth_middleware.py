from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import Message

from config.settings import settings


logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.text and event.text.startswith("/"):
            command = event.text.split()[0]

            admin_commands = [
                "/setup_ziz",
                "/add_group",
                "/remove_group",
                "/list_groups",
                "/stats",
                "/force_poll",
                "/manual_close",
                "/get_report",
                "/generate_all_reports",
                "/set_admin",
                "/remove_admin",
                "/configure_system",
                "/backup_db",
                "/test_screenshot",
                "/cleanup_old_data",
            ]

            if command in admin_commands:
                user_id = event.from_user.id

                if user_id not in settings.ADMIN_IDS:
                    await event.answer("⛔ У вас нет прав для выполнения этой команды")
                    return

        return await handler(event, data)


