"""
Вспомогательные функции для работы с AI-куратором.

Примеры использования RAG через PostgreSQL и Redis.
"""
import logging
from typing import Optional
from src.ai.curator import AICurator
from src.repositories.faq_repository import FAQRepository
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def create_info_message(
    curator: AICurator,
    topic: str,
    details: Optional[str] = None
) -> str:
    """
    Создать информационное сообщение для рассылки курьерам.
    
    Использует RAG для поиска релевантной информации из базы знаний.
    
    Args:
        curator: Экземпляр AI-куратора
        topic: Тема сообщения (например: "Правила парковки при доставке")
        details: Дополнительные детали (опционально)
    
    Returns:
        Текст информационного сообщения
    
    Example:
        message = await create_info_message(
            curator=curator,
            topic="Правила парковки при доставке",
            details="С 1 января новые правила парковки в центре города"
        )
    """
    return await curator.generate_broadcast(topic=topic, details=details)


async def create_warning_message(
    curator: AICurator,
    user_id: int,
    violation_description: str
) -> str:
    """
    Создать замечание курьеру о нарушении регламента.
    
    Использует правила общения из конфигурации для корректного формулирования.
    
    Args:
        curator: Экземпляр AI-куратора
        user_id: ID курьера в Telegram
        violation_description: Описание нарушения (например: "Курьер не дозвонился и оставил заказ")
    
    Returns:
        Текст замечания (вежливый и конструктивный)
    
    Example:
        warning = await create_warning_message(
            curator=curator,
            user_id=12345,
            violation_description="Курьер не дозвонился и оставил заказ у двери без настройки"
        )
    """
    return await curator.generate_warning(
        user_id=user_id,
        violation_description=violation_description
    )


async def add_faq_to_knowledge_base(
    faq_repo: FAQRepository,
    question: str,
    answer: str,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    keywords: Optional[list] = None
) -> int:
    """
    Добавить новый FAQ в базу знаний (RAG на лету).
    
    После добавления бот сразу сможет использовать этот FAQ для ответов.
    
    Args:
        faq_repo: Репозиторий FAQ
        question: Вопрос
        answer: Ответ
        category: Категория (например: "Доставка", "Оплата")
        tag: Тег для классификации (например: "Неаккуратная доставка")
        keywords: Ключевые слова (если не указаны, извлекаются автоматически)
    
    Returns:
        ID созданной записи
    
    Example:
        faq_id = await add_faq_to_knowledge_base(
            faq_repo=faq_repo,
            question="Что делать, если товар повреждён?",
            answer="Зафиксировать обращение с тегом «Неаккуратная доставка».",
            category="Доставка",
            tag="Неаккуратная доставка"
        )
    """
    return await faq_repo.add_faq(
        question=question,
        answer=answer,
        keywords=keywords,
        category=category,
        tag=tag
    )


async def search_knowledge_base(
    faq_repo: FAQRepository,
    query: str,
    limit: int = 5
) -> list:
    """
    Поиск в базе знаний по запросу (RAG).
    
    Использует гибридный поиск: сначала по ключевым словам, затем полнотекстовый.
    
    Args:
        faq_repo: Репозиторий FAQ
        query: Поисковый запрос
        limit: Максимальное количество результатов
    
    Returns:
        Список найденных FAQ
    
    Example:
        results = await search_knowledge_base(
            faq_repo=faq_repo,
            query="покупатель не отвечает",
            limit=5
        )
        for faq in results:
            print(f"Q: {faq['question']}\nA: {faq['answer']}\n")
    """
    return await faq_repo.search_hybrid(query, limit=limit)
