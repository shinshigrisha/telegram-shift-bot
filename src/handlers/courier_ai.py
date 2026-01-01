"""
Обработчик сообщений от курьеров для AI-куратора.

Использует RAG (Retrieval-Augmented Generation) через PostgreSQL для поиска релевантных FAQ.

Работает в три этапа:
1. Rule-based ответы для частых сценариев (терминал сломан, ДТП, повреждение товара, недозвон).
2. Must-match кейсы из конфигурации (обязательные маршруты).
3. Генерация через AI-куратора (Groq + LLaMA 3) с RAG через PostgreSQL, если доступен GROQ_API_KEY.
"""
import logging
from typing import Optional

# Сторонние библиотеки
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.enums import ChatType
from redis.asyncio import Redis

# Локальные импорты
from config.settings import settings
from src.ai.curator import AICurator
from src.repositories.faq_repository import FAQRepository
from src.services.ai_response_service import ai_response_service

logger = logging.getLogger(__name__)

router = Router(name="courier_ai")


@router.message()
async def handle_courier_message(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Обработка сообщений от курьеров.
    
    Обрабатывает только текстовые сообщения в приватных чатах.
    Сначала пытается выдать rule-based ответ, затем обращается к AI-куратору (если доступен).
    
    Args:
        message: Сообщение от пользователя
        bot: Экземпляр бота
        faq_repo: Репозиторий для работы с FAQ (dependency injection)
        redis: Клиент Redis для хранения истории (dependency injection)
    """
    # Обрабатываем только приватные чаты
    if message.chat.type != ChatType.PRIVATE:
        return
    
    # Проверяем, что это текстовое сообщение
    if not message.text or not message.from_user:
        return
    
    try:
        user_id = message.from_user.id
        question = message.text.strip()
        
        # Игнорируем слишком короткие сообщения (возможно, случайные символы)
        if len(question) < 3:
            return
        
        # Игнорируем команды (они обрабатываются другими handlers)
        if question.startswith("/"):
            return
        
        # Быстрый ответ для типовых сценариев
        quick_reply = ai_response_service.build_courier_quick_reply(question)
        if quick_reply:
            await message.answer(quick_reply)
            return

        # Если нет зависимостей (БД/Redis) или ключа — используем rule-based ответ
        if faq_repo is None or redis is None:
            logger.warning(
                "Missing dependencies in courier_ai handler: faq_repo=%s, redis=%s. "
                "Отправляю rule-based ответ без AI.",
                faq_repo is not None,
                redis is not None,
            )
            await message.answer(ai_response_service.build_courier_generic_answer(question))
            return

        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY не установлен, использую rule-based ответ без AI.")
            await message.answer(ai_response_service.build_courier_generic_answer(question))
            return

        curator = AICurator(
            faq_repo=faq_repo,
            redis=redis,
        )

        await bot.send_chat_action(message.chat.id, "typing")

        answer = await curator.generate_response(
            user_id=user_id,
            question=question,
            prompt_type="question",
        )

        await message.answer(answer)

        logger.info(
            "AI-куратор обработал сообщение от пользователя %s (длина вопроса: %d символов)",
            user_id,
            len(question),
        )

    except ValueError as e:
        logger.error("Ошибка конфигурации AI-куратора: %s", e, exc_info=True)
        await message.answer(ai_response_service.build_courier_generic_answer(message.text.strip()))

    except Exception as e:  # noqa: BLE001
        logger.error(
            "Ошибка при обработке сообщения от пользователя %s: %s",
            message.from_user.id if message.from_user else "unknown",
            e,
            exc_info=True,
        )
        await message.answer(
            ai_response_service.build_courier_generic_answer(message.text.strip())
        )