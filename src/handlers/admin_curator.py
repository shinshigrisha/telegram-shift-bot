"""
Обработчики для администраторов/кураторов по управлению AI-куратором.

Позволяют:
- Добавлять новые FAQ в базу знаний
- Искать FAQ
- Создавать информационные сообщения
- Генерировать замечания
"""
import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from redis.asyncio import Redis

from src.repositories.faq_repository import FAQRepository
from src.services.curator_service import CuratorService

logger = logging.getLogger(__name__)

router = Router(name="admin_curator")


@router.message(Command("add_faq"))
async def handle_add_faq(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Добавить новый FAQ в базу знаний.
    
    Формат команды: /add_faq
    Затем бот запросит вопрос и ответ.
    """
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        return
    
    # TODO: Реализовать интерактивный диалог для добавления FAQ
    await message.answer(
        "📝 Для добавления FAQ используйте формат:\n"
        "/add_faq\n"
        "Вопрос: ...\n"
        "Ответ: ...\n"
        "Категория: ... (опционально)\n"
        "Тег: ... (опционально)"
    )


@router.message(Command("search_faq"))
async def handle_search_faq(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Поиск FAQ в базе знаний.
    
    Формат команды: /search_faq <запрос>
    """
    if faq_repo is None:
        await message.answer("❌ База данных недоступна")
        return
    
    # Извлекаем запрос из команды
    query = message.text.replace("/search_faq", "").strip()
    
    if not query:
        await message.answer("❌ Укажите поисковый запрос: /search_faq <запрос>")
        return
    
    try:
        service = CuratorService(faq_repo, redis) if redis else None
        if service is None:
            await message.answer("❌ Redis недоступен")
            return
        
        results = await service.search_faq(query, limit=5)
        
        if not results:
            await message.answer(f"❌ По запросу «{query}» ничего не найдено")
            return
        
        response = f"🔍 Найдено {len(results)} результатов:\n\n"
        for idx, faq in enumerate(results, 1):
            response += f"{idx}. {faq.get('question', '')[:50]}...\n"
            if faq.get('category'):
                response += f"   Категория: {faq.get('category')}\n"
            if faq.get('tag'):
                response += f"   Тег: {faq.get('tag')}\n"
            response += "\n"
        
        await message.answer(response)
    
    except Exception as e:
        logger.error("Ошибка при поиске FAQ: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при поиске FAQ")


@router.message(Command("create_info"))
async def handle_create_info(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Создать информационное сообщение для рассылки.
    
    Формат команды: /create_info <тема>
    """
    if faq_repo is None or redis is None:
        await message.answer("❌ База данных или Redis недоступны")
        return
    
    # Извлекаем тему из команды
    topic = message.text.replace("/create_info", "").strip()
    
    if not topic:
        await message.answer("❌ Укажите тему: /create_info <тема>")
        return
    
    try:
        service = CuratorService(faq_repo, redis)
        info_message = await service.create_info_message(topic)
        
        await message.answer(
            f"📢 Информационное сообщение:\n\n{info_message}"
        )
    
    except Exception as e:
        logger.error("Ошибка при создании информационного сообщения: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при создании сообщения")


@router.message(Command("clear_history"))
async def handle_clear_history(
    message: Message,
    bot: Bot,
    faq_repo: Optional[FAQRepository] = None,
    redis: Optional[Redis] = None,
) -> None:
    """
    Очистить историю диалога пользователя.
    
    Формат команды: /clear_history [user_id]
    """
    if redis is None:
        await message.answer("❌ Redis недоступен")
        return
    
    # Извлекаем user_id из команды (если указан)
    parts = message.text.split()
    if len(parts) > 1:
        try:
            user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат user_id")
            return
    else:
        # Используем ID отправителя
        user_id = message.from_user.id if message.from_user else None
        if user_id is None:
            await message.answer("❌ Не удалось определить user_id")
            return
    
    try:
        service = CuratorService(faq_repo, redis) if faq_repo else None
        if service is None:
            await message.answer("❌ FAQ репозиторий недоступен")
            return
        
        await service.clear_user_history(user_id)
        await message.answer(f"✅ История диалога пользователя {user_id} очищена")
    
    except Exception as e:
        logger.error("Ошибка при очистке истории: %s", e, exc_info=True)
        await message.answer("❌ Ошибка при очистке истории")
