"""
Простой AI-куратор для курьеров.

Ищет ответы в таблице FAQ (PostgreSQL).
Если ответ найден — форматирует через Groq API.
Если ответ не найден — отправляет к живому куратору.

Минимум логики, без must-match и сложных конфигов.
"""
import logging
from typing import Optional, List, Dict, Any

from groq import Groq  # pyright: ignore[reportMissingImports]

from config.settings import settings
from src.repositories.faq_repository import FAQRepository

logger = logging.getLogger(__name__)


class SimpleCuratorService:
    """
    Простой AI-куратор для обработки вопросов курьеров.
    
    Работает по простой логике:
    1. Ищет ответы в таблице FAQ
    2. Если нашел — форматирует через Groq API
    3. Если не нашел — отправляет к живому куратору
    """
    
    def __init__(
        self,
        faq_repo: FAQRepository,
        groq_api_key: Optional[str] = None,
    ) -> None:
        """
        Инициализация простого AI-куратора.
        
        Args:
            faq_repo: Репозиторий для работы с FAQ
            groq_api_key: API ключ Groq (если не передан, берется из settings)
        """
        self.faq_repo = faq_repo
        
        # Инициализация Groq API (опционально)
        api_key = groq_api_key or settings.GROQ_API_KEY
        if api_key:
            try:
                self.client = Groq(api_key=api_key)
                self.model_name = "llama-3.1-8b-instant"
                self.groq_enabled = True
            except Exception as e:
                logger.warning("Не удалось инициализировать Groq API: %s", e)
                self.groq_enabled = False
        else:
            self.groq_enabled = False
            logger.info("GROQ_API_KEY не установлен, форматирование через AI отключено")
    
    async def get_answer(self, question: str) -> str:
        """
        Получить ответ на вопрос курьера.
        
        Логика:
        1. Ищет релевантные FAQ в базе данных
        2. Если нашел — форматирует ответ (через Groq, если доступен)
        3. Если не нашел — возвращает сообщение об эскалации
        
        Args:
            question: Вопрос курьера
            
        Returns:
            Ответ на вопрос или сообщение об эскалации
        """
        try:
            # Ищем релевантные FAQ в базе данных
            faqs = await self.faq_repo.search_hybrid(question, limit=3)
            
            # Если FAQ не найдены — отправляем к живому куратору
            if not faqs or len(faqs) == 0:
                logger.info(
                    "FAQ не найдены для вопроса: %s. Отправляем к живому куратору.",
                    question[:50]
                )
                return self._get_escalation_message()
            
            # Если нашли FAQ — используем первый (самый релевантный)
            best_faq = faqs[0]
            answer = best_faq.get("answer", "")
            
            # Если Groq доступен — форматируем ответ через AI
            if self.groq_enabled and answer:
                try:
                    formatted_answer = await self._format_answer_with_ai(question, answer, faqs)
                    return formatted_answer
                except Exception as e:
                    logger.warning(
                        "Ошибка при форматировании ответа через Groq: %s. Используем ответ из FAQ.",
                        e
                    )
                    # Если AI не сработал — просто возвращаем ответ из FAQ
                    return answer
            
            # Если Groq недоступен — просто возвращаем ответ из FAQ
            return answer
            
        except Exception as e:
            logger.error(
                "Ошибка при получении ответа: %s",
                e,
                exc_info=True
            )
            # В случае ошибки — отправляем к живому куратору
            return self._get_escalation_message()
    
    async def _format_answer_with_ai(
        self,
        question: str,
        answer: str,
        faqs: List[Dict[str, Any]]
    ) -> str:
        """
        Форматировать ответ через Groq API.
        
        Использует простой промпт для улучшения ответа из FAQ.
        
        Args:
            question: Вопрос курьера
            answer: Ответ из FAQ
            faqs: Список найденных FAQ (для контекста)
            
        Returns:
            Отформатированный ответ
        """
        # Формируем контекст из найденных FAQ
        context = "\n\n".join([
            f"Вопрос: {faq.get('question', '')}\nОтвет: {faq.get('answer', '')}"
            for faq in faqs[:2]  # Берем максимум 2 FAQ для контекста
        ])
        
        # Простой системный промпт
        system_prompt = """Ты — виртуальный куратор курьерской доставки.
Твоя задача — помочь курьеру, используя информацию из базы знаний.

Правила:
1. Используй ТОЛЬКО информацию из базы знаний
2. Отвечай кратко и по делу
3. Будь дружелюбным и профессиональным
4. Если информации недостаточно — скажи об этом"""
        
        # Формируем запрос
        user_prompt = f"""Вопрос курьера: {question}

Информация из базы знаний:
{context}

Сформулируй ответ курьеру на основе информации из базы знаний. 
Ответ должен быть понятным и полезным."""
        
        # Генерируем ответ через Groq API
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500,
        )
        
        formatted = response.choices[0].message.content.strip()
        return formatted if formatted else answer
    
    def _get_escalation_message(self) -> str:
        """
        Получить сообщение об эскалации к живому куратору.
        
        Returns:
            Текст сообщения об эскалации
        """
        return (
            "👋 Спасибо за ваш вопрос!\n\n"
            "К сожалению, в базе знаний нет ответа на ваш вопрос. "
            "Для получения помощи обратитесь к живому куратору.\n\n"
            "Он поможет вам разобраться в ситуации."
        )
