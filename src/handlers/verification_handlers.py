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
            try:
                from redis.asyncio import Redis
                import json
                
                # Пытаемся получить Redis
                redis: Redis = None
                
                # Пытаемся получить через state.storage (если это RedisStorage)
                if state:
                    try:
                        storage = state.storage
                        if hasattr(storage, 'redis'):
                            redis = storage.redis
                    except Exception:
                        pass
                
                # Если не получили через state, пытаемся через Bot.get_current()
                if not redis:
                    try:
                        from aiogram import Bot
                        bot_instance = Bot.get_current(no_error=True)
                        if bot_instance and hasattr(bot_instance, '_dispatcher'):
                            dispatcher = bot_instance._dispatcher
                            if dispatcher and "redis" in dispatcher:
                                redis = dispatcher["redis"]
                    except Exception as redis_get_error:
                        logger.debug("Could not get redis: %s", redis_get_error)
                
                if redis:
                    # Ищем все ключи welcome_message для этого пользователя
                    pattern = f"welcome_message:{user_id}:*"
                    deleted_count = 0
                    
                    async for key in redis.scan_iter(match=pattern):
                        try:
                            message_data_str = await redis.get(key)
                            if message_data_str:
                                message_data = json.loads(message_data_str)
                                msg_id = message_data.get("message_id")
                                chat_id = message_data.get("chat_id")
                                topic_id = message_data.get("topic_id")
                                
                                if msg_id and chat_id:
                                    try:
                                        await bot.delete_message(
                                            chat_id=chat_id,
                                            message_id=msg_id,
                                            message_thread_id=topic_id,
                                        )
                                        deleted_count += 1
                                        logger.info(
                                            "✅ Deleted welcome message %s from chat %s (topic_id: %s)",
                                            msg_id,
                                            chat_id,
                                            topic_id
                                        )
                                    except Exception as delete_error:
                                        logger.debug(
                                            "Could not delete welcome message %s from chat %s: %s",
                                            msg_id,
                                            chat_id,
                                            delete_error
                                        )
                            
                            # Удаляем ключ из Redis
                            await redis.delete(key)
                        except Exception as key_error:
                            logger.warning("Error processing welcome message key %s: %s", key, key_error)
                    
                    if deleted_count > 0:
                        logger.info(
                            "Deleted %d welcome messages for user %s",
                            deleted_count,
                            user_id
                        )
                else:
                    logger.warning("Redis not available, cannot delete welcome messages")
            except Exception as cleanup_error:
                logger.error(
                    "Error deleting welcome messages for user %s: %s",
                    user_id,
                    cleanup_error,
                    exc_info=True
                )
            
            logger.info("User %s verified successfully, restoring permissions", user_id)
            
            # Сначала восстанавливаем права в группах, где пользователь был ограничен (из Redis)
            restricted_chat_ids = set()
            try:
                from redis.asyncio import Redis
                import json
                
                # Пытаемся получить Redis
                redis: Redis = None
                
                # Пытаемся получить через state.storage (если это RedisStorage)
                if state:
                    try:
                        storage = state.storage
                        if hasattr(storage, 'redis'):
                            redis = storage.redis
                    except Exception:
                        pass
                
                # Если не получили через state, пытаемся через Bot.get_current()
                if not redis:
                    try:
                        from aiogram import Bot
                        bot_instance = Bot.get_current(no_error=True)
                        if bot_instance and hasattr(bot_instance, '_dispatcher'):
                            dispatcher = bot_instance._dispatcher
                            if dispatcher and "redis" in dispatcher:
                                redis = dispatcher["redis"]
                    except Exception as redis_get_error:
                        logger.debug("Could not get redis: %s", redis_get_error)
                
                if redis:
                    # Ищем все ключи welcome_message для этого пользователя
                    pattern = f"welcome_message:{user_id}:*"
                    async for key in redis.scan_iter(match=pattern):
                        try:
                            message_data_str = await redis.get(key)
                            if message_data_str:
                                message_data = json.loads(message_data_str)
                                chat_id = message_data.get("chat_id")
                                if chat_id:
                                    restricted_chat_ids.add(chat_id)
                        except Exception:
                            pass
                    
                    if restricted_chat_ids:
                        logger.info(
                            "Found %d groups where user %s was restricted (from Redis)",
                            len(restricted_chat_ids),
                            user_id
                        )
            except Exception as redis_error:
                logger.warning("Could not get restricted chat IDs from Redis: %s", redis_error)
            
            # Восстанавливаем права пользователя во всех группах
            try:
                from aiogram.types import ChatPermissions
                from src.repositories.group_repository import GroupRepository
                
                # Получаем сессию из user_service
                session = user_service.session
                group_repo = GroupRepository(session)
                
                # Получаем группы из БД для восстановления прав
                groups = await group_repo.get_active_groups()
                
                # Добавляем группы из Redis, если их нет в БД
                if restricted_chat_ids:
                    for restricted_chat_id in restricted_chat_ids:
                        # Проверяем, есть ли группа в БД
                        group = await group_repo.get_by_chat_id(restricted_chat_id)
                        if not group:
                            # Если группы нет в БД, создаем временный объект для восстановления прав
                            from types import SimpleNamespace
                            temp_group = SimpleNamespace(
                                telegram_chat_id=restricted_chat_id,
                                name=f"Chat {restricted_chat_id}",
                                is_active=True
                            )
                            groups.append(temp_group)
                            logger.debug(
                                "Added group from Redis (not in DB): chat_id=%s",
                                restricted_chat_id
                            )
                
                db_groups_count = len(await group_repo.get_active_groups())
                logger.info("Found %d groups to restore permissions (from DB: %d, from Redis: %d)", 
                           len(groups), 
                           db_groups_count,
                           len(restricted_chat_ids))
                
                # Восстанавливаем права во всех группах
                restored_count = 0
                failed_count = 0
                skipped_count = 0
                logger.info("Starting permission restoration loop for %d groups", len(groups))
                
                if len(groups) == 0:
                    logger.warning("No groups found to restore permissions for user %s", user_id)
                for group in groups:
                    try:
                        # Получаем chat_id и name группы
                        chat_id = getattr(group, 'telegram_chat_id', None) or getattr(group, 'chat_id', None) or group
                        group_name = getattr(group, 'name', f"Chat {chat_id}")
                        logger.info("Processing group: %s (chat_id: %s)", group_name, chat_id)
                        
                        # Проверяем, является ли пользователь участником группы
                        user_is_member = False
                        member_status = None
                        try:
                            chat_member = await bot.get_chat_member(chat_id, user_id)
                            member_status = chat_member.status
                            logger.info(
                                "User %s status in group %s (%s): %s",
                                user_id,
                                group_name,
                                chat_id,
                                member_status
                            )
                            # Проверяем все возможные статусы участника
                            # member, administrator, creator - пользователь в группе (нужно восстановить права на всякий случай)
                            # restricted - пользователь ограничен (ОБЯЗАТЕЛЬНО нужно восстановить права!)
                            # left, kicked - пользователь не в группе (пропускаем)
                            if member_status in ("left", "kicked"):
                                logger.info(
                                    "User %s is not a member of group %s (status: %s), skipping",
                                    user_id,
                                    group_name,
                                    member_status
                                )
                                skipped_count += 1
                                continue
                            
                            # Для всех остальных статусов (member, restricted, administrator, creator) восстанавливаем права
                            user_is_member = True
                            if member_status == "restricted":
                                logger.info(
                                    "User %s is RESTRICTED in group %s, will restore permissions",
                                    user_id,
                                    group_name
                                )
                            else:
                                logger.info(
                                    "User %s is member of group %s (status: %s), will restore permissions",
                                    user_id,
                                    group_name,
                                    member_status
                                )
                        except Exception as check_error:
                            error_msg = str(check_error).lower()
                            # Если ошибка "user not found" или "chat not found" - пропускаем
                            if "user not found" in error_msg or "chat not found" in error_msg:
                                logger.warning(
                                    "User %s or group %s not found, skipping: %s",
                                    user_id,
                                    group_name,
                                    check_error
                                )
                                skipped_count += 1
                                continue
                            # Для других ошибок пытаемся восстановить права в любом случае
                            logger.warning(
                                "Failed to check membership for user %s in group %s: %s. Will try to restore permissions anyway.",
                                user_id,
                                group_name,
                                check_error
                            )
                        
                        # Восстанавливаем права пользователя - снимаем ограничение полностью
                        logger.info(
                            "Attempting to restore permissions for user %s in group %s (%s)",
                            user_id,
                            group_name,
                            chat_id
                        )
                        try:
                            await bot.restrict_chat_member(
                                chat_id=chat_id,
                                user_id=user_id,
                                permissions=ChatPermissions(
                                    can_send_messages=True,
                                    can_send_media_messages=True,
                                    can_send_polls=True,
                                    can_send_other_messages=True,
                                    can_add_web_page_previews=True,
                                    can_change_info=True,
                                    can_invite_users=True,
                                    can_pin_messages=False,  # Оставляем False для безопасности
                                ),
                                until_date=None,  # Снимаем ограничение полностью (без временных ограничений)
                            )
                            logger.debug(
                                "Successfully called restrict_chat_member for user %s in group %s",
                                user_id,
                                group_name
                            )
                        except Exception as restrict_error:
                            logger.error(
                                "Error calling restrict_chat_member for user %s in group %s: %s",
                                user_id,
                                group_name,
                                restrict_error,
                                exc_info=True
                            )
                            failed_count += 1
                            continue
                        
                        # Проверяем, что права действительно восстановлены
                        try:
                            chat_member = await bot.get_chat_member(chat_id, user_id)
                            if hasattr(chat_member, 'permissions') and chat_member.permissions:
                                can_send = chat_member.permissions.can_send_messages
                                logger.info(
                                    "✅ Restored permissions for user %s in group %s (%s). can_send_messages=%s",
                                    user_id,
                                    group_name,
                                    chat_id,
                                    can_send
                                )
                                if not can_send:
                                    logger.warning(
                                        "⚠️ Permissions restored but can_send_messages is still False for user %s in group %s",
                                        user_id,
                                        group_name
                                    )
                            else:
                                logger.info(
                                    "✅ Restored permissions for user %s in group %s (%s)",
                                    user_id,
                                    group_name,
                                    chat_id
                                )
                        except Exception as check_error:
                            logger.warning(
                                "Could not verify restored permissions for user %s in group %s: %s",
                                user_id,
                                group_name,
                                check_error
                            )
                        
                        restored_count += 1
                    except Exception as restore_error:
                        failed_count += 1
                        logger.error(
                            "❌ Failed to restore permissions for user %s in group %s (%s): %s",
                            user_id,
                            group_name,
                            chat_id,
                            restore_error,
                            exc_info=True
                        )
                
                logger.info(
                    "Permission restoration completed for user %s: %d restored, %d failed, %d skipped",
                    user_id,
                    restored_count,
                    failed_count,
                    skipped_count
                )
                
                if restored_count == 0 and failed_count == 0:
                    logger.warning(
                        "⚠️ No permissions were restored for user %s. Possible reasons: "
                        "1. User is not a member of any active groups in DB, "
                        "2. All groups were skipped due to membership check failures, "
                        "3. No active groups found in DB",
                        user_id
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
