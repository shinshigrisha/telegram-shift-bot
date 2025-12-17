from datetime import datetime, date
from pathlib import Path
import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile

from config.settings import settings
from src.utils.auth import require_admin  # type: ignore


logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("get_report"))
@require_admin
async def cmd_get_report(
    message: Message,
    command: CommandObject,
    state: FSMContext | None = None,
) -> None:
    """Получить отчет по группе за дату."""
    try:
        args = command.args.split() if command.args else []

        if len(args) < 1:
            await message.answer(
                "❌ Не указана группа\n"
                "Использование: /get_report ЗИЗ-1 [дата]\n"
                "Дата в формате ДД.ММ.ГГГГ (по умолчанию сегодня)"
            )
            return

        group_name = args[0].strip()

        poll_date = date.today()
        if len(args) >= 2:
            try:
                poll_date = datetime.strptime(args[1], "%d.%m.%Y").date()
            except ValueError:
                await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
                return

        report_path = settings.REPORTS_DIR / group_name / f"{poll_date.strftime('%Y-%m-%d')}.txt"

        if not report_path.exists():
            await message.answer(
                f"📭 Отчет для группы {group_name} за {poll_date.strftime('%d.%m.%Y')} не найден"
            )
            return

        try:
            file = FSInputFile(Path(report_path))
            await message.answer_document(
                file,
                caption=f"📊 Отчет: {group_name} | {poll_date.strftime('%d.%m.%Y')}",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Error sending report: %s", e)
            await message.answer(f"❌ Ошибка при отправке отчета: {e}")

    except Exception as e:  # noqa: BLE001
        logger.error("Error in get_report: %s", e)
        await message.answer("❌ Произошла ошибка при получении отчета")


@router.message(Command("generate_all_reports"))
@require_admin
async def cmd_generate_all_reports(
    message: Message,
    state: FSMContext | None = None,
) -> None:
    """Сгенерировать отчеты для всех групп (пока заглушка)."""
    await message.answer("⏳ Генерация отчетов...")
    await message.answer("✅ Отчеты сгенерированы")


