"""Управление пользователями через админ-панель."""
import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.user_service import UserService
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin, require_admin_callback
from src.utils.admin_keyboards import create_verified_users_keyboard, create_user_edit_keyboard
from src.utils.telegram_helpers import safe_edit_message

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:list_verified")
@require_admin_callback
async def callback_list_verified(
    callback: CallbackQuery,
    user_service: UserService,
    state: FSMContext,
) -> None:
    """Показать список верифицированных пользователей."""
    # Очищаем состояние при возврате к списку
    await state.clear()
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_verified_users()
    
    # Сортируем по фамилии и имени
    users.sort(key=lambda u: (u.last_name or "", u.first_name or "", u.id))
    
    if not users:
        text = "❌ <b>Нет верифицированных пользователей</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
    else:
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page
        
        text = (
            f"✅ <b>Верифицированные пользователи</b>\n\n"
            f"Всего: <b>{len(users)}</b> | Страница 1/{total_pages}\n\n"
            f"Нажмите на пользователя для редактирования имени или фамилии."
        )
        
        keyboard = create_verified_users_keyboard(users, page=0)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:verified_page_"))
@require_admin_callback
async def callback_verified_page(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Навигация по страницам верифицированных пользователей."""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_verified_users()
    
    # Сортируем по фамилии и имени
    users.sort(key=lambda u: (u.last_name or "", u.first_name or "", u.id))
    
    if not users:
        text = "❌ <b>Нет верифицированных пользователей</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
    else:
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        
        text = (
            f"✅ <b>Верифицированные пользователи</b>\n\n"
            f"Всего: <b>{len(users)}</b> | Страница {page + 1}/{total_pages}\n\n"
            f"Нажмите на пользователя для редактирования имени или фамилии."
        )
        
        keyboard = create_verified_users_keyboard(users, page=page)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:edit_user_") and not c.data.startswith("admin:edit_user_lastname_") and not c.data.startswith("admin:edit_user_firstname_") and not c.data.startswith("admin:edit_user_name_") and not c.data.startswith("admin:delete_user_"))
@require_admin_callback
async def callback_edit_user(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Показать меню редактирования пользователя."""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    if not user.is_verified:
        await callback.answer("❌ Пользователь не верифицирован", show_alert=True)
        return
    
    full_name = user.get_full_name() or user.username or f"User {user.id}"
    current_firstname = user.first_name or "не указано"
    current_lastname = user.last_name or "не указано"
    
    text = (
        f"✏️ <b>Редактирование пользователя</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Полное имя: <b>{full_name}</b>\n\n"
        f"Текущие данные:\n"
        f"• Фамилия: <b>{current_lastname}</b>\n"
        f"• Имя: <b>{current_firstname}</b>\n"
        f"{f'• Username: @{user.username}' if user.username else ''}\n\n"
        f"Выберите, что хотите изменить:"
    )
    
    keyboard = create_user_edit_keyboard(user_id)
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:edit_user_name_"))
@require_admin_callback
async def callback_edit_user_name(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Запросить ввод имени и фамилии пользователя."""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await state.update_data(edit_user_id=user_id)
    
    current_full_name = user.get_full_name() or user.username or f"User {user_id}"
    current_firstname = user.first_name or "не указано"
    current_lastname = user.last_name or "не указано"
    
    text = (
        f"✏️ <b>Изменение имени и фамилии</b>\n\n"
        f"Пользователь: <b>{current_full_name}</b>\n\n"
        f"Текущие данные:\n"
        f"• Фамилия: <b>{current_lastname}</b>\n"
        f"• Имя: <b>{current_firstname}</b>\n\n"
        f"Введите <b>Фамилию и Имя</b> через пробел:\n"
        f"Формат: <b>Фамилия Имя</b>\n"
        f"Пример: <code>Иванов Иван</code>\n\n"
        f"Для отмены введите: <code>отмена</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:edit_user_{user_id}")],
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin:list_verified")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_user_name_edit)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_user_name_edit))
@require_admin
async def process_user_name_edit(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработать введенные имя и фамилию пользователя."""
    from src.utils.name_validator import validate_full_name
    
    data = await state.get_data()
    user_id = data.get("edit_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя. Начните заново.")
        await state.clear()
        return
    
    # Проверяем на отмену
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Изменение отменено")
        return
    
    # Проверяем формат ввода
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте текстовое сообщение с Фамилией и Именем.\n\n"
            "Формат: <b>Фамилия Имя</b>\n"
            "Пример: <code>Иванов Иван</code>"
        )
        return
    
    # Валидируем имя
    is_valid, last_name, first_name, error_message = validate_full_name(message.text)
    if not is_valid:
        await message.answer(f"❌ {error_message}")
        return
    
    # Обновляем имя и фамилию через user_service
    # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
    updated_user = await user_service.user_repo.update(user_id, first_name=first_name, last_name=last_name)
    
    if updated_user:
        full_name_display = updated_user.get_full_name()
        
        await message.answer(
            f"✅ <b>Имя и фамилия изменены!</b>\n\n"
            f"Фамилия: <b>{last_name}</b>\n"
            f"Имя: <b>{first_name}</b>\n"
            f"Полное имя: <b>{full_name_display}</b>"
        )
        
        await state.clear()
    else:
        await message.answer("❌ Ошибка при изменении имени и фамилии. Попробуйте еще раз.")


@router.callback_query(lambda c: c.data and c.data.startswith("admin:delete_user_") and not c.data.startswith("admin:delete_user_confirm_"))
@require_admin_callback
async def callback_delete_user(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Показать подтверждение удаления пользователя."""
    try:
        user_id = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return
    
    user_repo = user_service.user_repo
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    full_name = user.get_full_name() or user.username or f"User {user_id}"
    
    text = (
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить пользователя?\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Имя: <b>{full_name}</b>\n\n"
        f"⚠️ <b>Внимание!</b> При удалении будут также удалены:\n"
        f"• Все голоса пользователя в опросах\n"
        f"• Все данные пользователя\n\n"
        f"Это действие <b>необратимо</b>!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin:delete_user_confirm_{user_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:edit_user_{user_id}")],
    ])
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:delete_user_confirm_"))
@require_admin_callback
async def callback_delete_user_confirm(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Подтвердить и выполнить удаление пользователя."""
    logger.info("callback_delete_user_confirm called with data: %s", callback.data)
    try:
        user_id = int(callback.data.split("_")[-1])
        logger.info("Parsed user_id: %s", user_id)
    except (ValueError, IndexError) as e:
        logger.error("Error parsing user_id from callback data '%s': %s", callback.data, e)
        await callback.answer("❌ Ошибка: неверный ID пользователя", show_alert=True)
        return
    
    user_repo = user_service.user_repo
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    full_name = user.get_full_name() or user.username or f"User {user_id}"
    
    # Удаляем пользователя
    try:
        logger.info("Attempting to delete user %s", user_id)
        deleted = await user_repo.delete(user_id)
        logger.info("Delete result for user %s: %s", user_id, deleted)
        
        if deleted:
            text = (
                f"✅ <b>Пользователь удален</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                f"Имя: <b>{full_name}</b>\n\n"
                f"Все данные пользователя и его голоса были удалены."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin:list_verified")],
            ])
            
            await safe_edit_message(callback.message, text, reply_markup=keyboard)
            await callback.answer("✅ Пользователь удален", show_alert=True)
        else:
            logger.error("Failed to delete user %s: delete() returned False", user_id)
            await callback.answer("❌ Ошибка при удалении пользователя. Проверьте логи.", show_alert=True)
    except Exception as e:  # noqa: BLE001
        logger.error("Exception while deleting user %s: %s", user_id, e, exc_info=True)
        try:
            await callback.answer("❌ Ошибка при удалении пользователя. Проверьте логи.", show_alert=True)
        except Exception:  # noqa: BLE001
            logger.error("Failed to answer callback after error", exc_info=True)

