import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from config.settings import settings
from src.services.user_service import UserService
from src.states.verification_states import VerificationStates
from src.utils.auth import is_curator

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
        
        # Пропускаем кураторов без верификации
        if event.from_user and is_curator(event.from_user):
            return await handler(event, data)

        # Пропускаем команду /start без проверки (для верификации)
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)
        
        # Для команды /help проверяем верификацию
        if event.text and event.text.startswith("/help"):
            # Проверяем верификацию, но не блокируем
            user_service: Optional[UserService] = data.get("user_service")
            if user_service:
                user_id = event.from_user.id
                is_verified = await user_service.is_verified(user_id)
                if not is_verified:
                    await event.answer(
                        "❌ Для использования бота необходимо пройти верификацию.\n\n"
                        "Пожалуйста, используйте команду /start для начала работы."
                    )
                    return
            return await handler(event, data)

        # Получаем user_service из data (должен быть добавлен DatabaseMiddleware)
        user_service: UserService | None = data.get("user_service")
        if not user_service:
            return await handler(event, data)

        user_id = event.from_user.id

        # Проверяем верификацию
        is_verified = await user_service.is_verified(user_id)

        # Если пользователь не верифицирован, запускаем процесс верификации
        if not is_verified:
            # Создаем или получаем пользователя
            await user_service.get_or_create_user(
                user_id=user_id,
                first_name=event.from_user.first_name,
                last_name=event.from_user.last_name,
                username=event.from_user.username,
            )

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
                from aiogram import Bot
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

