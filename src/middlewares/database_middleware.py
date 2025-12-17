from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message

from src.models.database import AsyncSessionLocal
from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository  # type: ignore
from src.services.group_service import GroupService


class DatabaseMiddleware(BaseMiddleware):
    """Создает сессию БД и основные сервисы на время обработки апдейта."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            group_repo = GroupRepository(session)
            poll_repo = PollRepository(session)
            group_service = GroupService(session)

            data["db_session"] = session
            data["group_repo"] = group_repo
            data["poll_repo"] = poll_repo
            data["group_service"] = group_service

            return await handler(event, data)


