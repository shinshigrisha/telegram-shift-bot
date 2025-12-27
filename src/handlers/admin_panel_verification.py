"""Верификация пользователей через админ-панель."""
import logging
from typing import Optional

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.user_service import UserService
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin, require_admin_callback
from src.utils.admin_keyboards import (
    get_verification_menu_keyboard,
    create_unverified_users_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:verification_menu")
@require_admin_callback
async def callback_verification_menu(callback: CallbackQuery) -> None:
    """Меню управления верификацией."""
    text = (
        "👤 <b>Управление верификацией пользователей</b>\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_verification_menu_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:list_unverified")
@require_admin_callback
async def callback_list_unverified(
    callback: CallbackQuery,
    user_service: UserService,
    state: FSMContext,
) -> None:
    """Показать список неверифицированных пользователей."""
    # Очищаем состояние при возврате к списку
    await state.clear()
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_unverified_users()
    
    if not users:
        text = "✅ <b>Все пользователи верифицированы!</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
    else:
        users_with_username = [u for u in users if u.username]
        users_without_username = [u for u in users if not u.username]
        
        text = (
            f"📋 <b>Неверифицированные пользователи</b>\n\n"
            f"Всего: <b>{len(users)}</b>\n"
            f"• С username: {len(users_with_username)}\n"
            f"• Без username: {len(users_without_username)}\n\n"
            f"Нажмите на пользователя для верификации или используйте массовую верификацию."
        )
        
        keyboard = create_unverified_users_keyboard(users, page=0)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:unverified_page_"))
@require_admin_callback
async def callback_unverified_page(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Навигация по страницам неверифицированных пользователей."""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0
    
    # Используем репозиторий из middleware через user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_unverified_users()
    
    if not users:
        text = "✅ <b>Все пользователи верифицированы!</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
    else:
        users_with_username = [u for u in users if u.username]
        users_without_username = [u for u in users if not u.username]
        
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        
        text = (
            f"📋 <b>Неверифицированные пользователи</b>\n\n"
            f"Всего: <b>{len(users)}</b> | Страница {page + 1}/{total_pages}\n"
            f"• С username: {len(users_with_username)}\n"
            f"• Без username: {len(users_without_username)}\n\n"
            f"Нажмите на пользователя для верификации."
        )
        
        keyboard = create_unverified_users_keyboard(users, page=page)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:verify_user_"))
@require_admin_callback
async def callback_verify_user(
    callback: CallbackQuery,
    user_service: UserService,
    state: FSMContext,
) -> None:
    """Запросить ввод имени и фамилии для верификации пользователя."""
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
    
    if user.is_verified:
        await callback.answer("ℹ️ Пользователь уже верифицирован", show_alert=True)
        return
    
    # Сохраняем user_id в состоянии
    await state.update_data(verification_user_id=user_id)
    
    # Показываем текущие данные пользователя (если есть)
    current_info = ""
    if user.first_name or user.last_name:
        current_name = user.get_full_name()
        current_info = f"\n\nТекущие данные: <b>{current_name}</b>"
    elif user.username:
        current_info = f"\n\nТекущий username: <b>@{user.username}</b>"
    
    text = (
        f"👤 <b>Верификация пользователя</b>\n\n"
        f"ID: <code>{user_id}</code>{current_info}\n\n"
        f"Введите <b>Фамилию и Имя</b> через пробел:\n"
        f"Формат: <b>Фамилия Имя</b>\n"
        f"Пример: <code>Иванов Иван</code>\n\n"
        f"Для отмены введите: <code>отмена</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:list_unverified")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_verification_name)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_verification_name))
@require_admin
async def process_verification_name(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """Обработать введенные имя и фамилию для верификации."""
    from src.utils.name_validator import validate_full_name
    
    # Получаем user_id из состояния
    data = await state.get_data()
    user_id = data.get("verification_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя. Начните заново.")
        await state.clear()
        return
    
    # Проверяем на отмену
    if message.text and message.text.strip().lower() == "отмена":
        await message.answer("❌ Верификация отменена")
        await state.clear()
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
    
    # Верифицируем пользователя через user_service
    # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
    verified_user = await user_service.verify_user(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name
    )
    
    if verified_user:
        full_name_display = verified_user.get_full_name()
        
        # Восстанавливаем права пользователя во всех группах
        try:
            from aiogram import Bot
            bot = Bot.get_current(no_error=True)
            if bot:
                restored_count, failed_count, skipped_count = await user_service.restore_user_permissions(
                    bot=bot,
                    user_id=user_id,
                    state=state,
                )
                logger.info(
                    "Restored permissions for user %s: %d restored, %d failed, %d skipped",
                    user_id,
                    restored_count,
                    failed_count,
                    skipped_count
                )
        except Exception as e:
            logger.error("Error restoring permissions for user %s: %s", user_id, e, exc_info=True)
        
        # Отправляем подтверждение
        await message.answer(
            f"✅ <b>Пользователь верифицирован!</b>\n\n"
            f"Фамилия: <b>{last_name}</b>\n"
            f"Имя: <b>{first_name}</b>\n\n"
            f"Теперь пользователь может участвовать в опросах и писать в группах."
        )
        
        # Обновляем список неверифицированных пользователей
        users = await user_service.user_repo.get_unverified_users()
        
        # Отправляем обновленный список
        if not users:
            text = "✅ <b>Все пользователи верифицированы!</b>"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
            ])
        else:
            users_with_username = [u for u in users if u.username]
            users_without_username = [u for u in users if not u.username]
            
            text = (
                f"📋 <b>Неверифицированные пользователи</b>\n\n"
                f"Всего: <b>{len(users)}</b>\n"
                f"• С username: {len(users_with_username)}\n"
                f"• Без username: {len(users_without_username)}\n\n"
                f"Нажмите на пользователя для верификации или используйте массовую верификацию."
            )
            keyboard = create_unverified_users_keyboard(users, page=0)
        
        # Отправляем обновленный список
        await message.answer(text, reply_markup=keyboard)
        
        await state.clear()
    else:
        await message.answer("❌ Ошибка при верификации пользователя")
        await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:verify_page_"))
@require_admin_callback
async def callback_verify_page(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Верифицировать всех пользователей на текущей странице."""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0
    
    # Используем user_repo из user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_unverified_users()
    
    if not users:
        await callback.answer("✅ Все пользователи уже верифицированы!", show_alert=True)
        return
    
    per_page = 10
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    user_ids = [u.id for u in page_users]
    verified_count = await user_repo.verify_users_batch(user_ids)
    
    if verified_count > 0:
        # Восстанавливаем права для всех верифицированных пользователей
        try:
            from aiogram import Bot
            bot = Bot.get_current(no_error=True)
            if bot:
                for user_id in user_ids:
                    try:
                        await user_service.restore_user_permissions(
                            bot=bot,
                            user_id=user_id,
                        )
                    except Exception as e:
                        logger.warning("Failed to restore permissions for user %s: %s", user_id, e)
        except Exception as e:
            logger.error("Error restoring permissions during batch verification: %s", e, exc_info=True)
        
        # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        await callback.answer(f"✅ Верифицировано {verified_count} пользователей", show_alert=True)
        
        # Обновляем список
        users = await user_repo.get_unverified_users()
        if not users:
            text = "✅ <b>Все пользователи верифицированы!</b>"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
            ])
        else:
            users_with_username = [u for u in users if u.username]
            users_without_username = [u for u in users if not u.username]
            
            total_pages = (len(users) + per_page - 1) // per_page
            current_page = min(page, total_pages - 1) if total_pages > 0 else 0
            
            text = (
                f"📋 <b>Неверифицированные пользователи</b>\n\n"
                f"Всего: <b>{len(users)}</b> | Страница {current_page + 1}/{total_pages}\n"
                f"• С username: {len(users_with_username)}\n"
                f"• Без username: {len(users_without_username)}\n\n"
                f"Нажмите на пользователя для верификации."
            )
            keyboard = create_unverified_users_keyboard(users, page=current_page)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("ℹ️ На этой странице нет пользователей для верификации", show_alert=True)


