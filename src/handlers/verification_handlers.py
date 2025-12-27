import logging
import re
import asyncio

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from config.settings import settings
from src.states.verification_states import VerificationStates
from src.services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router()

# Проверяем наличие состояний верификации
HAS_VERIFICATION_STATES = hasattr(VerificationStates, 'waiting_for_full_name')


async def delete_message_safe(bot: Bot, chat_id: int, message_id: int) -> None:
    """Безопасно удалить сообщение, игнорируя ошибки."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        # Сообщение уже удалено или недоступно - это нормально
        pass
    except Exception:
        # Сообщение уже удалено или недоступно - это нормально
        pass


async def delete_message_after_delay(bot: Bot, chat_id: int, message_id: int, delay: int = 5) -> None:
    """Удалить сообщение через указанную задержку."""
    await asyncio.sleep(delay)
    await delete_message_safe(bot, chat_id, message_id)


if HAS_VERIFICATION_STATES:
    @router.message(StateFilter(VerificationStates.waiting_for_full_name))
    async def process_full_name(
        message: Message,
        bot: Bot,
        state: FSMContext,
        user_service: UserService,
    ) -> None:
        """Обработка ввода Фамилии и Имени в одном сообщении."""
        user_id = message.from_user.id
        
        # Получаем ID предыдущего сообщения бота для удаления
        data = await state.get_data()
        previous_bot_message_id = data.get("verification_bot_message_id")
        
        # Проверяем, что сообщение содержит текст
        if not message.text:
            # Удаляем предыдущее сообщение бота, если оно есть
            if previous_bot_message_id:
                await delete_message_safe(bot, user_id, previous_bot_message_id)
            
            # Отправляем сообщение в приватный чат
            try:
                error_message = await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ Пожалуйста, отправьте текстовое сообщение с вашими <b>Фамилией и Именем</b>\n\n"
                        "Формат: <b>Фамилия Имя</b>\n"
                        "Пример: <code>Иванов Иван</code>\n\n"
                        "Для отмены введите: <code>отмена</code>"
                    ),
                )
                # Сохраняем ID сообщения для удаления
                await state.update_data(verification_bot_message_id=error_message.message_id)
            except Exception as e:
                logger.error("Error sending verification message to user %s: %s", user_id, e)
            # Удаляем сообщение пользователя
            await delete_message_safe(bot, message.chat.id, message.message_id)
            return
        
        # Получаем ID предыдущего сообщения бота для удаления
        data = await state.get_data()
        previous_bot_message_id = data.get("verification_bot_message_id")
        
        # Проверяем на отмену
        if message.text.strip().lower() == "отмена":
            # Удаляем предыдущее сообщение бота, если оно есть
            if previous_bot_message_id:
                await delete_message_safe(bot, user_id, previous_bot_message_id)
            
            await state.clear()
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="❌ Верификация отменена",
                )
            except Exception as e:
                logger.error("Error sending cancellation message to user %s: %s", user_id, e)
            # Удаляем сообщение пользователя
            await delete_message_safe(bot, message.chat.id, message.message_id)
            return
        
        full_name = message.text.strip()
        
        # Получаем ID предыдущего сообщения бота для удаления
        data = await state.get_data()
        previous_bot_message_id = data.get("verification_bot_message_id")
        
        # Разделяем на фамилию и имя
        name_parts = full_name.split(maxsplit=1)
        if len(name_parts) < 2:
            # Удаляем предыдущее сообщение бота, если оно есть
            if previous_bot_message_id:
                await delete_message_safe(bot, user_id, previous_bot_message_id)
            
            # Отправляем сообщение об ошибке в приватный чат
            try:
                error_message = await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ Неверный формат.\n\n"
                        "Пожалуйста, введите <b>Фамилию и Имя</b> через пробел:\n"
                        "Формат: <b>Фамилия Имя</b>\n"
                        "Пример: <code>Иванов Иван</code>"
                    ),
                )
                # Сохраняем ID сообщения для удаления
                await state.update_data(verification_bot_message_id=error_message.message_id)
            except Exception as e:
                logger.error("Error sending error message to user %s: %s", user_id, e)
            # Удаляем сообщение пользователя
            await delete_message_safe(bot, message.chat.id, message.message_id)
            return
        
        last_name = name_parts[0].strip()
        first_name = name_parts[1].strip()
        
        # Валидация фамилии и имени (только буквы, пробелы, дефисы)
        name_pattern = r'^[А-Яа-яA-Za-z\s\-]{2,50}$'
        if not re.match(name_pattern, last_name) or not re.match(name_pattern, first_name):
            # Получаем ID предыдущего сообщения бота для удаления
            data = await state.get_data()
            previous_bot_message_id = data.get("verification_bot_message_id")
            
            # Удаляем предыдущее сообщение бота, если оно есть
            if previous_bot_message_id:
                await delete_message_safe(bot, user_id, previous_bot_message_id)
            
            # Отправляем сообщение об ошибке в приватный чат
            try:
                error_message = await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ Неверный формат.\n\n"
                        "Фамилия и Имя должны содержать только буквы (2-50 символов).\n"
                        "Пожалуйста, введите <b>Фамилию и Имя</b> через пробел:\n"
                        "Пример: <code>Иванов Иван</code>"
                    ),
                )
                # Сохраняем ID сообщения для удаления
                await state.update_data(verification_bot_message_id=error_message.message_id)
            except Exception as e:
                logger.error("Error sending validation error message to user %s: %s", user_id, e)
            # Удаляем сообщение пользователя
            await delete_message_safe(bot, message.chat.id, message.message_id)
            return
        
        # Получаем ID предыдущих сообщений бота для удаления
        data = await state.get_data()
        previous_bot_message_id = data.get("verification_bot_message_id")
        
        # Удаляем сообщение пользователя
        await delete_message_safe(bot, message.chat.id, message.message_id)
        
        # Удаляем предыдущее сообщение бота, если оно есть
        if previous_bot_message_id:
            await delete_message_safe(bot, user_id, previous_bot_message_id)
        
        # Верифицируем пользователя
        logger.info(
            "Verifying user %s with name: %s %s",
            user_id,
            last_name,
            first_name
        )
        
        user = await user_service.verify_user(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
        )
        
        if user:
            logger.info(
                "User %s verified successfully. is_verified=%s",
                user_id,
                user.is_verified
            )
            
            # Удаляем приветственные сообщения с кнопкой "Старт" из всех групп
            deleted_count = await user_service.delete_welcome_messages(
                bot=bot,
                user_id=user_id,
                state=state,
            )
            
            logger.info("User %s verified successfully, restoring permissions", user_id)
            
            # Восстанавливаем права пользователя во всех группах
            try:
                restored_count, failed_count, skipped_count = await user_service.restore_user_permissions(
                    bot=bot,
                    user_id=user_id,
                    state=state,
                )
                logger.info(
                    "Permission restoration completed for user %s: %d restored, %d failed, %d skipped",
                    user_id,
                    restored_count,
                    failed_count,
                    skipped_count
                )
            except Exception as e:
                logger.error(
                    "Error restoring permissions for user %s: %s",
                    user_id,
                    e,
                    exc_info=True
                )
            
            # Отправляем сообщение о завершении верификации в приватный чат
            try:
                success_message = await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Верификация завершена!</b>\n\n"
                        f"Ваши данные:\n"
                        f"Фамилия: <b>{last_name}</b>\n"
                        f"Имя: <b>{first_name}</b>\n\n"
                        f"Теперь вы можете участвовать в опросах и писать в группах."
                    ),
                )
                # Удаляем финальное сообщение через 5 секунд (чтобы пользователь успел прочитать)
                asyncio.create_task(delete_message_after_delay(bot, user_id, success_message.message_id, delay=5))
            except Exception as e:
                logger.error("Error sending success message to user %s: %s", user_id, e)
            await state.clear()
        else:
            # Отправляем сообщение об ошибке в приватный чат
            try:
                error_message = await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ Ошибка при сохранении данных.\n"
                        "Пожалуйста, попробуйте еще раз."
                    ),
                )
                # Сохраняем ID сообщения для удаления при следующем ответе
                await state.update_data(verification_bot_message_id=error_message.message_id)
            except Exception as e:
                logger.error("Error sending error message to user %s: %s", user_id, e)
else:
    # Заглушки для случаев, когда верификация отключена
    logger.info("Verification handlers disabled - states not available")
