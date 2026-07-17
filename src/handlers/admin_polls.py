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
from src.services.group_member_service import GroupMemberService
from src.services.poll_service import PollService
from src.services.group_service import GroupService
from src.services.service_registry import get_scheduler_service
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


def _extract_voted_user_ids(results: dict) -> set[int]:
    voted_user_ids: set[int] = set()
    slots = results.get("slots", {}) if isinstance(results, dict) else {}
    for voters in slots.values():
        if isinstance(voters, list):
            for voter in voters:
                if isinstance(voter, dict) and voter.get("user_id"):
                    voted_user_ids.add(int(voter["user_id"]))

    for voter in results.get("day_off", []) if isinstance(results, dict) else []:
        if isinstance(voter, dict) and voter.get("user_id"):
            voted_user_ids.add(int(voter["user_id"]))
    for bucket_name in ("curator", "night_out", "not_going"):
        for voter in results.get(bucket_name, []) if isinstance(results, dict) else []:
            if isinstance(voter, dict) and voter.get("user_id"):
                voted_user_ids.add(int(voter["user_id"]))

    custom_buckets = results.get("custom", {}) if isinstance(results, dict) else {}
    if isinstance(custom_buckets, dict):
        for voters in custom_buckets.values():
            if isinstance(voters, list):
                for voter in voters:
                    if isinstance(voter, dict) and voter.get("user_id"):
                        voted_user_ids.add(int(voter["user_id"]))

    return voted_user_ids


async def _close_poll_instance(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    poll_repo: PollRepository,
    group: dict,
    poll: dict,
) -> None:
    """Закрыть конкретный опрос и обновить сообщение в админке."""
    scheduler_service = get_scheduler_service()
    if scheduler_service is not None:
        await scheduler_service.close_single_poll_with_reporting(poll, group)
    else:
        if poll.get('telegram_message_id'):
            try:
                await bot.stop_poll(
                    chat_id=group['telegram_chat_id'],
                    message_id=poll['telegram_message_id'],
                )
            except Exception as e:
                logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
        await poll_repo.close_poll(str(poll['id']))

    text = (
        f"✅ <b>Опрос закрыт!</b>\n\n"
        f"Группа: <b>{group.get('name')}</b>\n"
        f"Дата: {poll.get('poll_date').strftime('%d.%m.%Y') if poll.get('poll_date') else '-'}"
    )

    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
    await safe_answer_callback(callback)
    await state.clear()


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


@router.callback_query(lambda c: c.data == "admin:polls:create_one")
@require_admin_callback
async def callback_create_single_poll_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    """Начало создания тестового опроса для одной группы."""
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="create_poll")

    text = (
        "📨 <b>Отправка тестового опроса</b>\n\n"
        "Выберите группу. Опрос будет отправлен на завтрашнюю дату."
    )

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


