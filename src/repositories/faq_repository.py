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
        Поиск по ключевым словам в единой базе знаний.
        
        Использует пересечение массивов keywords с ключевыми словами из вопроса.
        Ищет только в записях типа 'faq' (FAQ имеют keywords).
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных записей
        """
        try:
            # Извлекаем ключевые слова из вопроса (убираем стоп-слова)
            words = self._extract_keywords(question)
            
            if not words:
                return []
            
            async with self.pool.acquire() as conn:
                # Проверяем, существует ли unified_knowledge_base
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'unified_knowledge_base'
                    )
                """)
                
                if table_exists:
                    # Используем unified_knowledge_base
                    query = """
                        SELECT 
                            id,
                            type,
                            question,
                            answer,
                            keywords,
                            category,
                            tag,
                            source,
                            chunk_index,
                            content,
                            created_at,
                            updated_at
                        FROM unified_knowledge_base
                        WHERE type = 'faq' AND keywords && $1::text[]
                        ORDER BY 
                            array_length(keywords & $1::text[], 1) DESC,
                            id DESC
                        LIMIT $2
                    """
                else:
                    # Fallback на старую таблицу faq_ai
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
                
                # Преобразуем результаты в единый формат
                results = []
                for row in rows:
                    result = dict(row)
                    # Если это unified_knowledge_base, нормализуем формат
                    if 'type' in result:
                        if result['type'] == 'faq':
                            # Для FAQ используем question/answer
                            results.append({
                                'id': result['id'],
                                'question': result['question'],
                                'answer': result['answer'],
                                'keywords': result.get('keywords', []),
                                'category': result.get('category'),
                                'tag': result.get('tag'),
                                'type': 'faq',
                                'created_at': result['created_at'],
                                'updated_at': result['updated_at']
                            })
                        elif result['type'] == 'chunk':
                            # Для chunks используем content как answer
                            results.append({
                                'id': result['id'],
                                'question': f"Информация из {result['source']} (chunk #{result['chunk_index']})",
                                'answer': result['content'],
                                'keywords': [],
                                'category': 'knowledge_base',
                                'tag': None,
                                'type': 'chunk',
                                'source': result['source'],
                                'chunk_index': result['chunk_index'],
                                'created_at': result['created_at'],
                                'updated_at': result['updated_at']
                            })
                    else:
                        # Старый формат из faq_ai
                        results.append(result)
                
                return results
        
        except Exception as e:
            logger.error("Ошибка при поиске по ключевым словам: %s", e, exc_info=True)
            return []
    
    async def search_by_text(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Полнотекстовый поиск по всей базе знаний.
        
        Использует PostgreSQL полнотекстовый поиск (to_tsvector/to_tsquery).
        Ищет в unified_knowledge_base (все типы записей).
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных записей из всей базы знаний
        """
        try:
            # Формируем tsquery из вопроса
            # Убираем стоп-слова и приводим к нормализованному виду
            search_query = self._prepare_tsquery(question)
            
            if not search_query:
                return []
            
            async with self.pool.acquire() as conn:
                # Проверяем, существует ли unified_knowledge_base
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'unified_knowledge_base'
                    )
                """)
                
                if table_exists:
                    # Используем unified_knowledge_base (все типы)
                    query = """
                        SELECT 
                            id,
                            type,
                            question,
                            answer,
                            keywords,
                            category,
                            tag,
                            source,
                            chunk_index,
                            content,
                            created_at,
                            updated_at,
                            ts_rank(search_vector, to_tsquery('russian', $1)) as rank
                        FROM unified_knowledge_base
                        WHERE search_vector @@ to_tsquery('russian', $1)
                        ORDER BY rank DESC, id DESC
                        LIMIT $2
                    """
                else:
                    # Fallback на старую таблицу faq_ai
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
                
                # Преобразуем результаты в единый формат
                results = []
                for row in rows:
                    result = dict(row)
                    # Если это unified_knowledge_base, нормализуем формат
                    if 'type' in result:
                        if result['type'] == 'faq':
                            # Для FAQ используем question/answer
                            results.append({
                                'id': result['id'],
                                'question': result['question'],
                                'answer': result['answer'],
                                'keywords': result.get('keywords', []),
                                'category': result.get('category'),
                                'tag': result.get('tag'),
                                'type': 'faq',
                                'rank': result.get('rank', 0),
                                'created_at': result['created_at'],
                                'updated_at': result['updated_at']
                            })
                        elif result['type'] == 'chunk':
                            # Для chunks используем content как answer
                            results.append({
                                'id': result['id'],
                                'question': f"Информация из {result['source']} (chunk #{result['chunk_index']})",
                                'answer': result['content'],
                                'keywords': [],
                                'category': 'knowledge_base',
                                'tag': None,
                                'type': 'chunk',
                                'source': result['source'],
                                'chunk_index': result['chunk_index'],
                                'rank': result.get('rank', 0),
                                'created_at': result['created_at'],
                                'updated_at': result['updated_at']
                            })
                    else:
                        # Старый формат из faq_ai
                        results.append(result)
                
                return results
        
        except Exception as e:
            logger.error("Ошибка при полнотекстовом поиске: %s", e, exc_info=True)
            return []
    
    async def search_knowledge_base(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Поиск chunks в единой базе знаний.
        
        Использует полнотекстовый поиск PostgreSQL.
        Ищет только записи типа 'chunk' в unified_knowledge_base.
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных chunks в формате, совместимом с FAQ
        """
        try:
            # Формируем tsquery из вопроса
            search_query = self._prepare_tsquery(question)
            
            if not search_query:
                return []
            
            async with self.pool.acquire() as conn:
                # Проверяем, существует ли unified_knowledge_base
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'unified_knowledge_base'
                    )
                """)
                
                if table_exists:
                    # Используем unified_knowledge_base (только chunks)
                    query = """
                        SELECT 
                            id,
                            source,
                            content,
                            chunk_index,
                            created_at,
                            updated_at,
                            ts_rank(search_vector, to_tsquery('russian', $1)) as rank
                        FROM unified_knowledge_base
                        WHERE type = 'chunk' 
                        AND search_vector @@ to_tsquery('russian', $1)
                        ORDER BY rank DESC, chunk_index ASC
                        LIMIT $2
                    """
                else:
                    # Fallback на старую таблицу knowledge_base
                    query = """
                        SELECT 
                            id,
                            source,
                            content,
                            chunk_index,
                            created_at,
                            updated_at,
                            ts_rank(to_tsvector('russian', content), to_tsquery('russian', $1)) as rank
                        FROM knowledge_base
                        WHERE to_tsvector('russian', content) @@ to_tsquery('russian', $1)
                        ORDER BY rank DESC, chunk_index ASC
                        LIMIT $2
                    """
                
                rows = await conn.fetch(query, search_query, limit)
                
                # Преобразуем в формат, совместимый с FAQ
                results = []
                for row in rows:
                    results.append({
                        'id': f"kb_{row['id']}",  # Префикс для отличия от FAQ
                        'question': f"Информация из {row['source']} (chunk #{row['chunk_index']})",
                        'answer': row['content'],
                        'source': row['source'],
                        'chunk_index': row['chunk_index'],
                        'category': 'knowledge_base',
                        'tag': None,
                        'keywords': [],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                        'rank': row['rank']
                    })
                
                return results
        
        except Exception as e:
            logger.error("Ошибка при поиске chunks: %s", e, exc_info=True)
            return []
    
    async def search_hybrid(
        self,
        question: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Гибридный поиск по единой базе знаний.
        
        Если используется unified_knowledge_base:
        - Сначала поиск по ключевым словам (только FAQ)
        - Затем полнотекстовый поиск (все типы записей)
        
        Если используется старая структура:
        - Сначала в таблице faq_ai (по ключевым словам и полнотекстовый)
        - Затем в таблице knowledge_base (chunks из PDF)
        
        Args:
            question: Вопрос пользователя
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных результатов из всей базы знаний (без дубликатов)
        """
        # Сначала поиск по ключевым словам (только FAQ)
        keyword_results = await self.search_by_keywords(question, limit)
        
        # Объединяем результаты (ключевые слова + полнотекстовый поиск)
        seen_ids = {r['id'] for r in keyword_results}
        all_results = keyword_results.copy()
        
        # Если не хватает результатов, дополняем полнотекстовым поиском
        # (он уже ищет во всей unified_knowledge_base, включая chunks)
        if len(all_results) < limit:
            text_results = await self.search_by_text(question, limit * 2)  # Берем больше для фильтрации
            
            for result in text_results:
                # Пропускаем дубликаты
                result_id = result.get('id') or f"{result.get('type', 'unknown')}_{result.get('id', 0)}"
                if result_id not in seen_ids:
                    all_results.append(result)
                    seen_ids.add(result_id)
                    if len(all_results) >= limit:
                        break
        
        return all_results[:limit]
    
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
        
        Добавляет в unified_knowledge_base, если она существует,
        иначе в старую таблицу faq_ai.
        
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
            
            async with self.pool.acquire() as conn:
                # Проверяем, существует ли unified_knowledge_base
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'unified_knowledge_base'
                    )
                """)
                
                if table_exists:
                    # Используем unified_knowledge_base
                    query = """
                        INSERT INTO unified_knowledge_base (
                            type, question, answer, keywords, category, tag, search_vector
                        )
                        VALUES (
                            'faq', $1, $2, $3::text[], $4, $5, 
                            to_tsvector('russian', $6 || ' ' || $7)
                        )
                        RETURNING id
                    """
                    row = await conn.fetchrow(
                        query,
                        question,
                        answer,
                        keywords,
                        category,
                        tag,
                        question,
                        answer
                    )
                else:
                    # Fallback на старую таблицу faq_ai
                    search_text = f"{question} {answer}"
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
