"""
Сервис для работы с AI-куратором.

Предоставляет удобные функции для:
- Обработки сообщений от курьеров
- Создания информационных сообщений
- Генерации замечаний
- Рассылок
"""
import logging
from typing import Optional
from src.ai.curator import AICurator
from src.repositories.faq_repository import FAQRepository
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CuratorService:
    """
    Сервис для работы с AI-куратором.
    
    Обёртка над AICurator для удобного использования в handlers.
    """
    
    def __init__(
        self,
        faq_repo: FAQRepository,
        redis: Redis,
    ):
        """
        Инициализация сервиса.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
            redis: Клиент Redis для истории диалогов
        """
        self.curator = AICurator(
            faq_repo=faq_repo,
            redis=redis,
        )
    
    async def handle_courier_question(
        self,
        user_id: int,
        question: str,
    ) -> str:
        """
        Обработать вопрос от курьера.
        
        Использует RAG через PostgreSQL для поиска релевантных FAQ.
        
        Args:
            user_id: ID пользователя в Telegram
            question: Вопрос курьера
        
        Returns:
            Ответ AI-куратора
        """
        return await self.curator.generate_response(
            user_id=user_id,
            question=question,
            prompt_type="question",
        )
    
    async def create_info_message(
        self,
        topic: str,
        details: Optional[str] = None,
    ) -> str:
        """
        Создать информационное сообщение для курьеров.
        
        Используется для рассылок и информационных уведомлений.
        
        Args:
            topic: Тема сообщения (например: "Правила парковки при доставке")
            details: Дополнительные детали (опционально)
        
        Returns:
            Текст информационного сообщения
        
        Example:
            >>> service = CuratorService(faq_repo, redis)
            >>> msg = await service.create_info_message("Правила парковки при доставке")
            >>> print(msg)
        """
        return await self.curator.generate_broadcast(
            topic=topic,
            details=details,
        )
    
    async def create_warning(
        self,
        user_id: int,
        violation_description: str,
    ) -> str:
        """
        Создать замечание курьеру о нарушении.
        
        Args:
            user_id: ID курьера в Telegram
            violation_description: Описание нарушения
        
        Returns:
            Текст замечания
        
        Example:
            >>> service = CuratorService(faq_repo, redis)
            >>> warning = await service.create_warning(
            ...     user_id=12345,
            ...     violation_description="Курьер не дозвонился и оставил заказ у двери"
            ... )
        """
        return await self.curator.generate_warning(
            user_id=user_id,
            violation_description=violation_description,
        )
    
    async def add_faq_to_knowledge_base(
        self,
        question: str,
        answer: str,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        keywords: Optional[list] = None,
    ) -> int:
        """
        Добавить новый FAQ в базу знаний.
        
        После добавления FAQ сразу доступен для RAG-поиска.
        
        Args:
            question: Вопрос
            answer: Ответ
            category: Категория (опционально)
            tag: Тег для классификации (опционально)
            keywords: Ключевые слова (опционально, извлекаются автоматически)
        
        Returns:
            ID созданной записи
        
        Example:
            >>> service = CuratorService(faq_repo, redis)
            >>> faq_id = await service.add_faq_to_knowledge_base(
            ...     question="Что делать при ДТП?",
            ...     answer="Немедленно сообщить куратору и вызвать ГИБДД.",
            ...     category="Безопасность",
            ...     tag="ДТП"
            ... )
        """
        return await self.curator.faq_repo.add_faq(
            question=question,
            answer=answer,
            keywords=keywords,
            category=category,
            tag=tag,
        )
    
    async def search_faq(
        self,
        query: str,
        limit: int = 5,
    ) -> list:
        """
        Поиск FAQ по запросу (для администраторов/кураторов).
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных FAQ
        """
        return await self.curator.faq_repo.search_hybrid(
            question=query,
            limit=limit,
        )
    
    async def clear_user_history(self, user_id: int) -> None:
        """
        Очистить историю диалога пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
        """
        await self.curator.clear_history(user_id)
