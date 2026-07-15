"""
Обработчики для раздела "Рассылка" админ-панели.
"""
import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.states.admin_panel_states import AdminPanelStates
from src.services.group_service import GroupService
from src.utils.auth import require_admin_callback
from src.utils.admin_keyboards import get_back_keyboard
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:broadcast:create")
@require_admin_callback
async def callback_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Старт рассылки без тем."""
    await state.set_state(AdminPanelStates.waiting_for_broadcast_message)
    
    text = (
        "📢 <b>Рассылка по активным группам</b>\n\n"
        "Введите текст сообщения или отправьте фото с подписью.\n\n"
        "Можно использовать HTML-разметку для форматирования.\n\n"
        "Для отмены отправьте: <b>отмена</b>"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_back_keyboard("admin:broadcast_menu"))
    await safe_answer_callback(callback)


@router.message(AdminPanelStates.waiting_for_broadcast_message)
async def process_broadcast_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    group_service: GroupService,
) -> None:
    """Обработка ввода сообщения для рассылки."""
    # Проверка на отмену
    if message.text and message.text.lower() in ["отмена", "cancel"]:
        await state.clear()
        await message.answer("❌ Рассылка отменена", parse_mode="HTML")
        return
    
    # Получаем все активные группы
    groups = await group_service.get_all_groups(active_only=True)
    
    if not groups:
        await message.answer("❌ Нет активных групп для рассылки", parse_mode="HTML")
        await state.clear()
        return
    
    # Подготавливаем сообщение
    await message.answer("⏳ Отправка сообщений...\n\nПожалуйста, подождите.", parse_mode="HTML")
    
    sent_count = 0
    skipped_count = 0
    errors = []
    
    # Определяем, что отправляем: текст или фото
    has_photo = message.photo is not None and len(message.photo) > 0
    text_content = message.caption if has_photo else message.text
    
    if not text_content and not has_photo:
        await message.answer("❌ Сообщение пустое. Отправьте текст или фото с подписью.", parse_mode="HTML")
        await state.clear()
        return
    
    # Отправляем в каждую группу
    for group in groups:
        try:
            chat_id = group.get("telegram_chat_id")
            
            # Отправляем сообщение
            if has_photo:
                # Отправляем фото с подписью
                photo = message.photo[-1]  # Берем фото наибольшего размера
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo.file_id,
                    caption=text_content,
                    parse_mode="HTML",
                )
            else:
                # Отправляем текстовое сообщение
                await bot.send_message(
                    chat_id=chat_id,
                    text=text_content,
                    parse_mode="HTML",
                )
            
            sent_count += 1
            logger.info("Сообщение отправлено в группу %s", group.get("name"))
            
        except TelegramAPIError as e:
            error_msg = f"Группа {group.get('name')}: {str(e)}"
            errors.append(error_msg)
            logger.error("Ошибка при отправке в группу %s: %s", group.get("name"), e)
        except Exception as e:
            error_msg = f"Группа {group.get('name')}: {str(e)}"
            errors.append(error_msg)
            logger.error("Неожиданная ошибка при отправке в группу %s: %s", group.get("name"), e, exc_info=True)
    
    # Формируем отчет
    report_text = (
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{sent_count}</b>\n"
        f"⏭️ Пропущено: <b>{skipped_count}</b>\n"
    )
    
    if errors:
        error_text = "\n".join(f"❌ {e}" for e in errors[:10])
        if len(errors) > 10:
            error_text += f"\n... и еще {len(errors) - 10} ошибок"
        report_text += f"\n❌ <b>Ошибки:</b>\n{error_text}"
    
    await message.answer(report_text, reply_markup=get_back_keyboard("admin:broadcast_menu"), parse_mode="HTML")
    await state.clear()
