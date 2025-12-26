import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import ChatMemberUpdated, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config.settings import settings
from src.services.user_service import UserService
from src.services.group_service import GroupService
from src.states.verification_states import VerificationStates
from src.utils.env_updater import update_env_variable
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def handle_new_member(
    event: ChatMemberUpdated,
    bot: Bot,
    user_service: Optional[UserService] = None,
    state: Optional[FSMContext] = None,
) -> None:
    """Обработка добавления нового участника в группу."""
    try:
        user_id = event.new_chat_member.user.id
        user = event.new_chat_member.user
        
        # Пропускаем, если это сам бот
        if user_id == bot.id:
            return
        
        # Автоматически сохраняем/обновляем данные пользователя при входе в группу
        if user_service:
            try:
                await user_service.get_or_create_user(
                    user_id=user_id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                )
                logger.info(
                    "User data saved/updated for new member %s (%s %s) in group %s",
                    user_id,
                    user.first_name,
                    user.last_name,
                    event.chat.id,
                )
            except Exception as e:
                logger.error(
                    "Error saving user data for new member %s: %s",
                    user_id,
                    e,
                    exc_info=True,
                )
        
        # Проверяем, является ли новый участник админом группы
        from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
        if isinstance(event.new_chat_member, (ChatMemberAdministrator, ChatMemberOwner)):
            # Автоматически добавляем админа в ADMIN_IDS
            if user_id not in settings.ADMIN_IDS:
                current_admins = list(settings.ADMIN_IDS)
                current_admins.append(user_id)
                # Обновляем .env файл
                admin_ids_str = "[" + ",".join(str(admin_id) for admin_id in current_admins) + "]"
                if update_env_variable("ADMIN_IDS", admin_ids_str):
                    # Перезагружаем настройки
                    import importlib
                    import config.settings
                    importlib.reload(config.settings)
                    logger.info("Auto-added admin %s to ADMIN_IDS", user_id)
        
        # Для обычных участников - ограничиваем права и отправляем приветствие с кнопкой старт (только если верификация включена)
        if settings.ENABLE_VERIFICATION and user_service:
            is_verified = await user_service.is_verified(user_id)
            logger.info(
                "New member %s (%s) in chat %s, is_verified: %s",
                user_id,
                user.full_name,
                event.chat.id,
                is_verified
            )
            
            if not is_verified:
                # Ограничиваем права пользователя на отправку сообщений
                try:
                    from aiogram.types import ChatPermissions
                    await bot.restrict_chat_member(
                        chat_id=event.chat.id,
                        user_id=user_id,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_media_messages=False,
                            can_send_polls=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False,
                            can_change_info=False,
                            can_invite_users=False,
                            can_pin_messages=False,
                        ),
                    )
                    logger.info(
                        "✅ Restricted unverified user %s in chat %s",
                        user_id,
                        event.chat.id
                    )
                except Exception as restrict_error:
                    logger.error(
                        "❌ Failed to restrict unverified user %s in chat %s: %s",
                        user_id,
                        event.chat.id,
                        restrict_error,
                        exc_info=True
                    )
                # Получаем username бота для создания ссылки
                try:
                    bot_info = await bot.get_me()
                    bot_username = bot_info.username
                except Exception:
                    bot_username = None
                
                # Создаем inline-кнопку "Старт"
                if bot_username:
                    start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🚀 Старт",
                                url=f"https://t.me/{bot_username}?start=verify"
                            )
                        ]
                    ])
                else:
                    # Если username недоступен, используем команду
                    start_keyboard = None
                
                # Отправляем приветственное сообщение с кнопкой
                try:
                    welcome_text = (
                        f"👋 Привет, {user.full_name}!\n\n"
                        "Для участия в опросах необходимо пройти верификацию.\n\n"
                    )
                    if start_keyboard:
                        welcome_text += "Нажмите кнопку <b>Старт</b> ниже, чтобы начать:"
                    else:
                        welcome_text += "Используйте команду <b>/start</b> в личных сообщениях с ботом."
                    
                    # Определяем, куда отправлять сообщение
                    # Для форум-групп пытаемся найти тему "общий чат" или основную тему
                    topic_id = None
                    chat_id = event.chat.id
                    
                    # Проверяем, является ли группа форум-группой
                    try:
                        chat_info = await bot.get_chat(chat_id)
                        is_forum = getattr(chat_info, 'is_forum', False)
                        
                        if is_forum:
                            # Ищем группу в БД для получения topic_id
                            if user_service:
                                from src.repositories.group_repository import GroupRepository
                                group_repo = GroupRepository(user_service.session)
                                group = await group_repo.get_by_chat_id(chat_id)
                                
                                if group:
                                    # Приоритет: общий чат > основная тема
                                    topic_id = group.general_chat_topic_id or group.telegram_topic_id
                                    logger.info(
                                        "Found group %s, using topic_id: %s (general_chat: %s, main: %s)",
                                        group.name,
                                        topic_id,
                                        group.general_chat_topic_id,
                                        group.telegram_topic_id
                                    )
                    except Exception as e:
                        logger.warning("Failed to get chat info or group data: %s", e)
                    
                    # Отправляем сообщение
                    sent_message = await bot.send_message(
                        chat_id=chat_id,
                        message_thread_id=topic_id,  # None для обычных групп, topic_id для форум-групп
                        text=welcome_text,
                        reply_markup=start_keyboard,
                    )
                    logger.info(
                        "✅ Sent welcome message with Start button to user %s in chat %s (topic_id: %s, message_id: %s)",
                        user_id,
                        chat_id,
                        topic_id,
                        sent_message.message_id
                    )
                    
                    # Сохраняем ID приветственного сообщения в Redis для последующего удаления после верификации
                    try:
                        from redis.asyncio import Redis
                        redis: Redis = None
                        
                        # Пытаемся получить redis через state.storage (если это RedisStorage)
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
                            except Exception:
                                pass
                        
                        if redis:
                            # Сохраняем в Redis с ключом welcome_message:{user_id}:{chat_id}
                            redis_key = f"welcome_message:{user_id}:{chat_id}"
                            if topic_id:
                                redis_key += f":{topic_id}"
                            # Сохраняем как JSON: {"message_id": ..., "chat_id": ..., "topic_id": ...}
                            import json
                            message_data = {
                                "message_id": sent_message.message_id,
                                "chat_id": chat_id,
                                "topic_id": topic_id,
                            }
                            await redis.set(redis_key, json.dumps(message_data), ex=86400 * 7)  # Храним 7 дней
                            logger.debug("Saved welcome message ID to Redis: %s", redis_key)
                    except Exception as redis_error:
                        logger.warning("Failed to save welcome message ID to Redis: %s", redis_error)
                except Exception as e:
                    logger.error("Failed to send welcome message to new member: %s", e, exc_info=True)
                
                # Отправляем уведомление админам о новом пользователе (только если включены уведомления)
                if settings.ENABLE_ADMIN_NOTIFICATIONS:
                    try:
                        notification_service = NotificationService(bot)
                        username_text = f"@{user.username}" if user.username else "не указан"
                        user_info = (
                            f"👤 <b>Новый участник</b>\n\n"
                            f"Имя: {user.full_name}\n"
                            f"Username: {username_text}\n"
                            f"ID: <code>{user_id}</code>\n"
                            f"Группа: <code>{event.chat.id}</code>\n\n"
                            f"Статус верификации: ❌ Не верифицирован"
                        )
                        await notification_service.notify_admins(user_info)
                    except Exception as e:
                        logger.error("Failed to send admin notification about new member: %s", e)
                    
    except Exception as e:
        logger.error("Error handling new member: %s", e, exc_info=True)