@router.callback_query(lambda c: c.data == "admin:polls:test_reminder")
@require_admin_callback
async def callback_test_reminder_start(
    callback: CallbackQuery,
    state: FSMContext,
    group_service: GroupService,
) -> None:
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="send_test_reminder")

    text = (
        "🔔 <b>Тест напоминания</b>\n\n"
        "Для дневных групп используется 17:00, для ночных — 12:00.\n"
        "Выберите группу. Бот отправит список тех, кто не отметился, с тегами."
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(text=group_name, callback_data=f"admin:poll_group:{group['id']}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await safe_answer_callback(callback)


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
                            try:
                                await bot.stop_poll(
                                    chat_id=chat_id,
                                    message_id=poll['telegram_message_id'],
                                )
                            except Exception as e:
                                logger.warning("Не удалось закрыть опрос в Telegram: %s", e)
                    except Exception as e:
                        logger.warning("Ошибка при закрытии опроса в Telegram: %s", e)
                
                # Удаляем запись опроса из БД, чтобы можно было создать новый заново
                await poll_repo.delete(str(poll['id']))
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
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection)
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


@router.callback_query(lambda c: c.data == "admin:polls:test_results")
@require_admin_callback
async def callback_test_polls_results_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="view_test_poll_results")

    text = (
        "📊 <b>Результаты тестового опроса</b>\n\n"
        "Выберите группу:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(text=group_name, callback_data=f"admin:poll_group:{group['id']}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:test_close")
@require_admin_callback
async def callback_test_close_poll_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="close_test_poll")

    text = (
        "🔒 <b>Закрытие тестового опроса</b>\n\n"
        "Выберите группу:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(text=group_name, callback_data=f"admin:poll_group:{group['id']}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:test_delete")
@require_admin_callback
async def callback_test_delete_poll_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="delete_test_poll")

    text = (
        "🗑️ <b>Удаление тестового опроса</b>\n\n"
        "Будет удален последний опрос выбранной группы из базы.\n"
        "Выберите группу:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(text=group_name, callback_data=f"admin:poll_group:{group['id']}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:test_delete_all")
@require_admin_callback
async def callback_test_delete_all_polls_start(callback: CallbackQuery, state: FSMContext, group_service: GroupService) -> None:
    groups = await group_service.get_all_groups()

    if not groups:
        await safe_edit_message(
            callback.message,
            "❌ Нет зарегистрированных групп.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        return

    await state.set_state(AdminPanelStates.waiting_for_group_selection)
    await state.update_data(action="delete_all_test_polls")

    text = (
        "🧹 <b>Удаление всех тестовых опросов</b>\n\n"
        "Будут удалены все опросы выбранной группы из базы.\n"
        "Выберите группу:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for group in groups:
        group_name = clean_group_name_for_display(group.get("name", f"Группа {group.get('id', '?')}"))
        if len(group_name) > 30:
            group_name = group_name[:27] + "..."
        keyboard_buttons.append([
            InlineKeyboardButton(text=group_name, callback_data=f"admin:poll_group:{group['id']}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])
    await safe_edit_message(callback.message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data == "admin:polls:test_delete_all_confirm")
@require_admin_callback
async def callback_test_delete_all_polls_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    poll_repo: PollRepository,
    group_service: GroupService,
) -> None:
    data = await state.get_data()
    group_id = data.get("pending_group_id")

    if not group_id:
        await safe_edit_message(
            callback.message,
            "❌ Не удалось определить группу для удаления.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        await state.clear()
        return

    group = await group_service.get_group_by_id(int(group_id))
    deleted_count = await poll_repo.delete_all_by_group(int(group_id))

    if deleted_count == 0:
        text = (
            f"🧹 <b>Удаление всех тестовых опросов</b>\n\n"
            f"❌ Для группы <b>{group.get('name') if group else group_id}</b> в базе нет опросов."
        )
    else:
        text = (
            f"✅ <b>Все тестовые опросы удалены!</b>\n\n"
            f"Группа: <b>{group.get('name') if group else group_id}</b>\n"
            f"Удалено записей: <b>{deleted_count}</b>"
        )

    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
    await safe_answer_callback(callback)
    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:polls:test_close_select:"))
@require_admin_callback
async def callback_test_close_poll_selected(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    poll_repo: PollRepository,
    group_service: GroupService,
) -> None:
    poll_id = callback.data.split(":")[-1]
    data = await state.get_data()
    group_id = data.get("close_test_group_id")

    poll = await poll_repo.get_by_id(poll_id)
    group = await group_service.get_group_by_id(int(group_id)) if group_id else None

    if not poll or not group:
        await safe_edit_message(
            callback.message,
            "❌ Опрос или группа не найдены.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        await state.clear()
        return

    if poll.get("status") != "active":
        await safe_edit_message(
            callback.message,
            "❌ Этот опрос уже закрыт.",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        await state.clear()
        return

    try:
        await _close_poll_instance(
            callback=callback,
            state=state,
            bot=bot,
            poll_repo=poll_repo,
            group=group,
            poll=poll,
        )
    except Exception as e:
        logger.error("Ошибка при закрытии выбранного тестового опроса: %s", e, exc_info=True)
        await safe_edit_message(
            callback.message,
            f"❌ Ошибка при закрытии опроса: {e}",
            reply_markup=get_back_keyboard("admin:polls_menu")
        )
        await safe_answer_callback(callback)
        await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:poll_group:"))
@require_admin_callback
async def callback_select_group_for_polls(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    poll_repo: PollRepository,
    group_repo: GroupRepository,
    group_service: GroupService,
    group_member_service: GroupMemberService,
) -> None:
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
    
    if action == "create_poll":
        poll_service = PollService(bot=bot, poll_repo=poll_repo, group_repo=group_repo)
        target_date = poll_service.get_target_date_for_group(group)
        existing_poll = await poll_repo.get_by_group_and_date(group_id, target_date)
        if existing_poll:
            text = (
                f"ℹ️ <b>Тестовый опрос уже существует</b>\n\n"
                f"Группа: <b>{group.get('name')}</b>\n"
                f"Дата: {target_date.strftime('%d.%m.%Y')}"
            )
        else:
            poll = await poll_service.create_poll_for_group(group_id=group_id)
            if poll:
                text = (
                    f"✅ <b>Тестовый опрос отправлен</b>\n\n"
                    f"Группа: <b>{group.get('name')}</b>\n"
                    f"Дата: {target_date.strftime('%d.%m.%Y')}"
                )
            else:
                text = (
                    f"❌ <b>Не удалось отправить опрос</b>\n\n"
                    f"Проверьте настройки группы <b>{group.get('name')}</b> и слоты."
                )

        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        await safe_answer_callback(callback)
        await state.clear()
        return

    if action == "send_test_reminder":
        scheduler_service = get_scheduler_service()
        if scheduler_service is None:
            text = "❌ Планировщик не инициализирован. Перезапустите бота."
        else:
            ok, result_message = await scheduler_service.send_manual_reminder_for_group(group_id)
            prefix = "✅" if ok else "❌"
            text = f"{prefix} <b>Тест напоминания 17:00</b>\n\n{result_message}"
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        await safe_answer_callback(callback)
        await state.clear()
        return

    if action in {"view_poll_results", "view_test_poll_results"}:
        # Просмотр результатов опроса
        if action == "view_test_poll_results":
            poll = await poll_repo.get_latest_by_group(group_id)
            target_date = poll.get("poll_date") if poll else None
        else:
            target_date = date.today() if group.get("is_night", False) else date.today() + timedelta(days=1)
            poll = await poll_repo.get_by_group_and_date(group_id, target_date)
        
        if not poll:
            not_found_text = (
                "не найден"
                if action == "view_test_poll_results"
                else f"на дату {target_date.strftime('%d.%m.%Y')} не найден"
            )
            text = (
                f"📊 <b>Результаты опросов: {group.get('name')}</b>\n\n"
                f"❌ Опрос {not_found_text}.\n\n"
                f"Создайте опрос, чтобы увидеть результаты."
            )
        else:
            # Формируем текст с результатами
            text = (
                f"📊 <b>Результаты опроса: {group.get('name')}</b>\n"
                f"Дата: {poll.get('poll_date').strftime('%d.%m.%Y') if poll.get('poll_date') else '-'}\n\n"
            )
            
            # Получаем слоты группы для форматирования
            try:
                slots = group_service.get_slots_config(group)
                extra_options = group_service.get_extra_options(group)
                member_names_by_id, member_names_by_user_id = await group_member_service.get_member_name_maps(group_id)
                
                if group.get("is_night", False):
                    results = poll.get('results', {}) if isinstance(poll.get('results'), dict) else {}
                    for title, key in (
                        ("Выхожу", "night_out"),
                        ("Не выхожу", "not_going"),
                        ("Куратор", "curator"),
                        ("Выходной", "day_off"),
                    ):
                        voters = results.get(key, [])
                        text += f"<b>{title}:</b> {len(voters)}\n"
                        for voter in voters[:20]:
                            voter_name = group_member_service.resolve_voter_display_name(
                                voter,
                                member_names_by_id,
                                member_names_by_user_id,
                            )
                            text += f"• {voter_name}\n"
                        text += "\n"
                    custom_results = results.get("custom", {}) if isinstance(results, dict) else {}
                    if isinstance(custom_results, dict):
                        for index, option_text in enumerate(extra_options):
                            voters = custom_results.get(f"option_{index}", [])
                            text += f"<b>{option_text}:</b> {len(voters)}\n"
                            for voter in voters[:20]:
                                voter_name = group_member_service.resolve_voter_display_name(
                                    voter,
                                    member_names_by_id,
                                    member_names_by_user_id,
                                )
                                text += f"• {voter_name}\n"
                            text += "\n"
                    members = await group_member_service.get_group_members(group_id)
                    voted_user_ids = _extract_voted_user_ids(results)
                    not_voted = []
                    for member in members:
                        telegram_user_id = member.get("telegram_user_id")
                        if telegram_user_id is not None and int(telegram_user_id) in settings.ADMIN_IDS:
                            continue
                        if telegram_user_id is None or int(telegram_user_id) not in voted_user_ids:
                            not_voted.append(member.get("full_name", "Неизвестный курьер"))

                    if not_voted:
                        text += "<b>Не отметились:</b>\n"
                        for person in not_voted[:15]:
                            text += f"• {person}\n"
                        if len(not_voted) > 15:
                            text += f"... и еще {len(not_voted) - 15} человек\n"
                        text += "\n"
                elif slots:
                    text += "📋 <b>Результаты по выходам:</b>\n\n"
                    # Формируем структуру результатов
                    results = poll.get('results', {})
                    slot_results_map = results.get('slots', {}) if isinstance(results, dict) else {}
                    
                    if results and isinstance(results, dict) and results:
                        # Если результаты есть в БД, форматируем их
                        for i, slot in enumerate(slots):
                            slot_start = slot.get('start', '?')
                            slot_end = slot.get('end', '?')
                            # Получаем данные о голосах для этого слота (если есть)
                            slot_key = f"slot_{i}"
                            voters = slot_results_map.get(slot_key, []) if isinstance(slot_results_map, dict) else []
                            voters_count = len(voters) if isinstance(voters, list) else 0
                            
                            mark = "✅" if voters_count > 0 else "❌"
                            text += f"{mark} <b>{slot_start} - {slot_end}</b> ({voters_count})\n"
                            
                            if voters and isinstance(voters, list):
                                for voter in voters[:50]:
                                    voter_name = group_member_service.resolve_voter_display_name(
                                        voter,
                                        member_names_by_id,
                                        member_names_by_user_id,
                                    )
                                    text += f"• {voter_name}\n"
                            
                            text += "\n"

                        curator = results.get('curator', [])
                        if curator:
                            text += f"<b>Куратор:</b> {len(curator)}\n"
                            for person in curator[:20]:
                                person_name = group_member_service.resolve_voter_display_name(
                                    person,
                                    member_names_by_id,
                                    member_names_by_user_id,
                                )
                                text += f"• {person_name}\n"
                            text += "\n"
                        
                        # Выходной
                        day_off = results.get('day_off', [])
                        if day_off:
                            day_off_count = len(day_off) if isinstance(day_off, list) else 0
                            text += f"<b>Выходной:</b> {day_off_count}\n"
                            if isinstance(day_off, list):
                                for person in day_off[:10]:  # Показываем первые 10
                                    person_name = group_member_service.resolve_voter_display_name(
                                        person,
                                        member_names_by_id,
                                        member_names_by_user_id,
                                    )
                                    text += f"• {person_name}\n"
                                if len(day_off) > 10:
                                    text += f"... и еще {len(day_off) - 10} человек\n"
                            text += "\n"

                        custom_results = results.get("custom", {}) if isinstance(results, dict) else {}
                        if isinstance(custom_results, dict):
                            for index, option_text in enumerate(extra_options):
                                voters = custom_results.get(f"option_{index}", [])
                                if voters:
                                    text += f"<b>{option_text}:</b> {len(voters)}\n"
                                    for person in voters[:20]:
                                        person_name = group_member_service.resolve_voter_display_name(
                                            person,
                                            member_names_by_id,
                                            member_names_by_user_id,
                                        )
                                        text += f"• {person_name}\n"
                                    text += "\n"

                        members = await group_member_service.get_group_members(group_id)
                        voted_user_ids = _extract_voted_user_ids(results)
                        not_voted = []
                        for member in members:
                            telegram_user_id = member.get("telegram_user_id")
                            if telegram_user_id is not None and int(telegram_user_id) in settings.ADMIN_IDS:
                                continue
                            if telegram_user_id is None or int(telegram_user_id) not in voted_user_ids:
                                not_voted.append(member.get("full_name", "Неизвестный курьер"))

                        if not_voted:
                            text += "\n<b>Не отметились:</b>\n"
                            for person in not_voted[:15]:
                                text += f"• {person}\n"
                            if len(not_voted) > 15:
                                text += f"... и еще {len(not_voted) - 15} человек\n"
                    else:
                        # Если результатов нет, показываем структуру слотов
                        text += "⚠️ <b>Результаты еще не получены.</b>\n\n"
                        text += "💡 <b>Примечание:</b> Результаты опроса будут доступны после его закрытия или при получении обновлений от Telegram.\n\n"
                        text += "📋 <b>Настроенные выходы:</b>\n"
                        for i, slot in enumerate(slots):
                            slot_start = slot.get('start', '?')
                            slot_end = slot.get('end', '?')
                            text += f"• {slot_start} - {slot_end}\n"
                        if extra_options:
                            text += "\n📝 <b>Дополнительные ответы:</b>\n"
                            for option_text in extra_options:
                                text += f"• {option_text}\n"
                else:
                    text += "⚠️ У группы не настроены выходы."
                    
            except Exception as e:
                logger.error("Ошибка при получении результатов опроса: %s", e, exc_info=True)
                text += f"⚠️ Ошибка при получении результатов: {e}"
        
        await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
        await safe_answer_callback(callback)
        await state.clear()
    
    elif action in {"close_poll", "close_test_poll", "delete_test_poll", "delete_all_test_polls"}:
        # Закрытие опроса для группы
        if action == "delete_all_test_polls":
            await state.update_data(pending_group_id=group_id)
            text = (
                f"🧹 <b>Удаление всех тестовых опросов</b>\n\n"
                f"Группа: <b>{group.get('name')}</b>\n\n"
                f"⚠️ Будут удалены все опросы этой группы из базы данных.\n"
                f"Продолжить?"
            )
            await safe_edit_message(
                callback.message,
                text,
                reply_markup=get_confirmation_keyboard(
                    "admin:polls:test_delete_all_confirm",
                    "admin:polls_menu",
                ),
            )
            await safe_answer_callback(callback)
            return
        if action == "delete_test_poll":
            poll = await poll_repo.get_latest_by_group(group_id)
            target_date = poll.get("poll_date") if poll else None
        elif action == "close_test_poll":
            active_polls = await poll_repo.get_active_polls(group_id)
            if len(active_polls) > 1:
                await state.update_data(close_test_group_id=group_id)

                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard_buttons = []
                for poll_item in active_polls:
                    poll_date = poll_item.get("poll_date")
                    created_at = poll_item.get("created_at")
                    label = poll_date.strftime('%d.%m.%Y') if poll_date else "Без даты"
                    if created_at:
                        label += f" · {created_at.strftime('%H:%M')}"
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=label,
                            callback_data=f"admin:polls:test_close_select:{poll_item['id']}"
                        )
                    ])
                keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin:polls_menu")])

                text = (
                    f"🔒 <b>Выбор тестового опроса для закрытия</b>\n\n"
                    f"Группа: <b>{group.get('name')}</b>\n"
                    f"Найдено активных опросов: <b>{len(active_polls)}</b>\n\n"
                    f"Выберите, какой опрос закрыть:"
                )
                await safe_edit_message(
                    callback.message,
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
                )
                await safe_answer_callback(callback)
                return
            poll = active_polls[0] if active_polls else None
            target_date = poll.get("poll_date") if poll else None
        else:
            target_date = date.today() if group.get("is_night", False) else date.today() + timedelta(days=1)
            poll = await poll_repo.get_by_group_and_date(group_id, target_date)
        
        poll_missing = poll is None or (action in {"close_poll", "close_test_poll"} and poll.get('status') != 'active')
        if poll_missing:
            not_found_text = (
                "тестовый опрос не найден"
                if action == "delete_test_poll"
                else
                "тестовый опрос не найден"
                if action == "close_test_poll"
                else f"опрос на дату {target_date.strftime('%d.%m.%Y')} не найден"
            )
            text = (
                f"{'🗑️' if action == 'delete_test_poll' else '🔒'} <b>{'Удаление' if action == 'delete_test_poll' else 'Закрытие'} опроса: {group.get('name')}</b>\n\n"
                f"❌ {'Последний' if action == 'delete_test_poll' else 'Активный'} {not_found_text}."
            )
            await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
            await safe_answer_callback(callback)
            await state.clear()
            return
        
        try:
            if action == "delete_test_poll":
                deleted = await poll_repo.delete(str(poll['id']))
                if not deleted:
                    raise RuntimeError("Не удалось удалить опрос из БД")
                text = (
                    f"✅ <b>Тестовый опрос удален!</b>\n\n"
                    f"Группа: <b>{group.get('name')}</b>\n"
                    f"Дата: {poll.get('poll_date').strftime('%d.%m.%Y') if poll.get('poll_date') else '-'}"
                )
                await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
                await safe_answer_callback(callback)
                await state.clear()
                return

            await _close_poll_instance(
                callback=callback,
                state=state,
                bot=bot,
                poll_repo=poll_repo,
                group=group,
                poll=poll,
            )
            
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
    
    await state.set_state(AdminPanelStates.waiting_for_group_selection)
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
                        try:
                            await bot.stop_poll(
                                chat_id=group['telegram_chat_id'],
                                message_id=poll['telegram_message_id'],
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
    """Поиск запланированных опросов для дневных и ночных групп."""
    tomorrow = date.today() + timedelta(days=1)
    today = date.today()
    groups = await group_service.get_all_groups()
    
    day_polls_found = []
    day_polls_missing = []
    night_polls_found = []
    night_polls_missing = []
    
    for group in groups:
        target_date = today if group.get("is_night", False) else tomorrow
        poll = await poll_repo.get_by_group_and_date(group['id'], target_date)

        if group.get("is_night", False):
            if poll:
                night_polls_found.append(group)
            else:
                night_polls_missing.append(group)
        else:
            if poll:
                day_polls_found.append(group)
            else:
                day_polls_missing.append(group)
    
    text = (
        f"🔎 <b>Проверка опросов</b>\n\n"
        f"☀️ Дневные группы: дата <b>{tomorrow.strftime('%d.%m.%Y')}</b>\n"
        f"✅ Найдено: <b>{len(day_polls_found)}</b>\n"
        f"❌ Отсутствует: <b>{len(day_polls_missing)}</b>\n\n"
        f"🌙 Ночные группы: дата <b>{today.strftime('%d.%m.%Y')}</b>\n"
        f"✅ Найдено: <b>{len(night_polls_found)}</b>\n"
        f"❌ Отсутствует: <b>{len(night_polls_missing)}</b>\n\n"
    )
    
    if day_polls_found:
        text += "<b>✅ Дневные группы с опросами:</b>\n"
        for group in day_polls_found:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
        text += "\n"
    
    if day_polls_missing:
        text += "<b>❌ Дневные группы без опросов:</b>\n"
        for group in day_polls_missing:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
        text += "\n"

    if night_polls_found:
        text += "<b>✅ Ночные группы с опросами:</b>\n"
        for group in night_polls_found:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
        text += "\n"

    if night_polls_missing:
        text += "<b>❌ Ночные группы без опросов:</b>\n"
        for group in night_polls_missing:
            group_name = clean_group_name_for_display(group.get('name', 'Неизвестная группа'))
            text += f"• {group_name}\n"
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:polls_menu"))
    await safe_answer_callback(callback)
