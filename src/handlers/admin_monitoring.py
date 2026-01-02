"""
Обработчики для раздела "Мониторинг" админ-панели.
"""
import logging
import os
import platform
import psutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.services.group_service import GroupService
from src.services.user_service import UserService
from src.repositories.poll_repository import PollRepository
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import (
    get_monitoring_menu_keyboard,
    get_verification_menu_keyboard,
    get_back_keyboard,
    get_users_list_keyboard,
    get_user_actions_keyboard,
    get_confirmation_keyboard,
)
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:monitoring:stats")
@require_admin_callback
async def callback_monitoring_stats(
    callback: CallbackQuery,
    group_service: GroupService,
    poll_repo: PollRepository,
) -> None:
    """Статистика системы."""
    try:
        # Получаем статистику по группам
        groups = await group_service.get_all_groups()
        active_groups = await group_service.get_all_groups(active_only=True)
        
        day_groups = sum(1 for g in groups if not g.get("is_night", False))
        night_groups = sum(1 for g in groups if g.get("is_night", False))
        
        # Получаем статистику по опросам
        today = date.today()
        poll_stats = await poll_repo.get_statistics(start_date=today, end_date=today)
        
        # Получаем все активные опросы
        active_polls = await poll_repo.get_active_polls()
        
        text = (
            "📊 <b>Статистика системы</b>\n\n"
            f"👥 <b>Группы:</b>\n"
            f"• Всего: <b>{len(groups)}</b>\n"
            f"• Активных: <b>{len(active_groups)}</b>\n"
            f"• Дневных: <b>{day_groups}</b>\n"
            f"• Ночных: <b>{night_groups}</b>\n\n"
            f"📅 <b>Опросы:</b>\n"
            f"• Активных: <b>{len(active_polls)}</b>\n"
            f"• За сегодня: <b>{poll_stats.get('total_polls', 0)}</b>\n"
            f"• Закрытых за сегодня: <b>{poll_stats.get('closed_polls', 0)}</b>\n\n"
            f"📅 Дата: {today.strftime('%d.%m.%Y')}"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:monitoring_menu"))
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении статистики: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при получении статистики: {e}",
            reply_markup=get_back_keyboard("admin:monitoring_menu")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:monitoring:system")
@require_admin_callback
async def callback_monitoring_system(callback: CallbackQuery) -> None:
    """Статус системы (CPU, RAM, Disk)."""
    try:
        # Получаем информацию о системе
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Время работы системы
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_str = f"{uptime.days} дн. {uptime.seconds // 3600} ч. {(uptime.seconds % 3600) // 60} мин."
        
        text = (
            "🔍 <b>Статус системы</b>\n\n"
            f"💻 <b>CPU:</b> <b>{cpu_percent}%</b>\n"
            f"🧠 <b>RAM:</b> <b>{memory.percent}%</b> "
            f"({memory.used / (1024**3):.1f} GB / {memory.total / (1024**3):.1f} GB)\n"
            f"💾 <b>Disk:</b> <b>{disk.percent}%</b> "
            f"({disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB)\n\n"
            f"⏱️ <b>Время работы:</b> {uptime_str}\n"
            f"🖥️ <b>Платформа:</b> {platform.system()} {platform.release()}"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:monitoring_menu"))
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении статуса системы: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при получении статуса системы: {e}",
            reply_markup=get_back_keyboard("admin:monitoring_menu")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:monitoring:logs")
@require_admin_callback
async def callback_monitoring_logs(callback: CallbackQuery) -> None:
    """Просмотр логов."""
    try:
        # Путь к файлу логов
        log_file = Path(__file__).parent.parent.parent / "logs" / "bot.log"
        
        if not log_file.exists():
            text = (
                "📜 <b>Логи</b>\n\n"
                "❌ Файл логов не найден."
            )
            await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:monitoring_menu"))
            await safe_answer_callback(callback)
            return
        
        # Читаем последние 50 строк
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-50:] if len(lines) > 50 else lines
                log_content = "".join(last_lines)
        except Exception as e:
            logger.error("Ошибка при чтении логов: %s", e)
            text = (
                "📜 <b>Логи</b>\n\n"
                f"❌ Ошибка при чтении файла логов: {e}"
            )
            await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:monitoring_menu"))
            await safe_answer_callback(callback)
            return
        
        # Ограничиваем длину сообщения (Telegram лимит ~4096 символов)
        if len(log_content) > 4000:
            log_content = "...\n" + log_content[-4000:]
        
        text = (
            "📜 <b>Последние логи</b>\n\n"
            f"<pre>{log_content}</pre>"
        )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:monitoring_menu"))
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при просмотре логов: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при просмотре логов: {e}",
            reply_markup=get_back_keyboard("admin:monitoring_menu")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:monitoring:verification")
@require_admin_callback
async def callback_monitoring_verification(callback: CallbackQuery) -> None:
    """Меню верификации пользователей."""
    text = (
        "👤 <b>Верификация пользователей</b>\n\n"
        "Выберите действие:"
    )
    await safe_edit_message(callback.message, text, reply_markup=get_verification_menu_keyboard())
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:verification:unverified")
@require_admin_callback
async def callback_verification_unverified(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Список неверифицированных пользователей."""
    try:
        users = await user_service.get_unverified_users(limit=100)
        
        if not users:
            text = (
                "📋 <b>Неверифицированные пользователи</b>\n\n"
                "✅ Нет неверифицированных пользователей."
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_back_keyboard("admin:monitoring:verification")
            )
            await safe_answer_callback(callback)
            return
        
        text = (
            f"📋 <b>Неверифицированные пользователи</b>\n\n"
            f"Найдено: <b>{len(users)}</b>\n\n"
            "Выберите пользователя для верификации:"
        )
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_users_list_keyboard(users, action="verify", page=0)
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении списка неверифицированных: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:verification:verified")
@require_admin_callback
async def callback_verification_verified(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Список верифицированных пользователей."""
    try:
        users = await user_service.get_verified_users(limit=100)
        
        if not users:
            text = (
                "✅ <b>Верифицированные пользователи</b>\n\n"
                "📭 Нет верифицированных пользователей."
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_back_keyboard("admin:monitoring:verification")
            )
            await safe_answer_callback(callback)
            return
        
        text = (
            f"✅ <b>Верифицированные пользователи</b>\n\n"
            f"Найдено: <b>{len(users)}</b>\n\n"
            "Выберите пользователя:"
        )
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_users_list_keyboard(users, action="view", page=0)
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении списка верифицированных: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:verification:verify_all")
@require_admin_callback
async def callback_verification_verify_all(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Верифицировать всех неверифицированных пользователей."""
    try:
        count = await user_service.verify_all_users()
        
        text = (
            f"✅ <b>Верификация завершена</b>\n\n"
            f"Верифицировано пользователей: <b>{count}</b>"
        )
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при верификации всех пользователей: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user:verify:"))
@require_admin_callback
async def callback_user_verify(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Начало процесса верификации пользователя."""
    user_id = int(callback.data.split(":")[-1])
    
    user = await user_service.get_user_info_by_id(user_id)
    if not user:
        await safe_edit_message(
            callback.message,
            "❌ Пользователь не найден.",
            reply_markup=get_back_keyboard("admin:verification:unverified")
        )
        await safe_answer_callback(callback)
        return
    
    await state.update_data(verification_user_id=user_id)
    await state.set_state(AdminPanelStates.waiting_for_user_name)
    
    text = (
        f"✏️ <b>Верификация пользователя</b>\n\n"
        f"Telegram ID: <code>{user.get('telegram_user_id')}</code>\n\n"
        "Введите имя и фамилию пользователя в одной строке:\n"
        "<code>Имя Фамилия</code>\n\n"
        "Пример: <code>Иван Иванов</code>\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:verification:unverified"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_user_name)
async def process_user_name(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработка ввода имени и фамилии для верификации."""
    data = await state.get_data()
    user_id = data.get("verification_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран. Начните заново.", parse_mode="HTML")
        await state.clear()
        return
    
    # Проверка на отмену
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Верификация отменена", parse_mode="HTML")
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите имя и фамилию текстом.", parse_mode="HTML")
        return
    
    # Парсим имя и фамилию
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Введите имя и фамилию в одной строке.\n"
            "Пример: <code>Иван Иванов</code>",
            parse_mode="HTML"
        )
        return
    
    first_name = parts[0]
    last_name = parts[1]
    
    try:
        success = await user_service.verify_user(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
        
        if success:
            text = (
                f"✅ <b>Пользователь верифицирован!</b>\n\n"
                f"Имя: <b>{first_name}</b>\n"
                f"Фамилия: <b>{last_name}</b>\n\n"
                f"Теперь пользователь может участвовать в опросах."
            )
        else:
            text = "❌ Ошибка при верификации пользователя."
        
        await message.answer(text, reply_markup=get_back_keyboard("admin:monitoring:verification"), parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при верификации пользователя: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")
        await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user:view:"))
@require_admin_callback
async def callback_user_view(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Просмотр информации о верифицированном пользователе."""
    user_id = int(callback.data.split(":")[-1])
    
    user = await user_service.get_user_info_by_id(user_id)
    if not user:
        await safe_edit_message(
            callback.message,
            "❌ Пользователь не найден.",
            reply_markup=get_back_keyboard("admin:verification:verified")
        )
        await safe_answer_callback(callback)
        return
    
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    telegram_id = user.get("telegram_user_id", 0)
    is_verified = user.get("is_verified", False)
    
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"Имя: <b>{first_name}</b>\n"
        f"Фамилия: <b>{last_name}</b>\n"
        f"Telegram ID: <code>{telegram_id}</code>\n"
        f"Статус: {'✅ Верифицирован' if is_verified else '❌ Не верифицирован'}"
    )
    
    await safe_edit_message(
        callback.message,
        text,
        reply_markup=get_user_actions_keyboard(user_id)
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user:rename:"))
@require_admin_callback
async def callback_user_rename(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Начало процесса переименования пользователя."""
    user_id = int(callback.data.split(":")[-1])
    
    user = await user_service.get_user_info_by_id(user_id)
    if not user:
        await safe_edit_message(
            callback.message,
            "❌ Пользователь не найден.",
            reply_markup=get_back_keyboard("admin:verification:verified")
        )
        await safe_answer_callback(callback)
        return
    
    await state.update_data(rename_user_id=user_id)
    await state.set_state(AdminPanelStates.waiting_for_user_rename)
    
    current_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    
    text = (
        f"✏️ <b>Переименование пользователя</b>\n\n"
        f"Текущее имя: <b>{current_name or 'Не указано'}</b>\n\n"
        "Введите новое имя и фамилию в одной строке:\n"
        "<code>Имя Фамилия</code>\n\n"
        "Пример: <code>Петр Петров</code>\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:verification:verified"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_user_rename)
async def process_user_rename(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработка ввода нового имени и фамилии."""
    data = await state.get_data()
    user_id = data.get("rename_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не выбран. Начните заново.", parse_mode="HTML")
        await state.clear()
        return
    
    # Проверка на отмену
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Переименование отменено", parse_mode="HTML")
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите имя и фамилию текстом.", parse_mode="HTML")
        return
    
    # Парсим имя и фамилию
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Введите имя и фамилию в одной строке.\n"
            "Пример: <code>Петр Петров</code>",
            parse_mode="HTML"
        )
        return
    
    first_name = parts[0]
    last_name = parts[1]
    
    try:
        success = await user_service.update_user_name(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
        
        if success:
            text = (
                f"✅ <b>Имя обновлено!</b>\n\n"
                f"Новое имя: <b>{first_name} {last_name}</b>"
            )
        else:
            text = "❌ Ошибка при обновлении имени."
        
        await message.answer(text, reply_markup=get_back_keyboard("admin:monitoring:verification"), parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при переименовании пользователя: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}", parse_mode="HTML")
        await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user:delete:"))
@require_admin_callback
async def callback_user_delete(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Подтверждение удаления верификации пользователя."""
    user_id = int(callback.data.split(":")[-1])
    
    user = await user_service.get_user_info_by_id(user_id)
    if not user:
        await safe_edit_message(
            callback.message,
            "❌ Пользователь не найден.",
            reply_markup=get_back_keyboard("admin:verification:verified")
        )
        await safe_answer_callback(callback)
        return
    
    await state.update_data(delete_user_id=user_id)
    
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or f"ID: {user.get('telegram_user_id')}"
    
    text = (
        f"🗑️ <b>Удаление верификации</b>\n\n"
        f"Пользователь: <b>{name}</b>\n\n"
        "⚠️ Это действие удалит верификацию пользователя.\n"
        "Пользователь не сможет участвовать в опросах.\n\n"
        "Подтвердите удаление:"
    )
    
    await safe_edit_message(
        callback.message,
        text,
        reply_markup=get_confirmation_keyboard(
            confirm_callback=f"admin:user:delete_confirm:{user_id}",
            cancel_callback="admin:verification:verified"
        )
    )
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:user:delete_confirm:"))
@require_admin_callback
async def callback_user_delete_confirm(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Удаление верификации пользователя."""
    user_id = int(callback.data.split(":")[-1])
    
    try:
        success = await user_service.unverify_user(user_id)
        
        if success:
            text = (
                "✅ <b>Верификация удалена</b>\n\n"
                "Пользователь больше не может участвовать в опросах."
            )
        else:
            text = "❌ Ошибка при удалении верификации."
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при удалении верификации: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:verification:verify:page:"))
@require_admin_callback
async def callback_verification_unverified_page(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Пагинация списка неверифицированных пользователей."""
    page = int(callback.data.split(":")[-1])
    
    try:
        users = await user_service.get_unverified_users(limit=100)
        
        if not users:
            text = (
                "📋 <b>Неверифицированные пользователи</b>\n\n"
                "✅ Нет неверифицированных пользователей."
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_back_keyboard("admin:monitoring:verification")
            )
            await safe_answer_callback(callback)
            return
        
        text = (
            f"📋 <b>Неверифицированные пользователи</b>\n\n"
            f"Найдено: <b>{len(users)}</b>\n\n"
            "Выберите пользователя для верификации:"
        )
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_users_list_keyboard(users, action="verify", page=page)
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении списка неверифицированных: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:verification:view:page:"))
@require_admin_callback
async def callback_verification_verified_page(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Пагинация списка верифицированных пользователей."""
    page = int(callback.data.split(":")[-1])
    
    try:
        users = await user_service.get_verified_users(limit=100)
        
        if not users:
            text = (
                "✅ <b>Верифицированные пользователи</b>\n\n"
                "📭 Нет верифицированных пользователей."
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_back_keyboard("admin:monitoring:verification")
            )
            await safe_answer_callback(callback)
            return
        
        text = (
            f"✅ <b>Верифицированные пользователи</b>\n\n"
            f"Найдено: <b>{len(users)}</b>\n\n"
            "Выберите пользователя:"
        )
        
        await safe_edit_message(
            callback.message,
            text,
            reply_markup=get_users_list_keyboard(users, action="view", page=page)
        )
        await safe_answer_callback(callback)
        
    except Exception as e:
        logger.error("Ошибка при получении списка верифицированных: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка: {e}",
            reply_markup=get_back_keyboard("admin:monitoring:verification")
        )
        await safe_answer_callback(callback)
