from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import Bot, BaseMiddleware
from aiogram.types import TelegramObject

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository
from src.repositories.screenshot_check_repository import ScreenshotCheckRepository
from src.services.group_service import GroupService
from src.services.user_service import UserService
from src.services.poll_service import PollService


class DatabaseMiddleware(BaseMiddleware):
    """Создает сессию БД и основные сервисы на время обработки апдейта."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            user_repo = UserRepository(session)
            screenshot_check_repo = ScreenshotCheckRepository(session)
            group_service = GroupService(session)
            user_service = UserService(session)
            
            # Получаем bot и screenshot_service для создания PollService
            bot: Optional[Bot] = data.get("bot")
            # Fallback: пытаемся получить bot через Bot.get_current()
            if not bot:
                bot = Bot.get_current(no_error=True)
            
            screenshot_service = None
            if bot and hasattr(bot, "data"):
                try:
                    if "screenshot_service" in bot.data:
                        screenshot_service = bot.data["screenshot_service"]
                        data["screenshot_service"] = screenshot_service
                except Exception:
                    pass
            
            # Создаем PollService только если bot доступен
            # Если bot не доступен, poll_service будет None (для некоторых событий это нормально)
            poll_service = None
            if bot:
                try:
                    poll_service = PollService(
                        bot=bot,
                        poll_repo=poll_repo,
                        group_repo=group_repo,
                        screenshot_service=screenshot_service,
                    )
                except Exception:
                    # Если не удалось создать PollService, продолжаем без него
                    pass
            
            # Убеждаемся, что bot в data для использования в хэндлерах
            if bot:
                data["bot"] = bot

            data["db_session"] = session
            data["group_repo"] = group_repo
            data["poll_repo"] = poll_repo
            data["user_repo"] = user_repo
            data["screenshot_check_repo"] = screenshot_check_repo
            data["group_service"] = group_service
            data["user_service"] = user_service
            data["poll_service"] = poll_service

            try:
                result = await handler(event, data)
                # Коммитим изменения после успешного выполнения обработчика
                # Проверяем, что сессия активна и не в rollback состоянии
                if session.is_active:
                    await session.commit()
                return result
            except Exception as e:
                # Откатываем изменения при ошибке
                # Проверяем, что сессия еще активна перед rollback
                if session.is_active:
                    await session.rollback()
                raise


