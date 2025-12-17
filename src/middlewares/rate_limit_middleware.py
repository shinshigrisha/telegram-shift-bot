from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta
import logging

from aiogram import BaseMiddleware
from aiogram.types import Message

from config.settings import settings


logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self.user_requests: Dict[int, list[datetime]] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        now = datetime.now()

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        window = timedelta(seconds=settings.RATE_LIMIT_WINDOW)
        self.user_requests[user_id] = [
            t for t in self.user_requests[user_id] if now - t < window
        ]

        if len(self.user_requests[user_id]) >= settings.RATE_LIMIT_PER_USER:
            wait_time = settings.RATE_LIMIT_WINDOW - (
                now - self.user_requests[user_id][0]
            ).seconds
            await event.answer(
                f"⚠️ Слишком много запросов. Подождите {wait_time} секунд"
            )
            return

        self.user_requests[user_id].append(now)

        return await handler(event, data)


