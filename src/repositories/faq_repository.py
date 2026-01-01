"""
Репозиторий для работы с FAQ / базой знаний AI-куратора.

Использует PostgreSQL для хранения FAQ с поддержкой:
- Полнотекстового поиска (to_tsvector/to_tsquery)
- Поиска по ключевым словам (массивы)
- RAG (Retrieval-Augmented Generation)
"""
import logging
from typing import List, Optional, Dict, Any
import asyncpg
from asyncpg import Pool, Connection

logger = logging.getLogger(__name__)


class FAQRepository:
    """
    Репозиторий для работы с FAQ в PostgreSQL.
    
    Поддерживает:
    - Поиск по ключевым словам (массивы)
    - Полнотекстовый поиск (PostgreSQL FTS)
    - RAG для AI-куратора
    """
    
    def __init__(self, pool: Pool):
        """
        Инициализация репозитория.
        
        Args:
            pool: Пул соединений asyncpg
        """
        self.pool = pool
    
    async def search_by_keywords(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск FAQ по ключевым словам.
        
        Использует пересечение массивов keywords с ключевыми словами из вопроса.
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных FAQ
        """
        try:
            # Извлекаем ключевые слова из вопроса (убираем стоп-слова)
            words = self._extract_keywords(question)
            
            if not words:
                return []
            
            async with self.pool.acquire() as conn:
                query = """
                    SELECT 
                        id,
                        question,
                        answer,
                        keywords,
                        category,
                        tag,
                        created_at,
                        updated_at
                    FROM faq_ai
                    WHERE keywords && $1::text[]
                    ORDER BY 
                        array_length(keywords & $1::text[], 1) DESC,
                        id DESC
                    LIMIT $2
                """
                rows = await conn.fetch(query, words, limit)
                
                return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error("Ошибка при поиске FAQ по ключевым словам: %s", e, exc_info=True)
            return []
    
    async def search_by_text(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Полнотекстовый поиск FAQ по тексту вопроса и ответа.
        
        Использует PostgreSQL полнотекстовый поиск (to_tsvector/to_tsquery).
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных FAQ
        """
        try:
            # Формируем tsquery из вопроса
            # Убираем стоп-слова и приводим к нормализованному виду
            search_query = self._prepare_tsquery(question)
            
            if not search_query:
                return []
            
            async with self.pool.acquire() as conn:
                query = """
                    SELECT 
                        id,
                        question,
                        answer,
                        keywords,
                        category,
                        tag,
                        created_at,
                        updated_at,
                        ts_rank(search_vector, to_tsquery('russian', $1)) as rank
                    FROM faq_ai
                    WHERE search_vector @@ to_tsquery('russian', $1)
                    ORDER BY rank DESC, id DESC
                    LIMIT $2
                """
                rows = await conn.fetch(query, search_query, limit)
                
                return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error("Ошибка при полнотекстовом поиске FAQ: %s", e, exc_info=True)
            return []
    
    async def search_hybrid(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Гибридный поиск: сначала по ключевым словам, затем полнотекстовый.
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных FAQ (без дубликатов)
        """
        # Сначала поиск по ключевым словам
        keyword_results = await self.search_by_keywords(question, limit)
        
        # Если нашли достаточно результатов, возвращаем их
        if len(keyword_results) >= limit:
            return keyword_results
        
        # Дополняем полнотекстовым поиском
        text_results = await self.search_by_text(question, limit)
        
        # Объединяем результаты, убирая дубликаты по id
        seen_ids = {r['id'] for r in keyword_results}
        unique_results = keyword_results.copy()
        
        for result in text_results:
            if result['id'] not in seen_ids:
                unique_results.append(result)
                seen_ids.add(result['id'])
                if len(unique_results) >= limit:
                    break
        
        return unique_results[:limit]
    
    async def add_faq(
        self,
        question: str,
        answer: str,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None
    ) -> int:
        """
        Добавить новый FAQ в базу знаний.
        
        Args:
            question: Вопрос
            answer: Ответ
            keywords: Ключевые слова (если не указаны, извлекаются автоматически)
            category: Категория FAQ
            tag: Тег для классификации
        
        Returns:
            ID созданной записи
        """
        try:
            # Если keywords не указаны, извлекаем их из вопроса
            if keywords is None:
                keywords = self._extract_keywords(question)
            
            # Создаем search_vector для полнотекстового поиска
            search_text = f"{question} {answer}"
            
            async with self.pool.acquire() as conn:
                query = """
                    INSERT INTO faq_ai (question, answer, keywords, category, tag, search_vector)
                    VALUES ($1, $2, $3::text[], $4, $5, to_tsvector('russian', $6))
                    RETURNING id
                """
                row = await conn.fetchrow(
                    query,
                    question,
                    answer,
                    keywords,
                    category,
                    tag,
                    search_text
                )
                
                logger.info("Добавлен новый FAQ: id=%d, question=%s", row['id'], question[:50])
                return row['id']
        
        except Exception as e:
            logger.error("Ошибка при добавлении FAQ: %s", e, exc_info=True)
            raise
    
    async def update_faq(
        self,
        faq_id: int,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None
    ) -> bool:
        """
        Обновить существующий FAQ.
        
        Args:
            faq_id: ID FAQ для обновления
            question: Новый вопрос (опционально)
            answer: Новый ответ (опционально)
            keywords: Новые ключевые слова (опционально)
            category: Новая категория (опционально)
            tag: Новый тег (опционально)
        
        Returns:
            True если обновление успешно, False если запись не найдена
        """
        try:
            updates = []
            params = []
            param_num = 1
            
            if question is not None:
                updates.append(f"question = ${param_num}")
                params.append(question)
                param_num += 1
            
            if answer is not None:
                updates.append(f"answer = ${param_num}")
                params.append(answer)
                param_num += 1
            
            if keywords is not None:
                updates.append(f"keywords = ${param_num}::text[]")
                params.append(keywords)
                param_num += 1
            
            if category is not None:
                updates.append(f"category = ${param_num}")
                params.append(category)
                param_num += 1
            
            if tag is not None:
                updates.append(f"tag = ${param_num}")
                params.append(tag)
                param_num += 1
            
            # Обновляем search_vector если изменились question или answer
            if question is not None or answer is not None:
                # Нужно получить текущие значения для формирования search_vector
                async with self.pool.acquire() as conn:
                    current = await conn.fetchrow(
                        "SELECT question, answer FROM faq_ai WHERE id = $1",
                        faq_id
                    )
                    if not current:
                        return False
                    
                    new_question = question if question is not None else current['question']
                    new_answer = answer if answer is not None else current['answer']
                    search_text = f"{new_question} {new_answer}"
                    
                    updates.append(f"search_vector = to_tsvector('russian', ${param_num})")
                    params.append(search_text)
                    param_num += 1
            
            if not updates:
                return True  # Нет изменений
            
            updates.append("updated_at = NOW()")
            params.append(faq_id)
            
            async with self.pool.acquire() as conn:
                query = f"""
                    UPDATE faq_ai
                    SET {', '.join(updates)}
                    WHERE id = ${param_num}
                """
                result = await conn.execute(query, *params)
                
                return result == "UPDATE 1"
        
        except Exception as e:
            logger.error("Ошибка при обновлении FAQ: %s", e, exc_info=True)
            return False
    
    async def get_by_id(self, faq_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить FAQ по ID.
        
        Args:
            faq_id: ID FAQ
        
        Returns:
            FAQ или None если не найден
        """
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM faq_ai WHERE id = $1",
                    faq_id
                )
                
                return dict(row) if row else None
        
        except Exception as e:
            logger.error("Ошибка при получении FAQ по ID: %s", e, exc_info=True)
            return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Извлечь ключевые слова из текста.
        
        Убирает стоп-слова и приводит к нижнему регистру.
        
        Args:
            text: Исходный текст
        
        Returns:
            Список ключевых слов
        """
        # Русские стоп-слова (можно расширить)
        stop_words = {
            'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'из', 'к', 'о', 'у', 'за', 'со',
            'что', 'как', 'где', 'когда', 'почему', 'кто', 'какой', 'какая', 'какое',
            'это', 'тот', 'та', 'те', 'эти', 'этот', 'эта', 'это',
            'не', 'нет', 'да', 'или', 'а', 'но', 'же', 'ли', 'бы', 'б',
            'я', 'ты', 'он', 'она', 'оно', 'мы', 'вы', 'они',
            'мой', 'твой', 'его', 'её', 'наш', 'ваш', 'их',
            'быть', 'был', 'была', 'было', 'были',
            'делать', 'делал', 'делала', 'делали',
            'можно', 'нужно', 'надо', 'должен', 'должна', 'должно', 'должны'
        }
        
        # Разбиваем на слова, убираем знаки препинания
        words = text.lower().split()
        keywords = []
        
        for word in words:
            # Убираем знаки препинания
            word = ''.join(c for c in word if c.isalnum() or c in 'ё')
            
            # Пропускаем стоп-слова и слишком короткие слова
            if word and len(word) > 2 and word not in stop_words:
                keywords.append(word)
        
        return keywords
    
    def _prepare_tsquery(self, text: str) -> str:
        """
        Подготовить текст для PostgreSQL tsquery.
        
        Args:
            text: Исходный текст
        
        Returns:
            Строка для tsquery
        """
        keywords = self._extract_keywords(text)
        
        if not keywords:
            return ""
        
        # Формируем tsquery: каждое слово через & (AND) или | (OR)
        # Используем & для более точного поиска
        return ' & '.join(keywords)
