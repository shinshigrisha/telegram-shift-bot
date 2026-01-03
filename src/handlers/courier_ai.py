"""
Простой обработчик сообщений от курьеров для AI-куратора.

Использует SimpleCuratorService для поиска ответов в таблице FAQ.
Если ответ найден — форматирует через Groq API.
Если ответ не найден — отправляет к живому куратору.
"""
import logging
from typing import Optional

# Сторонние библиотеки
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.enums import ChatType
from aiogram.filters import MagicData

# Локальные импорты
from src.repositories.faq_repository import FAQRepository
from src.services.simple_curator_service import SimpleCuratorService
from src.services.ai_enhanced_curator import EnhancedCuratorService
from src.services.new_curator_service import NewCuratorService
from src.services.ai_response_service import ai_response_service
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

router = Router(name="courier_ai")


@router.message()
async def handle_courier_message(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
    **kwargs,  # Для явного доступа к data из middleware
) -> None:
    """
    Обработка сообщений от курьеров.
    
    Обрабатывает только текстовые сообщения в приватных чатах.
    Использует EnhancedCuratorService (с живым общением) или SimpleCuratorService
    для поиска ответов в FAQ.
    
    Args:
        message: Сообщение от пользователя
        bot: Экземпляр бота
        faq_repo: Репозиторий для работы с FAQ (dependency injection)
        redis: Клиент Redis для памяти стиля общения (dependency injection)
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
        
        # Быстрый ответ для типовых сценариев (опционально, можно убрать)
        quick_reply = ai_response_service.build_courier_quick_reply(question)
        if quick_reply:
            await message.answer(quick_reply)
            return

        # Если нет FAQ репозитория — отправляем общий ответ
        if faq_repo is None:
            logger.warning(
                "FAQ репозиторий недоступен. Отправляю общий ответ."
            )
            await message.answer(ai_response_service.build_courier_generic_answer(question))
            return

        # Создаём улучшенный AI-куратор (с живым общением)
        # Использует EnhancedCuratorService, который является обёрткой над SimpleCuratorService
        # и добавляет: анализ контекста, определение роли, память стиля, переходные фразы
        
        # Пытаемся получить Redis из middleware, если не передан через параметр
        # В aiogram 3 dependency injection работает автоматически, но иногда нужно явно получать из data
        if redis is None:
            # Пробуем получить из kwargs (data из middleware)
            if kwargs and "redis" in kwargs:
                redis = kwargs["redis"]
                logger.info("Redis получен из kwargs для пользователя %s", user_id)
            
            # Если всё ещё None, создаём Redis клиент напрямую (он уже используется для FSM)
            if redis is None:
                try:
                    from config.settings import settings
                    from redis.asyncio import Redis as RedisClient
                    redis = RedisClient.from_url(settings.REDIS_URL, decode_responses=True)
                    await redis.ping()  # Проверяем подключение
                    logger.info("Redis клиент создан напрямую для пользователя %s", user_id)
                except Exception as e:
                    logger.warning("Не удалось создать Redis клиент: %s", e)
                    redis = None
        
        logger.info("Redis доступен: %s, тип: %s", redis is not None, type(redis).__name__ if redis else "None")
        logger.info("FAQ repo доступен: %s", faq_repo is not None)
        
        # Используем новый куратор с DecisionEngine, ResponseValidator и ExplainabilityLogger
        # Для explainability логов создаем директорию logs/explainability
        from pathlib import Path
        log_dir = Path(__file__).parent.parent.parent / "logs" / "explainability"
        
        try:
            curator = NewCuratorService(faq_repo=faq_repo, log_dir=log_dir)
            logger.info("✅ Используется NewCuratorService (новая архитектура) для пользователя %s", user_id)
        except Exception as e:
            logger.error("❌ Ошибка при создании NewCuratorService: %s. Используем SimpleCuratorService.", e, exc_info=True)
            curator = SimpleCuratorService(faq_repo=faq_repo)

        # Показываем, что бот печатает
        await bot.send_chat_action(message.chat.id, "typing")

        # Получаем ответ от куратора
        # NewCuratorService.get_answer() принимает user_id для логирования
        if isinstance(curator, NewCuratorService):
            answer = await curator.get_answer(question, user_id=user_id)
        elif isinstance(curator, EnhancedCuratorService):
            answer = await curator.get_answer(question, user_id=user_id)
        else:
            answer = await curator.get_answer(question)

        # Отправляем ответ курьеру
        await message.answer(answer)

        logger.info(
            "AI-куратор обработал сообщение от пользователя %s (длина вопроса: %d символов)",
            user_id,
            len(question),
        )

    except Exception as e:  # noqa: BLE001
        logger.error(
            "Ошибка при обработке сообщения от пользователя %s: %s",
            message.from_user.id if message.from_user else "unknown",
            e,
            exc_info=True,
        )
        # В случае ошибки отправляем общий ответ
        await message.answer(
            ai_response_service.build_courier_generic_answer(message.text.strip())
        )