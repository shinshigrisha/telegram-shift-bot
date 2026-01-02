"""
Обработчики для раздела "Опросы" админ-панели.
"""
import logging
from typing import Optional
from datetime import date, timedelta

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.states.admin_panel_states import AdminPanelStates
from src.services.poll_service import PollService
from src.services.group_service import GroupService
from src.repositories.poll_repository import PollRepository
from src.repositories.group_repository import GroupRepository
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import (
    get_polls_menu_keyboard,
    get_groups_list_keyboard,
    get_back_keyboard,
    get_confirmation_keyboard,
)
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback
from src.utils.group_formatters import clean_group_name_for_display
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:polls_menu")
@require_admin_callback
async def callback_polls_menu(callback: CallbackQuery) -> None:
    """Меню управления опросами."""
    text = (
        "📊 <b>Управление опросами</b>\n\n"
        "Выберите действие:"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_polls_menu_keyboard())
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:create")
@require_admin_callback
async def callback_create_polls(callback: CallbackQuery, bot: Bot, poll_repo: PollRepository, group_repo: GroupRepository) -> None:
    """Создание опросов вручную."""
    try:
        poll_service = PollService(bot=bot, poll_repo=poll_repo, group_repo=group_repo)
        
        await safe_edit_message(
            callback.message,
            "⏳ Создание опросов...\n\nПожалуйста, подождите.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        
        created_count, errors = await poll_service.create_daily_polls()
        
        if errors:
            error_text = "\n".join(f"❌ {e}" for e in errors[:10])  # Показываем первые 10 ошибок
            if len(errors) > 10:
                error_text += f"\n... и еще {len(errors) - 10} ошибок"
            
            text = (
                f"✅ <b>Создание опросов завершено</b>\n\n"
                f"Создано опросов: <b>{created_count}</b>\n\n"
                f"❌ <b>Ошибки:</b>\n{error_text}"
            )
        else:
            text = (
                f"✅ <b>Опросы успешно созданы!</b>\n\n"
                f"Создано опросов: <b>{created_count}</b>\n\n"
                f"Опросы созданы на завтрашний день для всех активных групп."
            )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        
    except Exception as e:
        logger.error("Ошибка при создании опросов: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при создании опросов: {e}",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )


@router.callback_query(lambda c: c.data == "admin:polls:recreate")
@require_admin_callback
async def callback_recreate_polls_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса пересоздания опросов."""
    await state.set_state(AdminPanelStates.waiting_for_delete_confirmation)
    await state.update_data(action="recreate_polls")
    
    text = (
        "🔄 <b>Пересоздание опросов</b>\n\n"
        "⚠️ <b>Внимание!</b> При пересоздании:\n"
        "• Все существующие опросы будут удалены\n"
        "• Все голоса в них будут потеряны\n"
        "• Будут созданы новые опросы на завтрашний день\n\n"
        "Вы уверены, что хотите продолжить?"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_confirmation_keyboard("admin:polls:recreate_confirm", "admin:polls_menu"))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:recreate_confirm")
@require_admin_callback
async def callback_recreate_polls_confirm(callback: CallbackQuery, bot: Bot, poll_repo: PollRepository, group_repo: GroupRepository, state: FSMContext) -> None:
    """Подтверждение пересоздания опросов."""
    try:
        # Удаляем все активные опросы
        active_polls = await poll_repo.get_active_polls()
        deleted_count = 0
        
        for poll in active_polls:
            try:
                # Закрываем опрос в Telegram (если возможно)
                if poll.get('telegram_poll_id') and poll.get('telegram_message_id'):
                    try:
                        chat_id = None
                        # Получаем chat_id из группы
                        group = await group_repo.get_by_id(poll['group_id'])
                        if group:
                            chat_id = group['telegram_chat_id']
                            topic_id = poll.get('telegram_topic_id')
                            
                            try:
                                await bot.stop_poll(
                                    chat_id=chat_id,
                                    message_id=poll['telegram_message_id'],
                                    message_thread_id=topic_id
                                )
                            except Exception as e:
                                logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
                    except Exception as e:
                        logger.warning("Ошибка при закрытии опроса в Telegram: %s", e)
                
                # Удаляем опрос из БД
                await poll_repo.close_poll(str(poll['id']))
                deleted_count += 1
            except Exception as e:
                logger.error("Ошибка при удалении опроса %s: %s", poll.get('id'), e)
        
        # Создаем новые опросы
        poll_service = PollService(bot=bot, poll_repo=poll_repo, group_repo=group_repo)
        
        await safe_edit_message(
            callback.message,
            f"⏳ Удалено опросов: {deleted_count}\n\nСоздание новых опросов...",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        
        created_count, errors = await poll_service.create_daily_polls()
        
        if errors:
            error_text = "\n".join(f"❌ {e}" for e in errors[:10])
            if len(errors) > 10:
                error_text += f"\n... и еще {len(errors) - 10} ошибок"
            
            text = (
                f"✅ <b>Пересоздание опросов завершено</b>\n\n"
                f"Удалено опросов: <b>{deleted_count}</b>\n"
                f"Создано опросов: <b>{created_count}</b>\n\n"
                f"❌ <b>Ошибки:</b>\n{error_text}"
            )
        else:
            text = (
                f"✅ <b>Опросы успешно пересозданы!</b>\n\n"
                f"Удалено опросов: <b>{deleted_count}</b>\n"
                f"Создано опросов: <b>{created_count}</b>"
            )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        await state.clear()
        
    except Exception as e:
        logger.error("Ошибка при пересоздании опросов: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при пересоздании опросов: {e}",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "admin:polls:results")
@require_admin_callback
async def callback_polls_results_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Начало просмотра результатов опросов."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)
    await state.update_data(action="view_poll_results")
    
    text = (
        "📊 <b>Результаты опросов</b>\n\n"
        "Выберите группу:"
    )
    
    # Создаем клавиатуру с модифицированными callback_data для опросов
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group_name,
                callback_data=f"admin:poll_group:{group['id']}"
            )
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:poll_group:"))
@require_admin_callback
async def callback_select_group_for_polls(callback: CallbackQuery, state: FSMContext, bot: Bot, poll_repo: PollRepository, group_repo: GroupRepository, group_service: GroupService) -> None:
    """Обработка выбора группы для опросов (результаты или закрытие)."""
    data = await state.get_data()
    action = data.get("action")
    
    group_id = int(callback.data.split(":")[-1])
    group = await group_service.get_group_by_id(group_id)
    
    if not group:
        await safe_edit_message(
            callback.message,
            "❌ Группа не найдена.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return
    
    if action == "view_poll_results":
        # Просмотр результатов опроса
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Ищем опрос на завтра
        poll = await poll_repo.get_by_group_and_date(group_id, tomorrow)
        
        if not poll:
            text = (
                f"📊 <b>Результаты опросов: {group.get('name')}</b>\n\n"
                f"❌ Опрос на завтра ({tomorrow.strftime('%d.%m.%Y')}) не найден.\n\n"
                f"Создайте опрос, чтобы увидеть результаты."
            )
        else:
            # Получаем результаты опроса
            results = poll.get('results', {})
            
            # Формируем текст с результатами
            text = (
                f"📊 <b>Результаты опроса: {group.get('name')}</b>\n"
                f"Дата: {tomorrow.strftime('%d.%m.%Y')}\n\n"
            )
            
            if results:
                # TODO: Реализовать форматирование результатов из Telegram API
                text += "📋 <b>Результаты:</b>\n"
                text += "⚠️ Просмотр результатов будет реализован после интеграции с Telegram API"
            else:
                text += "⚠️ Результаты еще не получены."
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        await safe_answer_callback(callback)
        await state.clear()
    
    elif action == "close_poll":
        # Закрытие опроса для группы
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Ищем активный опрос
        poll = await poll_repo.get_by_group_and_date(group_id, tomorrow)
        
        if not poll or poll.get('status') != 'active':
            text = (
                f"🔒 <b>Закрытие опроса: {group.get('name')}</b>\n\n"
                f"❌ Активный опрос на завтра ({tomorrow.strftime('%d.%m.%Y')}) не найден."
            )
            await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
            await safe_answer_callback(callback)
            await state.clear()
            return
        
        # Закрываем опрос
        try:
            chat_id = group['telegram_chat_id']
            topic_id = poll.get('telegram_topic_id')
            
            # Закрываем опрос в Telegram
            if poll.get('telegram_message_id'):
                try:
                    await bot.stop_poll(
                        chat_id=chat_id,
                        message_id=poll['telegram_message_id'],
                        message_thread_id=topic_id
                    )
                except Exception as e:
                    logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
            
            # Закрываем опрос в БД
            await poll_repo.close_poll(str(poll['id']))
            
            text = (
                f"✅ <b>Опрос закрыт!</b>\n\n"
                f"Группа: <b>{group.get('name')}</b>\n"
                f"Дата: {tomorrow.strftime('%d.%m.%Y')}"
            )
            
            await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
            await safe_answer_callback(callback)
            await state.clear()
            
        except Exception as e:
            logger.error("Ошибка при закрытии опроса: %s", e, exc_info=True)
            await safe_edit_message(
                callback.message,
                f"❌ Ошибка при закрытии опроса: {e}",
                reply_markup=get_back_keyboard("admin:polls_menu")
            )
            await safe_answer_callback(callback)
            await state.clear()


@router.callback_query(lambda c: c.data == "admin:polls:close")
@require_admin_callback
async def callback_close_poll_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    """Начало процесса закрытия опроса."""
    groups = await group_service.get_all_groups()
    
    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection_for_topic)
    await state.update_data(action="close_poll")
    
    text = (
        "🔒 <b>Закрытие опроса</b>\n\n"
        "Выберите группу:"
    )
    
    # Создаем клавиатуру с модифицированными callback_data для закрытия опросов
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group_name,
                callback_data=f"admin:poll_group:{group['id']}"
            )
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:close_all")
@require_admin_callback
async def callback_close_all_polls(callback: CallbackQuery, bot: Bot, poll_repo: PollRepository, group_repo: GroupRepository) -> None:
    """Закрытие всех опросов сразу."""
    try:
        active_polls = await poll_repo.get_active_polls()
        
        if not active_polls:
            await safe_edit_message(
                callback.message,
                "ℹ️ Нет активных опросов для закрытия.",
                reply_markup=get_back_keyboard("admin:polls_menu")
            )
            await safe_answer_callback(callback)
            return
        
        await safe_edit_message(
            callback.message,
            f"⏳ Закрытие {len(active_polls)} опросов...",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        
        closed_count = 0
        errors = []
        
        for poll in active_polls:
            try:
                # Закрываем опрос в Telegram
                if poll.get('telegram_poll_id') and poll.get('telegram_message_id'):
                    group = await group_repo.get_by_id(poll['group_id'])
                    if group:
                        chat_id = group['telegram_chat_id']
                        topic_id = poll.get('telegram_topic_id')
                        
                        try:
                            await bot.stop_poll(
                                chat_id=chat_id,
                                message_id=poll['telegram_message_id'],
                                message_thread_id=topic_id
                            )
                        except Exception as e:
                            logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
                            errors.append(f"Группа {group.get('name')}: ошибка закрытия в Telegram")
                
                # Закрываем опрос в БД
                await poll_repo.close_poll(str(poll['id']))
                closed_count += 1
                
            except Exception as e:
                logger.error("Ошибка при закрытии опроса %s: %s", poll.get('id'), e)
                errors.append(f"Опрос {poll.get('id')}: {str(e)}")
        
        if errors:
            error_text = "\n".join(f"❌ {e}" for e in errors[:10])
            if len(errors) > 10:
                error_text += f"\n... и еще {len(errors) - 10} ошибок"
            
            text = (
                f"✅ <b>Закрытие опросов завершено</b>\n\n"
                f"Закрыто опросов: <b>{closed_count}</b>\n\n"
                f"❌ <b>Ошибки:</b>\n{error_text}"
            )
        else:
            text = (
                f"✅ <b>Все опросы закрыты!</b>\n\n"
                f"Закрыто опросов: <b>{closed_count}</b>"
            )
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        
    except Exception as e:
        logger.error("Ошибка при закрытии всех опросов: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при закрытии опросов: {e}",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )


@router.callback_query(lambda c: c.data == "admin:polls:find_tomorrow")
@require_admin_callback
async def callback_find_tomorrow_polls(callback: CallbackQuery, poll_repo: PollRepository, group_service: GroupService) -> None:
    """Поиск опросов на завтра."""
    tomorrow = date.today() + timedelta(days=1)
    groups = await group_service.get_all_groups()
    
    polls_found = []
    polls_missing = []
    
    for group in groups:
        poll = await poll_repo.get_by_group_and_date(group['id'], tomorrow)
        if poll:
            polls_found.append(group)
        else:
            polls_missing.append(group)
    
    text = (
        f"🔎 <b>Опросы на завтра ({tomorrow.strftime('%d.%m.%Y')})</b>\n\n"
        f"✅ Найдено опросов: <b>{len(polls_found)}</b>\n"
        f"❌ Отсутствует опросов: <b>{len(polls_missing)}</b>\n\n"
    )
    
    if polls_found:
        text += "<b>✅ Группы с опросами:</b>\n"
        for group in polls_found:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
        text += "\n"
    
    if polls_missing:
        text += "<b>❌ Группы без опросов:</b>\n"
        for group in polls_missing:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
    await safe_answer_callback(callback)
