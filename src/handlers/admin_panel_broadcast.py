"""Рассылка сообщений через админ-панель."""
import logging

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.repositories.group_repository import GroupRepository
from src.states.admin_panel_states import AdminPanelStates
from src.utils.auth import require_admin_callback
from src.utils.telegram_helpers import safe_edit_message, safe_answer_callback

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data == "admin:broadcast")
@require_admin_callback
async def callback_broadcast_menu(
    callback: CallbackQuery,
) -> None:
    """Меню рассылки по группам."""
    text = (
        "📢 <b>Рассылка по группам</b>\n\n"
        "Выберите тему, в которую отправить сообщение:\n\n"
        "• <b>Отметки на слот</b> - тема, где создаются опросы\n"
        "• <b>Приход/уход</b> - тема для других целей\n"
        "• <b>Общий чат</b> - тема для напоминаний\n"
        "• <b>Важная информация</b> - тема для важных сообщений"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Отметки на слот", callback_data="admin:broadcast:poll")],
        [InlineKeyboardButton(text="📥 Приход/уход", callback_data="admin:broadcast:arrival")],
        [InlineKeyboardButton(text="💬 Общий чат", callback_data="admin:broadcast:general")],
        [InlineKeyboardButton(text="📢 Важная информация", callback_data="admin:broadcast:important")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_main")],
    ])
    
    await safe_edit_message(callback.message, text, reply_markup=keyboard)
    await safe_answer_callback(callback)


@router.callback_query(lambda c: c.data.startswith("admin:broadcast:"))
@require_admin_callback
async def callback_broadcast_topic(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Обработка выбора темы для рассылки."""
    topic_type = callback.data.split(":")[-1]
    
    topic_names = {
        "poll": "отметки на слот",
        "arrival": "приход/уход",
        "general": "общий чат",
        "important": "важная информация",
    }
    
    if topic_type not in topic_names:
        await callback.answer("❌ Неизвестный тип темы")
        return
    
    topic_name = topic_names[topic_type]
    
    await state.update_data(broadcast_topic_type=topic_type)
    
    text = (
        f"📢 <b>Рассылка в тему: {topic_name}</b>\n\n"
        "Введите сообщение для рассылки во все группы:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:broadcast")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(AdminPanelStates.waiting_for_broadcast_message)
    await callback.answer()


@router.message(StateFilter(AdminPanelStates.waiting_for_broadcast_message))
async def process_broadcast_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    group_repo: GroupRepository,
) -> None:
    """Обработка ввода сообщения для рассылки (поддерживает текст, фото, файлы)."""
    # Проверяем на отмену (если это текстовое сообщение)
    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer("❌ Отменено")
        return
    
    # Проверяем, есть ли контент для отправки
    has_text = bool(message.text or message.caption)
    has_photo = bool(message.photo)
    has_document = bool(message.document)
    has_video = bool(message.video)
    has_audio = bool(message.audio)
    has_voice = bool(message.voice)
    has_video_note = bool(message.video_note)
    has_sticker = bool(message.sticker)
    
    if not any([has_text, has_photo, has_document, has_video, has_audio, has_voice, has_video_note, has_sticker]):
        await message.answer("❌ Сообщение не может быть пустым. Отправьте текст, фото, файл или другое медиа:")
        return
    
    data = await state.get_data()
    topic_type = data.get("broadcast_topic_type")
    
    if not topic_type:
        await message.answer("❌ Ошибка: тип темы не найден")
        await state.clear()
        return
    
    # Определяем поле для topic_id
    topic_fields = {
        "poll": "telegram_topic_id",
        "arrival": "arrival_departure_topic_id",
        "general": "general_chat_topic_id",
        "important": "important_info_topic_id",
    }
    field_name = topic_fields.get(topic_type)
    
    if not field_name:
        await message.answer("❌ Ошибка: неизвестный тип темы")
        await state.clear()
        return
    
    # Получаем все активные группы
    groups = await group_repo.get_active_groups()
    
    if not groups:
        await message.answer("❌ Нет активных групп для рассылки")
        await state.clear()
        return
    
    # Отправляем сообщение во все группы
    sent_count = 0
    errors = []
    
    # Определяем текст/подпись
    broadcast_text = message.text or message.caption
    
    for group in groups:
        try:
            topic_id = getattr(group, field_name, None)
            
            if not topic_id:
                errors.append(f"{group.name}: тема не настроена")
                continue
            
            # Отправляем в зависимости от типа медиа
            if has_photo:
                # Отправляем фото с подписью
                await bot.send_photo(
                    chat_id=group.telegram_chat_id,
                    photo=message.photo[-1].file_id,  # Берем фото наибольшего размера
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_document:
                # Отправляем документ с подписью
                await bot.send_document(
                    chat_id=group.telegram_chat_id,
                    document=message.document.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_video:
                # Отправляем видео с подписью
                await bot.send_video(
                    chat_id=group.telegram_chat_id,
                    video=message.video.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_audio:
                # Отправляем аудио с подписью
                await bot.send_audio(
                    chat_id=group.telegram_chat_id,
                    audio=message.audio.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_voice:
                # Отправляем голосовое сообщение с подписью
                await bot.send_voice(
                    chat_id=group.telegram_chat_id,
                    voice=message.voice.file_id,
                    caption=broadcast_text,
                    message_thread_id=topic_id,
                )
            elif has_video_note:
                # Отправляем видеосообщение (кружок)
                await bot.send_video_note(
                    chat_id=group.telegram_chat_id,
                    video_note=message.video_note.file_id,
                    message_thread_id=topic_id,
                )
                # Если есть подпись, отправляем отдельным сообщением
                if broadcast_text:
                    await bot.send_message(
                        chat_id=group.telegram_chat_id,
                        text=broadcast_text,
                        message_thread_id=topic_id,
                    )
            elif has_sticker:
                # Отправляем стикер
                await bot.send_sticker(
                    chat_id=group.telegram_chat_id,
                    sticker=message.sticker.file_id,
                    message_thread_id=topic_id,
                )
                # Если есть подпись, отправляем отдельным сообщением
                if broadcast_text:
                    await bot.send_message(
                        chat_id=group.telegram_chat_id,
                        text=broadcast_text,
                        message_thread_id=topic_id,
                    )
            elif has_text:
                # Отправляем текстовое сообщение
                await bot.send_message(
                    chat_id=group.telegram_chat_id,
                    text=broadcast_text,
                    message_thread_id=topic_id,
                )
            else:
                errors.append(f"{group.name}: неизвестный тип медиа")
                continue
                
            sent_count += 1
        except Exception as e:
            errors.append(f"{group.name}: {str(e)}")
            logger.error("Error sending broadcast to group %s: %s", group.name, e)
    
    # Формируем ответ
    result_text = (
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: {sent_count} из {len(groups)}\n"
    )
    
    if errors:
        result_text += f"\n❌ <b>Ошибки ({len(errors)}):</b>\n"
        result_text += "\n".join(f"• {e}" for e in errors[:5])
        if len(errors) > 5:
            result_text += f"\n... и ещё {len(errors) - 5}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в админ-панель", callback_data="admin:back_to_main")],
    ])
    
    await message.answer(result_text, reply_markup=keyboard)
    await state.clear()