@router.callback_query(lambda c: c.data == "admin:verify_all_confirm")
@require_admin_callback
async def callback_verify_all_confirm(callback: CallbackQuery) -> None:
    """Подтверждение массовой верификации всех пользователей."""
    text = (
        "⚠️ <b>Внимание!</b>\n\n"
        "Вы уверены, что хотите верифицировать <b>ВСЕХ</b> неверифицированных пользователей?\n\n"
        "Это действие нельзя отменить."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, верифицировать всех", callback_data="admin:verify_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:list_unverified")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:verify_all")
@require_admin_callback
async def callback_verify_all(
    callback: CallbackQuery,
    user_service: UserService,
) -> None:
    """Верифицировать всех неверифицированных пользователей."""
    # Используем user_repo из user_service
    user_repo = user_service.user_repo
    users = await user_repo.get_unverified_users()
    
    if not users:
        await callback.answer("✅ Все пользователи уже верифицированы!", show_alert=True)
        text = "✅ <b>Все пользователи верифицированы!</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        return
    
    user_ids = [u.id for u in users]
    verified_count = await user_repo.verify_users_batch(user_ids)
    
    if verified_count > 0:
        # Восстанавливаем права для всех верифицированных пользователей
        try:
            from aiogram import Bot
            bot = Bot.get_current(no_error=True)
            if bot:
                restored_total = 0
                for user_id in user_ids:
                    try:
                        restored_count, failed_count, skipped_count = await user_service.restore_user_permissions(
                            bot=bot,
                            user_id=user_id,
                        )
                        restored_total += restored_count
                    except Exception as e:
                        logger.warning("Failed to restore permissions for user %s: %s", user_id, e)
                logger.info("Restored permissions for %d users (total groups: %d)", len(user_ids), restored_total)
        except Exception as e:
            logger.error("Error restoring permissions during mass verification: %s", e, exc_info=True)
        
        # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        await callback.answer(f"✅ Верифицировано {verified_count} пользователей", show_alert=True)
        
        text = (
            f"✅ <b>Массовая верификация завершена!</b>\n\n"
            f"Верифицировано пользователей: <b>{verified_count}</b>\n\n"
            f"Теперь все пользователи могут участвовать в опросах и писать в группах."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("❌ Ошибка при верификации", show_alert=True)

