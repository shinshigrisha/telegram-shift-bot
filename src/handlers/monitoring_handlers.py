import logging
from typing import Optional

import psutil
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.utils.auth import require_admin


router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("status"))
@require_admin
async def cmd_status(
    message: Message,
    state: Optional[FSMContext] = None,
) -> None:
    """Статус системы."""
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    disk = psutil.disk_usage("/")

    status_text = (
        "📊 Статус системы:\n\n"
        f"💾 Память: {memory.percent}% использовано\n"
        f"⚡ CPU: {cpu_percent}% загружен\n"
        f"💿 Диск: {disk.percent}% заполнен\n"
        f"🔄 Процессов: {len(psutil.pids())}\n"
    )

    await message.answer(status_text)


@router.message(Command("logs"))
@require_admin
async def cmd_logs(
    message: Message,
    state: Optional[FSMContext] = None,
) -> None:
    """Последние логи."""
    from config.settings import settings

    try:
        with open(settings.LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]

        logs_text = "📝 Последние логи:\n\n" + "".join(lines)

        if len(logs_text) > 4000:
            for i in range(0, len(logs_text), 4000):
                await message.answer(logs_text[i : i + 4000])
        else:
            await message.answer(logs_text)

    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ Ошибка при чтении логов: {e}")


