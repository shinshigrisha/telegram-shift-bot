import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def get_or_create_user(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> User:
        """Получить пользователя или создать нового. Обновляет данные, если пользователь уже существует."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            user = await self.user_repo.create(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
            )
            # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        else:
            # Для верифицированных пользователей не обновляем имена автоматически
            # (они были установлены вручную и не должны перезаписываться данными из Telegram)
            if not user.is_verified:
                # Обновляем данные пользователя, если они изменились (только для неверифицированных)
                updated = False
                if first_name is not None and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name is not None and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                if username is not None and user.username != username:
                    user.username = username
                    updated = True
            else:
                # Для верифицированных пользователей обновляем только username (если изменился)
                # Имена (first_name, last_name) не обновляем, так как они были установлены вручную
                if username is not None and user.username != username:
                    user.username = username
            # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        return user

    async def verify_user(self, user_id: int, first_name: str, last_name: str) -> Optional[User]:
        """Верифицировать пользователя."""
        user = await self.user_repo.verify_user(user_id, first_name, last_name)
        # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        return user

    async def is_verified(self, user_id: int) -> bool:
        """Проверить, верифицирован ли пользователь."""
        user = await self.user_repo.get_by_id(user_id)
        return user.is_verified if user else False

    async def delete_welcome_messages(
        self,
        bot,
        user_id: int,
        redis=None,
        state=None,
    ) -> int:
        """
        Удалить приветственные сообщения из групп для пользователя.
        
        Args:
            bot: Экземпляр Bot
            user_id: ID пользователя
            redis: Экземпляр Redis (опционально)
            state: FSMContext (опционально, для получения Redis)
        
        Returns:
            Количество удаленных сообщений
        """
        from redis.asyncio import Redis as RedisType
        import json
        
        try:
            # Пытаемся получить Redis
            current_redis: RedisType = redis
            
            if not current_redis and state:
                try:
                    storage = state.storage
                    if hasattr(storage, 'redis'):
                        current_redis = storage.redis
                except Exception:
                    pass
            
            if not current_redis:
                try:
                    from aiogram import Bot
                    bot_instance = Bot.get_current(no_error=True)
                    if bot_instance and hasattr(bot_instance, '_dispatcher'):
                        dispatcher = bot_instance._dispatcher
                        if dispatcher and "redis" in dispatcher:
                            current_redis = dispatcher["redis"]
                except Exception:
                    pass
            
            if not current_redis:
                logger.warning("Redis not available, cannot delete welcome messages")
                return 0
            
            # Ищем все ключи welcome_message для этого пользователя
            pattern = f"welcome_message:{user_id}:*"
            deleted_count = 0
            
            async for key in current_redis.scan_iter(match=pattern):
                try:
                    message_data_str = await current_redis.get(key)
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
                    await current_redis.delete(key)
                except Exception as key_error:
                    logger.warning("Error processing welcome message key %s: %s", key, key_error)
            
            if deleted_count > 0:
                logger.info(
                    "Deleted %d welcome messages for user %s",
                    deleted_count,
                    user_id
                )
            
            return deleted_count
        except Exception as cleanup_error:
            logger.error(
                "Error deleting welcome messages for user %s: %s",
                user_id,
                cleanup_error,
                exc_info=True
            )
            return 0

    async def restore_user_permissions(
        self,
        bot,
        user_id: int,
        redis=None,
        state=None,
    ) -> tuple[int, int, int]:
        """
        Восстановить права пользователя во всех группах после верификации.
        
        Args:
            bot: Экземпляр Bot
            user_id: ID пользователя
            redis: Экземпляр Redis (опционально)
            state: FSMContext (опционально, для получения Redis)
        
        Returns:
            Кортеж (restored_count, failed_count, skipped_count)
        """
        import asyncio
        from aiogram.types import ChatPermissions
        from src.repositories.group_repository import GroupRepository
        from redis.asyncio import Redis as RedisType
        import json
        
        # Сначала восстанавливаем права в группах, где пользователь был ограничен (из Redis)
        restricted_chat_ids = set()
        try:
            # Пытаемся получить Redis
            current_redis: RedisType = redis
            
            if not current_redis and state:
                try:
                    storage = state.storage
                    if hasattr(storage, 'redis'):
                        current_redis = storage.redis
                except Exception:
                    pass
            
            if not current_redis:
                try:
                    from aiogram import Bot
                    bot_instance = Bot.get_current(no_error=True)
                    if bot_instance and hasattr(bot_instance, '_dispatcher'):
                        dispatcher = bot_instance._dispatcher
                        if dispatcher and "redis" in dispatcher:
                            current_redis = dispatcher["redis"]
                except Exception:
                    pass
            
            if current_redis:
                # Ищем все ключи welcome_message для этого пользователя
                pattern = f"welcome_message:{user_id}:*"
                async for key in current_redis.scan_iter(match=pattern):
                    try:
                        message_data_str = await current_redis.get(key)
                        if message_data_str:
                            message_data = json.loads(message_data_str)
                            chat_id = message_data.get("chat_id")
                            if chat_id:
                                restricted_chat_ids.add(chat_id)
                    except Exception:
                        pass
                
                # Также ищем ключи restricted_user для этого пользователя
                restricted_pattern = f"restricted_user:{user_id}:*"
                async for key in current_redis.scan_iter(match=restricted_pattern):
                    try:
                        parts = key.split(":")
                        if len(parts) >= 3:
                            chat_id = int(parts[2])
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
            group_repo = GroupRepository(self.session)
            
            # Получаем группы из БД для восстановления прав
            groups = await group_repo.get_active_groups()
            
            # Добавляем группы из Redis, если их нет в БД
            if restricted_chat_ids:
                for restricted_chat_id in restricted_chat_ids:
                    group = await group_repo.get_by_chat_id(restricted_chat_id)
                    if not group:
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
            
            logger.info("Found %d groups to restore permissions (from DB: %d, from Redis: %d)", 
                       len(groups), 
                       len(await group_repo.get_active_groups()),
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
                        
                        # Если группа из Redis (где пользователь был ограничен), восстанавливаем права в любом случае
                        is_from_redis = hasattr(group, 'telegram_chat_id') and group.telegram_chat_id in restricted_chat_ids
                        
                        if member_status in ("left", "kicked"):
                            if is_from_redis:
                                logger.warning(
                                    "User %s status is %s in group %s from Redis, but will try to restore permissions anyway",
                                    user_id,
                                    member_status,
                                    group_name
                                )
                            else:
                                logger.info(
                                    "User %s is not a member of group %s (status: %s), skipping",
                                    user_id,
                                    group_name,
                                    member_status
                                )
                                skipped_count += 1
                                continue
                        
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
                        is_from_redis = hasattr(group, 'telegram_chat_id') and group.telegram_chat_id in restricted_chat_ids
                        
                        if "user not found" in error_msg or "chat not found" in error_msg:
                            if is_from_redis:
                                logger.warning(
                                    "User %s or group %s not found, but group is from Redis. Will try to restore permissions anyway: %s",
                                    user_id,
                                    group_name,
                                    check_error
                                )
                            else:
                                logger.warning(
                                    "User %s or group %s not found, skipping: %s",
                                    user_id,
                                    group_name,
                                    check_error
                                )
                                skipped_count += 1
                                continue
                        
                        logger.warning(
                            "Failed to check membership for user %s in group %s: %s. Will try to restore permissions anyway.",
                            user_id,
                            group_name,
                            check_error
                        )
                    
                    # Восстанавливаем права пользователя
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
                                can_pin_messages=False,
                            ),
                            until_date=None,
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
                    await asyncio.sleep(0.5)  # Задержка для обновления статуса в Telegram
                    
                    try:
                        chat_member = await bot.get_chat_member(chat_id, user_id)
                        logger.info(
                            "Checking restored permissions - user %s status in group %s: %s",
                            user_id,
                            group_name,
                            chat_member.status
                        )
                        
                        if chat_member.status in ("member", "restricted", "administrator", "creator"):
                            if hasattr(chat_member, 'permissions') and chat_member.permissions:
                                can_send = chat_member.permissions.can_send_messages
                                logger.info(
                                    "✅ Restored permissions for user %s in group %s (%s). Status: %s, can_send_messages=%s",
                                    user_id,
                                    group_name,
                                    chat_id,
                                    chat_member.status,
                                    can_send
                                )
                                if not can_send:
                                    logger.error(
                                        "❌ CRITICAL: Permissions restored but can_send_messages is still False for user %s in group %s. Status: %s",
                                        user_id,
                                        group_name,
                                        chat_member.status
                                    )
                            elif chat_member.status in ("member", "administrator", "creator"):
                                logger.info(
                                    "✅ Restored permissions for user %s in group %s (%s). Status: %s (full permissions)",
                                    user_id,
                                    group_name,
                                    chat_id,
                                    chat_member.status
                                )
                    except Exception as check_error:
                        logger.warning(
                            "Could not verify restored permissions for user %s in group %s: %s",
                            user_id,
                            group_name,
                            check_error
                        )
                    
                    restored_count += 1
                    
                    # Удаляем ключ restricted_user из Redis после успешного восстановления прав
                    if current_redis and chat_id in restricted_chat_ids:
                        try:
                            restricted_key = f"restricted_user:{user_id}:{chat_id}"
                            await current_redis.delete(restricted_key)
                            logger.debug("Deleted restricted_user key from Redis: %s", restricted_key)
                        except Exception:
                            pass
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
            
            return (restored_count, failed_count, skipped_count)
        except Exception as e:
            logger.error(
                "Error restoring permissions for user %s: %s",
                user_id,
                e,
                exc_info=True
            )
            return (0, 0, 0)

