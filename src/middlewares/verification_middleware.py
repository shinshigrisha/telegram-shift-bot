import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType

from config.settings import settings
from src.services.user_service import UserService
from src.states.verification_states import VerificationStates

logger = logging.getLogger(__name__)


class VerificationMiddleware(BaseMiddleware):
    """Middleware для проверки верификации пользователей."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Если верификация отключена, пропускаем все проверки
        if not settings.ENABLE_VERIFICATION:
            return await handler(event, data)
        
        # Проверяем только сообщения от пользователей
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # Пропускаем команды без проверки (для верификации и админ-панели)
        if event.text and event.text.startswith("/"):
            command = event.text.split()[0] if event.text else ""
            # Пропускаем команды /start, /admin, /help без проверки верификации
            if command in ["/start", "/admin", "/help"]:
                return await handler(event, data)
        
        # Получаем user_service из data (должен быть добавлен DatabaseMiddleware)
        user_service: UserService | None = data.get("user_service")
        if not user_service:
            return await handler(event, data)

        user_id = event.from_user.id

        # Проверяем верификацию
        is_verified = await user_service.is_verified(user_id)
        
        # Логируем для отладки (только для групп)
        if event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            logger.debug(
                "Verification check for user %s in chat %s: is_verified=%s",
                user_id,
                event.chat.id,
                is_verified
            )

        # Если пользователь не верифицирован
        if not is_verified:
            # Создаем или получаем пользователя
            await user_service.get_or_create_user(
                user_id=user_id,
                first_name=event.from_user.first_name,
                last_name=event.from_user.last_name,
                username=event.from_user.username,
            )

            # Проверяем, является ли сообщение из группы (не из приватного чата)
            is_group_chat = event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
            
            if is_group_chat:
                # Пользователь не может писать (права ограничены), но на всякий случай блокируем обработку
                # Если права не были ограничены, пытаемся ограничить их сейчас
                bot: Bot = data.get("bot")
                if not bot:
                    bot = Bot.get_current(no_error=True)
                
                if bot:
                    try:
                        # Пытаемся ограничить права, если они еще не ограничены
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
                                ),
                            )
                            logger.debug(
                                "Restricted unverified user %s in chat %s (fallback)",
                                user_id,
                                event.chat.id
                            )
                        except Exception as restrict_error:
                            # Если не удалось ограничить (нет прав или уже ограничен), продолжаем
                            logger.debug(
                                "Could not restrict unverified user %s: %s",
                                user_id,
                                restrict_error
                            )
                    except Exception as e:
                        logger.error("Error handling unverified user in group: %s", e, exc_info=True)
                
                # Блокируем обработку сообщения (даже если права не удалось ограничить)
                return
            
            # Для приватных чатов - проверяем команды
            # Для команды /help показываем сообщение о необходимости верификации
            if event.text and event.text.startswith("/help"):
                await event.answer(
                    "❌ Для использования бота необходимо пройти верификацию.\n\n"
                    "Пожалуйста, используйте команду /start для начала работы."
                )
                return
            
            # Для других сообщений в приватном чате - запускаем процесс верификации
            # Получаем FSM context
            from aiogram.fsm.context import FSMContext
            state: FSMContext = data.get("state")
            
            if state:
                current_state = await state.get_state()
                # Если пользователь уже в процессе верификации, пропускаем
                if current_state == VerificationStates.waiting_for_full_name:
                    return await handler(event, data)
                
                # Запускаем процесс верификации
                await state.set_state(VerificationStates.waiting_for_full_name)
                # Отправляем сообщение в приватный чат пользователя
                bot: Bot = data.get("bot")
                if not bot:
                    bot = Bot.get_current(no_error=True)
                
                if bot:
                    try:
                        verification_message = await bot.send_message(
                            chat_id=event.from_user.id,
                            text=(
                                "👋 <b>Добро пожаловать!</b>\n\n"
                                "Для участия в опросах необходимо пройти верификацию.\n\n"
                                "Пожалуйста, введите ваши <b>Фамилию и Имя</b> через пробел:\n"
                                "Формат: <b>Фамилия Имя</b>\n"
                                "Пример: <code>Иванов Иван</code>\n\n"
                                "Для отмены введите: <code>отмена</code>"
                            ),
                        )
                        # Сохраняем ID сообщения для удаления
                        await state.update_data(verification_bot_message_id=verification_message.message_id)
                    except Exception as e:
                        logger.error("Error sending verification message to user %s: %s", event.from_user.id, e)
                return

        return await handler(event, data)
