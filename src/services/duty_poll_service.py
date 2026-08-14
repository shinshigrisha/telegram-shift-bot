"""Ежедневный опрос дежурных в отдельной теме Telegram."""

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Dict, List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from src.repositories.duty_poll_repository import DutyPollRepository

logger = logging.getLogger(__name__)


DUTY_POLL_OPTIONS = [
    "зиз-1,2 красноказарменная",
    "зиз-3 энергетическая",
    "зиз-4 боровая",
    "зиз-5 госпиталка",
    "зиз-6 солдатская",
    "зиз-7 карачарово",
    "зиз-8 басманка",
    "зиз-9 курская",
    "зиз-10 волочаевская",
    "зиз-11 шоссе",
    "зиз-12 невельского",
    "зиз-18 авиамоторная",
]


class DutyPollService:
    """Создаёт и закрывает опросы в настроенных темах «Дежурные»."""

    def __init__(self, bot: Bot, repository: DutyPollRepository):
        self.bot = bot
        self.repository = repository

    @staticmethod
    def format_question(poll_date: date) -> str:
        """Сформировать заголовок по образцу из рабочей группы."""
        return f"дежурные {poll_date.strftime('%d.%m')} до 00:00"

    async def send_daily_polls(self, poll_date: date | None = None) -> tuple[int, List[str]]:
        """Отправить один опрос на дату в каждую включённую тему."""
        poll_date = poll_date or date.today()
        created_count = 0
        errors: List[str] = []

        for config in await self.repository.get_active_configs():
            config_id = int(config["id"])
            claimed = await self.repository.claim_dispatch(config_id, poll_date)
            if not claimed:
                continue

            try:
                message = await self._send_poll_with_retry(config, poll_date)
                await self.repository.mark_sent(
                    config_id=config_id,
                    poll_date=poll_date,
                    telegram_poll_id=str(message.poll.id),
                    telegram_message_id=message.message_id,
                )
                created_count += 1

                try:
                    await self.bot.pin_chat_message(
                        chat_id=config["telegram_chat_id"],
                        message_id=message.message_id,
                        disable_notification=False,
                    )
                except Exception as exc:  # Опрос уже создан, закрепление не критично.
                    logger.warning("Не удалось закрепить опрос дежурных: %s", exc)
            except Exception as exc:
                await self.repository.release_dispatch(config_id, poll_date)
                error = (
                    f"chat_id={config['telegram_chat_id']}, "
                    f"topic_id={config['message_thread_id']}: {exc}"
                )
                logger.error("Ошибка отправки опроса дежурных: %s", error, exc_info=True)
                errors.append(error)

        return created_count, errors

    async def _send_poll_with_retry(self, config: Dict[str, Any], poll_date: date):
        """Повторить отправку при временной сетевой ошибке."""
        last_error: TelegramNetworkError | None = None
        for attempt in range(1, 4):
            try:
                return await self.bot.send_poll(
                    chat_id=config["telegram_chat_id"],
                    message_thread_id=config["message_thread_id"],
                    question=self.format_question(poll_date),
                    options=DUTY_POLL_OPTIONS,
                    is_anonymous=False,
                    allows_multiple_answers=False,
                    disable_notification=False,
                )
            except TelegramNetworkError as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(attempt)

        if last_error:
            raise last_error
        raise RuntimeError("Telegram не вернул сообщение с опросом")

    async def close_expired_polls(self, current_date: date | None = None) -> int:
        """Закрыть активные опросы прошлых дней."""
        current_date = current_date or date.today()
        closed_count = 0

        for dispatch in await self.repository.get_expired_active(current_date):
            try:
                await self.bot.stop_poll(
                    chat_id=dispatch["telegram_chat_id"],
                    message_id=dispatch["telegram_message_id"],
                )
            except TelegramBadRequest as exc:
                if "poll can't be stopped" not in str(exc).lower():
                    logger.error("Не удалось закрыть опрос дежурных: %s", exc)
                    continue
            except Exception as exc:
                logger.error("Не удалось закрыть опрос дежурных: %s", exc)
                continue

            await self.repository.mark_closed(dispatch["id"], datetime.now())
            closed_count += 1

        return closed_count
