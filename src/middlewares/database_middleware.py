from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository  # type: ignore
from src.repositories.user_repository import UserRepository
from src.services.group_service import GroupService
from src.services.user_service import UserService


class DatabaseMiddleware(BaseMiddleware):
    """Создает сессию БД и основные сервисы на время обработки апдейта."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            user_repo = UserRepository(session)
            group_service = GroupService(session)
            user_service = UserService(session)

            data["db_session"] = session
            data["group_repo"] = group_repo
            data["poll_repo"] = poll_repo
            data["user_repo"] = user_repo
            data["group_service"] = group_service
            data["user_service"] = user_service

            return await handler(event, data)


