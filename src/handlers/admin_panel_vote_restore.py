"""Восстановление голосов через админ-панель."""
import logging
from typing import Optional

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository
from src.repositories.group_repository import GroupRepository
from src.models.database import AsyncSessionLocal
from src.utils.auth import require_admin_callback
from src.utils.group_formatters import clean_group_name_for_display
from src.utils.admin_keyboards import create_restore_votes_keyboard, create_slot_selection_keyboard
from src.utils.vote_restore import get_restorable_votes, add_vote_manually

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:restore_votes_menu")
@require_admin_callback
async def callback_restore_votes_menu(callback: CallbackQuery) -> None:
    """Меню восстановления голосов."""
    restorable_votes = await get_restorable_votes()
    
    if not restorable_votes:
        text = (
            "🔄 <b>Восстановление голосов</b>\n\n"
            "✅ Нет голосов для восстановления.\n\n"
            "Все верифицированные пользователи уже проголосовали или не было попыток голосования."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
        ])
    else:
        # Группируем по опросам
        active_polls = [v for v in restorable_votes if v.get("poll_status") == "active"]
        closed_polls = [v for v in restorable_votes if v.get("poll_status") == "closed"]
        
        text = (
            f"🔄 <b>Восстановление голосов</b>\n\n"
            f"Найдено попыток голосования верифицированных пользователей: <b>{len(restorable_votes)}</b>\n\n"
            f"• Активные опросы: <b>{len(active_polls)}</b>\n"
            f"• Закрытые опросы: <b>{len(closed_polls)}</b>\n\n"
            f"Выберите попытку голосования для восстановления:"
        )
        keyboard = create_restore_votes_keyboard(restorable_votes, page=0)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:restore_votes_page_"))
@require_admin_callback
async def callback_restore_votes_page(callback: CallbackQuery) -> None:
    """Пагинация списка голосов для восстановления."""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0
    
    restorable_votes = await get_restorable_votes()
    
    if not restorable_votes:
        await callback.answer("❌ Нет голосов для восстановления", show_alert=True)
        return
    
    active_polls = [v for v in restorable_votes if v.get("poll_status") == "active"]
    closed_polls = [v for v in restorable_votes if v.get("poll_status") == "closed"]
    
    text = (
        f"🔄 <b>Восстановление голосов</b>\n\n"
        f"Найдено попыток голосования верифицированных пользователей: <b>{len(restorable_votes)}</b>\n\n"
        f"• Активные опросы: <b>{len(active_polls)}</b>\n"
        f"• Закрытые опросы: <b>{len(closed_polls)}</b>\n\n"
        f"Выберите попытку голосования для восстановления:"
    )
    keyboard = create_restore_votes_keyboard(restorable_votes, page=page)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:restore_vote_") and not c.data.startswith("admin:restore_vote_slot_") and not c.data.startswith("admin:restore_vote_dayoff_"))
