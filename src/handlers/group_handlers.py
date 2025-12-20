import logging
from typing import Optional

from aiogram import Router, Bot
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import ChatMemberUpdated, Message
from aiogram.fsm.context import FSMContext

from config.settings import settings
from src.services.user_service import UserService
from src.services.group_service import GroupService
from src.states.verification_states import VerificationStates
from src.utils.env_updater import update_env_variable

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
        
        # Пропускаем, если это сам бот
        if user_id == bot.id:
            return
        
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
        
        # Для обычных участников - отправляем приветствие с кнопкой старт
        if user_service and state:
            is_verified = await user_service.is_verified(user_id)
            
            if not is_verified:
                # Отправляем приветственное сообщение с инструкцией использовать /start
                try:
                    await bot.send_message(
                        chat_id=event.chat.id,
                        text=(
                            f"👋 Привет, {event.new_chat_member.user.full_name}!\n\n"
                            "Для участия в опросах необходимо пройти верификацию.\n\n"
                            "Пожалуйста, используйте команду <b>/start</b> в личных сообщениях с ботом."
                        ),
                    )
                except Exception as e:
                    logger.error("Failed to send welcome message to new member: %s", e)
                    
    except Exception as e:
        logger.error("Error handling new member: %s", e, exc_info=True)

