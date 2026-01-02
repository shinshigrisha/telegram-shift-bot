"""
Обработчики для команд управления планировщиком и принудительных операций.

Команды:
- /force_poll [группа] - Принудительно создать опрос
- /manual_close [группа] - Принудительно закрыть опрос
- /get_report [группа] [дата] - Получить отчет
- /test_screenshot - Тест создания скриншота
- /stats - Статистика по всем ЗИЗам
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from pathlib import Path

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, FSInputFile

from src.utils.auth import require_admin, require_admin_callback
from src.services.scheduler_service import SchedulerService
from src.services.poll_service import PollService
from src.services.group_service import GroupService
from src.services.service_registry import get_scheduler_service, get_poll_service
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("force_poll"))
@require_admin
async def cmd_force_poll(
    message: Message,
    command: CommandObject,
    bot: Bot,
) -> None:
    """
    Принудительно создать опросы.
    
    Использование:
        /force_poll - создать опросы для всех групп на завтра
        /force_poll ЗИЗ-1 - создать опрос только для ЗИЗ-1
        /force_poll 2024-01-15 - создать опросы на указанную дату
    """
    # Получаем scheduler из глобального реестра
    scheduler_service: Optional[SchedulerService] = get_scheduler_service()
    
    if not scheduler_service:
        await message.answer("❌ Планировщик не инициализирован")
        return
    
    # Парсим аргументы
    args = command.args.split() if command.args else []
    
    target_date = date.today() + timedelta(days=1)
    group_name: Optional[str] = None
    
    for arg in args:
        # Проверяем, дата ли это
        try:
            target_date = datetime.strptime(arg, "%Y-%m-%d").date()
        except ValueError:
            # Не дата - считаем названием группы
            group_name = arg
    
    await message.answer(
        f"🔄 Создание опросов...\n"
        f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
        f"📍 Группа: {group_name or 'все'}"
    )
    
    try:
        created_count, errors = await scheduler_service.force_create_polls(target_date)
        
        result = (
            f"✅ <b>Опросы созданы</b>\n\n"
            f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
            f"✅ Создано: {created_count}\n"
        )
        
        if errors:
            result += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
            for error in errors[:5]:
                result += f"• {error}\n"
            if len(errors) > 5:
                result += f"... и еще {len(errors) - 5}\n"
        
        await message.answer(result)
        
    except Exception as e:
        logger.error("Ошибка создания опросов: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("manual_close"))
@require_admin
async def cmd_manual_close(
    message: Message,
    command: CommandObject,
    bot: Bot,
) -> None:
    """
    Принудительно закрыть опросы.
    
    Использование:
        /manual_close - закрыть все активные опросы на завтра
        /manual_close ЗИЗ-1 - закрыть опрос только для ЗИЗ-1
        /manual_close 2024-01-15 - закрыть опросы на указанную дату
    """
    scheduler_service: Optional[SchedulerService] = main_module.scheduler_service
    
    if not scheduler_service:
        await message.answer("❌ Планировщик не инициализирован")
        return
    
    # Парсим аргументы
    args = command.args.split() if command.args else []
    
    target_date = date.today() + timedelta(days=1)
    group_name: Optional[str] = None
    
    for arg in args:
        try:
            target_date = datetime.strptime(arg, "%Y-%m-%d").date()
        except ValueError:
            group_name = arg
    
    await message.answer(
        f"🔒 Закрытие опросов...\n"
        f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
        f"📍 Группа: {group_name or 'все'}"
    )
    
    try:
        closed_count, errors = await scheduler_service.force_close_polls(target_date)
        
        result = (
            f"🔒 <b>Опросы закрыты</b>\n\n"
            f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n"
            f"✅ Закрыто: {closed_count}\n"
        )
        
        if errors:
            result += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
            for error in errors[:5]:
                result += f"• {error}\n"
        
        await message.answer(result)
        
    except Exception as e:
        logger.error("Ошибка закрытия опросов: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("get_report"))
@require_admin
async def cmd_get_report(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
) -> None:
    """
    Получить отчет по опросам.
    
    Использование:
        /get_report ЗИЗ-1 - отчет для группы за сегодня
        /get_report ЗИЗ-1 2024-01-15 - отчет за указанную дату
    """
    args = command.args.split() if command.args else []
    
    if not args:
        await message.answer(
            "ℹ️ <b>Использование:</b>\n"
            "/get_report <группа> [дата]\n\n"
            "Примеры:\n"
            "/get_report ЗИЗ-1\n"
            "/get_report ЗИЗ-1 2024-01-15"
        )
        return
    
    group_name = args[0]
    target_date = date.today()
    
    if len(args) > 1:
        try:
            target_date = datetime.strptime(args[1], "%Y-%m-%d").date()
        except ValueError:
            await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD")
            return
    
    # Ищем файл отчета
    report_path = Path("reports") / group_name / f"{target_date.strftime('%Y-%m-%d')}.txt"
    
    if report_path.exists():
        # Отправляем текстовый отчет
        report_content = report_path.read_text(encoding='utf-8')
        await message.answer(
            f"📊 <b>Отчет: {group_name}</b>\n"
            f"📅 Дата: {target_date.strftime('%d.%m.%Y')}\n\n"
            f"<pre>{report_content[:3500]}</pre>"  # Ограничиваем длину
        )
        
        # Проверяем наличие PNG скриншота
        png_path = Path("reports") / group_name / f"{target_date.strftime('%Y-%m-%d')}.png"
        if png_path.exists():
            await message.answer_photo(
                photo=FSInputFile(png_path),
                caption=f"📸 Скриншот опроса: {group_name} | {target_date.strftime('%d.%m.%Y')}"
            )
    else:
        await message.answer(
            f"📭 Отчет не найден\n\n"
            f"Группа: {group_name}\n"
            f"Дата: {target_date.strftime('%d.%m.%Y')}"
        )


@router.message(Command("stats"))
@require_admin
async def cmd_stats(
    message: Message,
    group_service: GroupService,
    bot: Bot,
) -> None:
    """
    Показать статистику по всем ЗИЗам.
    """
    poll_service: Optional[PollService] = get_poll_service()
    
    try:
        # Статистика по группам
        groups = await group_service.get_all_groups()
        active_groups = await group_service.get_all_groups(active_only=True)
        
        # Статистика по опросам (если доступен poll_service)
        active_polls = 0
        today_polls = 0
        tomorrow_polls = 0
        
        if poll_service:
            all_active_polls = await poll_service.poll_repo.get_active_polls()
            active_polls = len(all_active_polls)
            
            today = date.today()
            tomorrow = today + timedelta(days=1)
            
            today_polls = len([p for p in all_active_polls if p.get('poll_date') == today])
            tomorrow_polls = len([p for p in all_active_polls if p.get('poll_date') == tomorrow])
        
        # Подсчет типов групп
        day_groups = sum(1 for g in groups if not g.get('is_night', False))
        night_groups = sum(1 for g in groups if g.get('is_night', False))
        
        # Группы со слотами
        groups_with_slots = sum(
            1 for g in groups 
            if g.get('settings', {}).get('slots')
        )
        
        stats_text = (
            "📊 <b>Статистика системы</b>\n\n"
            f"👥 <b>Группы:</b>\n"
            f"• Всего: {len(groups)}\n"
            f"• Активных: {len(active_groups)}\n"
            f"• Дневных: {day_groups}\n"
            f"• Ночных: {night_groups}\n"
            f"• Со слотами: {groups_with_slots}\n\n"
            f"📋 <b>Опросы:</b>\n"
            f"• Активных: {active_polls}\n"
            f"• На сегодня: {today_polls}\n"
            f"• На завтра: {tomorrow_polls}\n\n"
            f"⏰ <b>Расписание:</b>\n"
            f"• Создание: {settings.POLL_CREATION_HOUR}:{str(settings.POLL_CREATION_MINUTE).zfill(2)}\n"
            f"• Закрытие: {settings.POLL_CLOSING_HOUR}:{str(settings.POLL_CLOSING_MINUTE).zfill(2)}\n"
            f"• Напоминания: {', '.join(map(str, settings.REMINDER_HOURS))}\n"
        )
        
        await message.answer(stats_text)
        
    except Exception as e:
        logger.error("Ошибка получения статистики: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("test_screenshot"))
@require_admin
async def cmd_test_screenshot(message: Message) -> None:
    """
    Тест создания скриншота (заглушка).
    """
    await message.answer(
        "📸 <b>Тест скриншота</b>\n\n"
        "Функция создания скриншотов использует текстовые отчеты.\n"
        "Для полноценных скриншотов требуется:\n"
        "• Selenium/Playwright для рендеринга\n"
        "• Доступ к Telegram Web\n\n"
        "Текущая реализация сохраняет результаты в текстовом формате."
    )


@router.message(Command("setup_ziz"))
@require_admin
async def cmd_setup_ziz(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
) -> None:
    """
    Настройка слотов для группы.
    
    Использование:
        /setup_ziz ЗИЗ-1
    """
    if not command.args:
        await message.answer(
            "ℹ️ <b>Использование:</b>\n"
            "/setup_ziz <название группы>\n\n"
            "Примеры:\n"
            "/setup_ziz ЗИЗ-1\n"
            "/setup_ziz НОЧЬ-лево"
        )
        return
    
    group_name = command.args.strip()
    
    # Проверяем существование группы
    group = await group_service.get_group_by_name(group_name)
    
    if not group:
        await message.answer(
            f"❌ Группа <b>{group_name}</b> не найдена.\n\n"
            "Используйте /add_ziz для создания группы."
        )
        return
    
    # Показываем текущие настройки
    settings_data = group.get('settings', {})
    slots = settings_data.get('slots', [])
    
    if slots:
        slots_text = "📋 <b>Текущие слоты:</b>\n"
        for i, slot in enumerate(slots, 1):
            slots_text += (
                f"  {i}. {slot.get('start', '?')}-{slot.get('end', '?')} | "
                f"Лимит: {slot.get('limit', 3)} чел\n"
            )
    else:
        slots_text = "⚠️ Слоты не настроены"
    
    poll_close_time = group.get('poll_close_time', '19:00')
    
    await message.answer(
        f"⚙️ <b>Настройки {group_name}:</b>\n\n"
        f"{slots_text}\n"
        f"⏰ <b>Закрытие опроса:</b> {poll_close_time}\n\n"
        "Для редактирования используйте:\n"
        "• Админ-панель → Настройки → Настроить слоты\n"
        "• Или /admin"
    )


@router.message(Command("add_ziz"))
@require_admin
async def cmd_add_ziz(
    message: Message,
    command: CommandObject,
    group_service: GroupService,
) -> None:
    """
    Добавить новую группу.
    
    Использование:
        /add_ziz ЗИЗ-15 -1001234567890
    """
    if not command.args:
        await message.answer(
            "ℹ️ <b>Использование:</b>\n"
            "/add_ziz <название> <chat_id>\n\n"
            "Примеры:\n"
            "/add_ziz ЗИЗ-15 -1001234567890\n"
            "/add_ziz НОЧЬ-право -1009876543210\n\n"
            "💡 <b>Как получить Chat ID:</b>\n"
            "1. Добавьте бота в группу\n"
            "2. Отправьте любое сообщение\n"
            "3. Chat ID будет в логах бота"
        )
        return
    
    args = command.args.split()
    
    if len(args) < 2:
        await message.answer("❌ Укажите название группы и Chat ID")
        return
    
    group_name = args[0]
    
    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("❌ Chat ID должен быть числом")
        return
    
    # Проверяем, не существует ли уже такая группа
    existing = await group_service.get_group_by_name(group_name)
    if existing:
        await message.answer(f"❌ Группа <b>{group_name}</b> уже существует")
        return
    
    # Определяем, ночная ли группа
    is_night = "ночь" in group_name.lower()
    
    try:
        # Создаем группу
        new_group = await group_service.create_group(
            name=group_name,
            telegram_chat_id=chat_id,
            is_night=is_night,
        )
        
        await message.answer(
            f"✅ <b>Группа создана</b>\n\n"
            f"📍 Название: {group_name}\n"
            f"💬 Chat ID: {chat_id}\n"
            f"🌙 Ночная: {'Да' if is_night else 'Нет'}\n\n"
            f"Теперь настройте слоты:\n"
            f"• Админ-панель → Настройки → Настроить слоты\n"
            f"• Или /setup_ziz {group_name}"
        )
        
    except Exception as e:
        logger.error("Ошибка создания группы: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка создания группы: {e}")


@router.message(Command("scheduler_status"))
@require_admin
async def cmd_scheduler_status(message: Message, bot: Bot) -> None:
    """
    Показать статус планировщика.
    """
    scheduler_service: Optional[SchedulerService] = main_module.scheduler_service
    
    if not scheduler_service:
        await message.answer("❌ Планировщик не инициализирован")
        return
    
    jobs = scheduler_service.scheduler.get_jobs()
    
    status_text = (
        "⏰ <b>Статус планировщика</b>\n\n"
        f"🟢 Статус: {'Запущен' if scheduler_service._is_running else 'Остановлен'}\n\n"
        f"📋 <b>Задачи ({len(jobs)}):</b>\n"
    )
    
    for job in jobs:
        next_run = job.next_run_time
        next_run_str = next_run.strftime('%d.%m.%Y %H:%M') if next_run else 'N/A'
        status_text += f"• {job.name}: {next_run_str}\n"
    
    await message.answer(status_text)