@require_admin_callback
async def callback_restore_vote(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора попытки голосования для восстановления."""
    # Парсим данные из callback_data: admin:restore_vote_{user_id}_{poll_id}
    # Используем rsplit с ограничением, чтобы правильно разделить даже если poll_id содержит подчеркивания
    try:
        # Убираем префикс "admin:restore_vote_"
        data_part = callback.data[len("admin:restore_vote_"):]
        
        # Разделяем на user_id и poll_id (rsplit с ограничением 1, чтобы разделить только последнее подчеркивание)
        parts = data_part.rsplit("_", 1)
        if len(parts) != 2:
            logger.error("Неверный формат callback_data для restore_vote: %s, data_part: %s, parts: %s", 
                        callback.data, data_part, parts)
            await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
            return
        
        user_id = int(parts[0])
        poll_id = parts[1]  # telegram_poll_id
        
        if not poll_id or not poll_id.strip():
            logger.error("Пустой poll_id в callback_data: %s", callback.data)
            await callback.answer("❌ Ошибка: неверный формат данных (пустой poll_id)", show_alert=True)
            return
        
    except (ValueError, IndexError, AttributeError) as e:
        logger.error("Ошибка парсинга callback_data для restore_vote: %s, callback_data: %s", e, callback.data)
        await callback.answer("❌ Ошибка: неверный ID пользователя или опроса", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        user_repo = UserRepository(session)
        group_repo = GroupRepository(session)
        
        # Получаем опрос
        poll = await poll_repo.get_by_telegram_poll_id(poll_id)
        if not poll:
            await callback.answer("❌ Опрос не найден", show_alert=True)
            return
        
        # Проверяем, что опрос активен или закрыт
        if poll.status not in ["active", "closed"]:
            await callback.answer("❌ Опрос не может быть восстановлен (статус: {})".format(poll.status), show_alert=True)
            return
        
        # Получаем пользователя
        user = await user_repo.get_by_id(user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        if not user.is_verified:
            await callback.answer("❌ Пользователь не верифицирован", show_alert=True)
            return
        
        # Проверяем, не голосовал ли пользователь уже
        from sqlalchemy import select
        from src.models.user_vote import UserVote
        
        existing_vote_result = await session.execute(
            select(UserVote).where(
                UserVote.poll_id == poll.id,
                UserVote.user_id == user_id
            )
        )
        existing_vote = existing_vote_result.scalar_one_or_none()
        
        if existing_vote:
            await callback.answer(
                "ℹ️ Пользователь уже проголосовал в этом опросе",
                show_alert=True
            )
            return
        
        # Получаем группу
        group = await group_repo.get_by_id(poll.group_id)
        
        # Если опрос активен, предлагаем пользователю проголосовать заново
        if poll.status == "active":
            text = (
                f"🔄 <b>Восстановление голоса</b>\n\n"
                f"Пользователь: <b>{user.get_full_name()}</b>\n"
                f"Группа: <b>{clean_group_name_for_display(group.name) if group else 'Unknown'}</b>\n"
                f"Дата опроса: <b>{poll.poll_date}</b>\n\n"
                f"⚠️ Опрос еще <b>активен</b>.\n\n"
                f"Рекомендуется попросить пользователя проголосовать заново в Telegram.\n\n"
                f"Если пользователь не может проголосовать, выберите слот вручную:"
            )
            
            # Получаем слоты
            slots = await poll_repo.get_poll_slots(poll.id)
            
            if slots:
                keyboard = create_slot_selection_keyboard(slots, poll_id, user_id, include_day_off=True)
            else:
                # Для ночных опросов или опросов без слотов
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚫 Выходной", callback_data=f"admin:restore_vote_dayoff_{poll_id}_{user_id}")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:restore_votes_menu")],
                ])
        else:
            # Опрос закрыт - можно только вручную добавить голос
            text = (
                f"🔄 <b>Восстановление голоса</b>\n\n"
                f"Пользователь: <b>{user.get_full_name()}</b>\n"
                f"Группа: <b>{clean_group_name_for_display(group.name) if group else 'Unknown'}</b>\n"
                f"Дата опроса: <b>{poll.poll_date}</b>\n"
                f"Статус: <b>Закрыт</b>\n\n"
                f"⚠️ Опрос уже закрыт. Выберите слот для восстановления голоса:"
            )
            
            # Получаем слоты
            slots = await poll_repo.get_poll_slots(poll.id)
            
            if slots:
                keyboard = create_slot_selection_keyboard(slots, poll_id, user_id, include_day_off=True)
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚫 Выходной", callback_data=f"admin:restore_vote_dayoff_{poll_id}_{user_id}")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:restore_votes_menu")],
                ])
        
        # Сохраняем данные в состоянии
        await state.update_data(
            restore_vote_user_id=user_id,
            restore_vote_poll_id=poll_id,
            restore_vote_poll_db_id=str(poll.id),
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()


@router.callback_query(lambda c: c.data and (c.data.startswith("admin:restore_vote_slot_") or c.data.startswith("admin:restore_vote_dayoff_")))
@require_admin_callback
async def callback_restore_vote_slot(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора слота для восстановления голоса."""
    data = await state.get_data()
    user_id = data.get("restore_vote_user_id")
    poll_db_id = data.get("restore_vote_poll_db_id")
    
    if not user_id or not poll_db_id:
        await callback.answer("❌ Ошибка: данные не найдены. Начните заново.", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        poll_repo = PollRepository(session)
        user_repo = UserRepository(session)
        group_repo = GroupRepository(session)
        
        poll = await poll_repo.get_by_id(poll_db_id)
        user = await user_repo.get_by_id(user_id)
        group = await group_repo.get_by_id(poll.group_id) if poll else None
        
        if not poll or not user:
            await callback.answer("❌ Ошибка: опрос или пользователь не найдены", show_alert=True)
            return
        
        # Определяем слот или "Выходной"
        if callback.data.startswith("admin:restore_vote_dayoff_"):
            slot_id = None
            voted_option = "Выходной"
            slot_info = "Выходной"
        else:
            # Парсим slot_id из callback_data: admin:restore_vote_slot_{poll_id}_{user_id}_{slot_id}
            parts = callback.data.split("_")
            try:
                slot_id = int(parts[5])
                slot = await poll_repo.get_poll_slots(poll_db_id)
                slot_obj = next((s for s in slot if s.id == slot_id), None)
                if slot_obj:
                    voted_option = f"Слот {slot_obj.slot_number}"
                    slot_info = f"Слот {slot_obj.slot_number} ({slot_obj.start_time.strftime('%H:%M')}-{slot_obj.end_time.strftime('%H:%M')})"
                else:
                    await callback.answer("❌ Слот не найден", show_alert=True)
                    return
            except (ValueError, IndexError):
                await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
                return
        
        # Добавляем голос
        success = await add_vote_manually(
            poll_db_id=poll_db_id,
            user_id=user_id,
            slot_id=slot_id,
            voted_option=voted_option,
        )
        
        if success:
            text = (
                f"✅ <b>Голос восстановлен!</b>\n\n"
                f"Пользователь: <b>{user.get_full_name()}</b>\n"
                f"Группа: <b>{clean_group_name_for_display(group.name) if group else 'Unknown'}</b>\n"
                f"Дата опроса: <b>{poll.poll_date}</b>\n"
                f"Выбор: <b>{slot_info}</b>\n\n"
                f"Голос успешно добавлен в базу данных."
            )
            
            # Обновляем список восстановимых голосов
            restorable_votes = await get_restorable_votes()
            
            if restorable_votes:
                keyboard = create_restore_votes_keyboard(restorable_votes, page=0)
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:verification_menu")],
                ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("✅ Голос восстановлен", show_alert=True)
            await state.clear()
        else:
            await callback.answer("❌ Ошибка при восстановлении голоса", show_alert=True)

