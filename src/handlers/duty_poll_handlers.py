"""Команды настройки ежедневного опроса в теме «Дежурные»."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asyncpg import Pool

from config.settings import settings
from src.repositories.duty_poll_repository import DutyPollRepository

router = Router()


def _is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in settings.ADMIN_IDS)


async def _validate_topic_command(message: Message) -> bool:
    if not _is_admin(message):
        await message.answer("⛔ Настраивать опрос дежурных может только администратор.")
        return False
    if message.chat.type != "supergroup" or message.message_thread_id is None:
        await message.answer(
            "❌ Отправьте эту команду прямо внутри темы «Дежурные» в общей группе."
        )
        return False
    return True


@router.message(Command("setup_duty_poll"))
async def setup_duty_poll(message: Message, db_pool: Pool) -> None:
    """Запомнить текущую тему и включить ежедневный опрос."""
    if not await _validate_topic_command(message):
        return

    await DutyPollRepository(db_pool).enable(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
    )
    await message.answer(
        "✅ <b>Ежедневный опрос дежурных включён.</b>\n\n"
        "Бот будет отправлять его в эту тему каждый день в <b>10:00 по Москве</b> "
        "и закрывать после 00:00.\n\n"
        "Отключить: /disable_duty_poll",
        parse_mode="HTML",
    )


@router.message(Command("disable_duty_poll"))
async def disable_duty_poll(message: Message, db_pool: Pool) -> None:
    """Отключить ежедневный опрос для текущей темы."""
    if not await _validate_topic_command(message):
        return

    disabled = await DutyPollRepository(db_pool).disable(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
    )
    text = (
        "✅ Ежедневный опрос дежурных отключён для этой темы."
        if disabled
        else "ℹ️ Для этой темы автоматизация ещё не была настроена."
    )
    await message.answer(text)
