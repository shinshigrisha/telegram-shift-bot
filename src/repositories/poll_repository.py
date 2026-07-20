"""
Репозиторий для работы с опросами в PostgreSQL.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from asyncpg import Pool
import json

logger = logging.getLogger(__name__)


def _normalize_poll_dict(poll_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует словарь опроса, обрабатывая JSONB поля.
    """
    if "results" in poll_dict:
        results = poll_dict["results"]
        if isinstance(results, str):
            try:
                poll_dict["results"] = json.loads(results)
            except (json.JSONDecodeError, TypeError):
                poll_dict["results"] = {}
        elif results is None:
            poll_dict["results"] = {}
    return poll_dict


class PollRepository:
    """
    Репозиторий для работы с опросами в PostgreSQL.
    
    Поддерживает CRUD операции для таблицы daily_polls.
    """
    
    def __init__(self, pool: Pool):
        """
        Инициализация репозитория.
        
        Args:
            pool: Пул соединений asyncpg
        """
        self.pool = pool
    
    async def create(
        self,
        group_id: int,
        poll_date: date,
        telegram_poll_id: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        status: str = "active",
        results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Создать новый опрос.
        
        Args:
            group_id: ID группы
            poll_date: Дата опроса
            telegram_poll_id: ID опроса в Telegram (опционально)
            telegram_message_id: ID сообщения с опросом (опционально)
            status: Статус опроса (по умолчанию "active")
            results: Результаты опроса в формате JSON (опционально)
            
        Returns:
            Словарь с данными созданного опроса
        """
        async with self.pool.acquire() as conn:
            query = """
                INSERT INTO daily_polls (
                    group_id, poll_date, telegram_poll_id, telegram_message_id,
                    status, results
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING *
            """
            row = await conn.fetchrow(
                query,
                group_id,
                poll_date,
                telegram_poll_id,
                telegram_message_id,
                status,
                json.dumps(results) if results else None,
            )
            
            logger.info("Создан опрос: id=%s, group_id=%d, date=%s", row['id'], group_id, poll_date)
            return _normalize_poll_dict(dict(row))
    
    async def get_by_id(self, poll_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить опрос по ID.
        
        Args:
            poll_id: UUID опроса
            
        Returns:
            Словарь с данными опроса или None если не найден
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM daily_polls WHERE id = $1",
                poll_id
            )
            return _normalize_poll_dict(dict(row)) if row else None
    
    async def get_by_group_and_date(
        self,
        group_id: int,
        poll_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Получить опрос по группе и дате.
        
        Args:
            group_id: ID группы
            poll_date: Дата опроса
            
        Returns:
            Словарь с данными опроса или None если не найден
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM daily_polls
                WHERE group_id = $1 AND poll_date = $2
                ORDER BY
                    CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                    created_at DESC,
                    id DESC
                LIMIT 1
                """,
                group_id,
                poll_date
            )
            return _normalize_poll_dict(dict(row)) if row else None

    async def get_latest_by_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Получить последний опрос группы независимо от даты и статуса."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM daily_polls
                WHERE group_id = $1
                ORDER BY created_at DESC, poll_date DESC
                LIMIT 1
                """,
                group_id,
            )
            return _normalize_poll_dict(dict(row)) if row else None

    async def get_latest_active_by_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Получить последний активный опрос группы независимо от даты."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM daily_polls
                WHERE group_id = $1 AND status = 'active'
                ORDER BY created_at DESC, poll_date DESC
                LIMIT 1
                """,
                group_id,
            )
            return _normalize_poll_dict(dict(row)) if row else None

    async def get_by_telegram_poll_id(self, telegram_poll_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить опрос по Telegram poll id.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM daily_polls WHERE telegram_poll_id = $1",
                telegram_poll_id,
            )
            return _normalize_poll_dict(dict(row)) if row else None
    
    async def get_active_polls(self, group_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Получить все активные опросы.
        
        Args:
            group_id: ID группы (опционально, если None - все группы)
            
        Returns:
            Список словарей с данными опросов
        """
        async with self.pool.acquire() as conn:
            if group_id:
                rows = await conn.fetch(
                    "SELECT * FROM daily_polls WHERE status = 'active' AND group_id = $1 ORDER BY poll_date",
                    group_id
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM daily_polls WHERE status = 'active' ORDER BY poll_date, group_id"
                )
            return [_normalize_poll_dict(dict(row)) for row in rows]
    
    async def get_by_date_range(
        self,
        start_date: date,
        end_date: date,
        group_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить опросы за период.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            group_id: ID группы (опционально)
            
        Returns:
            Список словарей с данными опросов
        """
        async with self.pool.acquire() as conn:
            if group_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM daily_polls
                    WHERE poll_date BETWEEN $1 AND $2 AND group_id = $3
                    ORDER BY poll_date, group_id
                    """,
                    start_date,
                    end_date,
                    group_id
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM daily_polls
                    WHERE poll_date BETWEEN $1 AND $2
                    ORDER BY poll_date, group_id
                    """,
                    start_date,
                    end_date
                )
            return [_normalize_poll_dict(dict(row)) for row in rows]
    
    async def update(
        self,
        poll_id: str,
        status: Optional[str] = None,
        telegram_poll_id: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        results: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None,
        closed_at: Optional[datetime] = None,
    ) -> bool:
        """
        Обновить данные опроса.
        
        Args:
            poll_id: ID опроса
            status: Новый статус (опционально)
            telegram_poll_id: Новый ID опроса в Telegram (опционально)
            telegram_message_id: Новый ID сообщения (опционально)
            results: Новые результаты (опционально)
            screenshot_path: Путь к скриншоту (опционально)
            closed_at: Время закрытия (опционально)
            
        Returns:
            True если обновление успешно, False если опрос не найден
        """
        updates = []
        params = []
        param_num = 1
        
        if status is not None:
            updates.append(f"status = ${param_num}")
            params.append(status)
            param_num += 1
        
        if telegram_poll_id is not None:
            updates.append(f"telegram_poll_id = ${param_num}")
            params.append(telegram_poll_id)
            param_num += 1
        
        if telegram_message_id is not None:
            updates.append(f"telegram_message_id = ${param_num}")
            params.append(telegram_message_id)
            param_num += 1
        
        if results is not None:
            updates.append(f"results = ${param_num}::jsonb")
            params.append(json.dumps(results))
            param_num += 1
        
        if screenshot_path is not None:
            updates.append(f"screenshot_path = ${param_num}")
            params.append(screenshot_path)
            param_num += 1
        
        if closed_at is not None:
            updates.append(f"closed_at = ${param_num}")
            params.append(closed_at)
            param_num += 1
        
        if not updates:
            return True  # Нет изменений
        
        params.append(poll_id)
        
        async with self.pool.acquire() as conn:
            query = f"""
                UPDATE daily_polls
                SET {', '.join(updates)}
                WHERE id = ${param_num}
            """
            result = await conn.execute(query, *params)
            
            return result == "UPDATE 1"
    
    async def close_poll(self, poll_id: str, closed_at: Optional[datetime] = None) -> bool:
        """
        Закрыть опрос.
        
        Args:
            poll_id: ID опроса
            closed_at: Время закрытия (если None - текущее время)
            
        Returns:
            True если закрытие успешно
        """
        if closed_at is None:
            closed_at = datetime.utcnow()
        
        return await self.update(poll_id, status="closed", closed_at=closed_at)

    async def mark_telegram_poll_obsolete(
        self,
        telegram_poll_id: str,
        group_id: Optional[int] = None,
        poll_date: Optional[date] = None,
        reason: str = "recreated",
    ) -> bool:
        """
        Сохранить старый telegram_poll_id как устаревший, чтобы поздние update'ы
        не считались ошибкой после пересоздания/удаления опроса.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO obsolete_telegram_polls (
                    telegram_poll_id, group_id, poll_date, reason
                )
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (telegram_poll_id) DO UPDATE
                SET group_id = EXCLUDED.group_id,
                    poll_date = EXCLUDED.poll_date,
                    reason = EXCLUDED.reason,
                    retired_at = NOW()
                """,
                telegram_poll_id,
                group_id,
                poll_date,
                reason,
            )
            return result in {"INSERT 0 1", "UPDATE 1"}

    async def is_telegram_poll_obsolete(self, telegram_poll_id: str) -> bool:
        """Проверить, помечен ли telegram_poll_id как устаревший."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM obsolete_telegram_polls
                WHERE telegram_poll_id = $1
                """,
                telegram_poll_id,
            )
            return row is not None

    async def replace_poll_options(
        self,
        poll_id: str,
        options: List[Dict[str, Any]],
    ) -> None:
        """
        Полностью пересоздать список вариантов для опроса в poll_options.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM poll_options WHERE poll_id = $1", poll_id)
                for index, option in enumerate(options):
                    await conn.execute(
                        """
                        INSERT INTO poll_options (
                            poll_id, option_index, option_text, slot_start, slot_end, max_users, current_count
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, 0)
                        """,
                        poll_id,
                        index,
                        option.get("option_text"),
                        option.get("slot_start"),
                        option.get("slot_end"),
                        option.get("max_users"),
                    )

    async def sync_user_vote(
        self,
        poll_id: str,
        user_id: int,
        user_name: Optional[str],
        full_name: Optional[str],
        option_indexes: List[int],
    ) -> None:
        """
        Обновить детальный учет голосов пользователя в user_votes.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM user_votes WHERE poll_id = $1 AND user_id = $2",
                    poll_id,
                    user_id,
                )

                for option_index in option_indexes:
                    option_row = await conn.fetchrow(
                        """
                        SELECT id
                        FROM poll_options
                        WHERE poll_id = $1 AND option_index = $2
                        """,
                        poll_id,
                        option_index,
                    )
                    if option_row is None:
                        continue

                    await conn.execute(
                        """
                        INSERT INTO user_votes (poll_id, option_id, user_id, user_name, full_name)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        poll_id,
                        option_row["id"],
                        user_id,
                        user_name,
                        full_name,
                    )

                await conn.execute(
                    """
                    UPDATE poll_options AS po
                    SET current_count = COALESCE(v.cnt, 0)
                    FROM (
                        SELECT option_id, COUNT(*)::int AS cnt
                        FROM user_votes
                        WHERE poll_id = $1
                        GROUP BY option_id
                    ) AS v
                    WHERE po.id = v.option_id
                    """,
                    poll_id,
                )
                await conn.execute(
                    """
                    UPDATE poll_options
                    SET current_count = 0
                    WHERE poll_id = $1
                      AND id NOT IN (
                          SELECT option_id
                          FROM user_votes
                          WHERE poll_id = $1
                      )
                    """,
                    poll_id,
                )

    async def claim_reminder_dispatch(
        self,
        poll_id: str,
        reminder_hour: int,
        is_night: bool,
    ) -> bool:
        """
        Атомарно забрать отправку напоминания в обработку.

        Возвращает True только для первого процесса/корутины.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO poll_reminder_dispatches (poll_id, reminder_hour, is_night)
                VALUES ($1, $2, $3)
                ON CONFLICT (poll_id, reminder_hour, is_night) DO NOTHING
                """,
                poll_id,
                reminder_hour,
                is_night,
            )
            return result == "INSERT 0 1"

    async def release_reminder_dispatch(
        self,
        poll_id: str,
        reminder_hour: int,
        is_night: bool,
    ) -> bool:
        """
        Освободить claim напоминания, если отправка сорвалась.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM poll_reminder_dispatches
                WHERE poll_id = $1 AND reminder_hour = $2 AND is_night = $3
                """,
                poll_id,
                reminder_hour,
                is_night,
            )
            return result == "DELETE 1"

    async def claim_for_closing(self, poll_id: str) -> bool:
        """
        Атомарно забрать активный опрос в обработку закрытия.

        Returns:
            True, если текущий процесс первым забрал опрос.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE daily_polls
                SET status = 'closing'
                WHERE id = $1 AND status = 'active'
                """,
                poll_id,
            )
            return result == "UPDATE 1"

    async def release_closing_claim(self, poll_id: str) -> bool:
        """
        Вернуть опрос из промежуточного статуса closing обратно в active.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE daily_polls
                SET status = 'active'
                WHERE id = $1 AND status = 'closing'
                """,
                poll_id,
            )
            return result == "UPDATE 1"

    async def reminder_already_sent(
        self,
        poll_id: str,
        reminder_hour: int,
        is_night: bool,
    ) -> bool:
        """Проверить, отправлялось ли уже автоматическое напоминание."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM poll_reminder_dispatches
                WHERE poll_id = $1 AND reminder_hour = $2 AND is_night = $3
                """,
                poll_id,
                reminder_hour,
                is_night,
            )
            return row is not None

    async def mark_reminder_sent(
        self,
        poll_id: str,
        reminder_hour: int,
        is_night: bool,
    ) -> bool:
        """Зафиксировать факт автоматической отправки напоминания."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                INSERT INTO poll_reminder_dispatches (poll_id, reminder_hour, is_night)
                VALUES ($1, $2, $3)
                ON CONFLICT (poll_id, reminder_hour, is_night) DO NOTHING
                """,
                poll_id,
                reminder_hour,
                is_night,
            )
            return result == "INSERT 0 1"

    async def delete(self, poll_id: str) -> bool:
        """Удалить опрос из БД."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM daily_polls WHERE id = $1",
                poll_id,
            )
            return result == "DELETE 1"

    async def delete_all_by_group(self, group_id: int) -> int:
        """Удалить все опросы группы из БД."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM daily_polls WHERE group_id = $1",
                group_id,
            )
            return int(result.split()[-1])
    
    async def get_statistics(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Получить статистику по опросам.
        
        Args:
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            Словарь со статистикой
        """
        async with self.pool.acquire() as conn:
            if start_date and end_date:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_polls,
                        COUNT(*) FILTER (WHERE status = 'active') as active_polls,
                        COUNT(*) FILTER (WHERE status = 'closed') as closed_polls
                    FROM daily_polls
                    WHERE poll_date BETWEEN $1 AND $2
                """, start_date, end_date)
            else:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_polls,
                        COUNT(*) FILTER (WHERE status = 'active') as active_polls,
                        COUNT(*) FILTER (WHERE status = 'closed') as closed_polls
                    FROM daily_polls
                """)
            
            return dict(stats) if stats else {
                "total_polls": 0,
                "active_polls": 0,
                "closed_polls": 0,
            }
