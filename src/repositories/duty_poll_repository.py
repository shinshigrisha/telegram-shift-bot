"""Хранение настройки и отправок ежедневного опроса дежурных."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from asyncpg import Pool


class DutyPollRepository:
    """Репозиторий отдельной автоматизации темы «Дежурные»."""

    def __init__(self, pool: Pool):
        self.pool = pool

    async def enable(self, chat_id: int, message_thread_id: int) -> Dict[str, Any]:
        """Включить автоматизацию для указанной темы."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO duty_poll_configs (
                    telegram_chat_id, message_thread_id, is_active
                )
                VALUES ($1, $2, TRUE)
                ON CONFLICT (telegram_chat_id, message_thread_id)
                DO UPDATE SET is_active = TRUE, updated_at = NOW()
                RETURNING *
                """,
                chat_id,
                message_thread_id,
            )
            return dict(row)

    async def disable(self, chat_id: int, message_thread_id: int) -> bool:
        """Отключить автоматизацию для указанной темы."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE duty_poll_configs
                SET is_active = FALSE, updated_at = NOW()
                WHERE telegram_chat_id = $1 AND message_thread_id = $2
                """,
                chat_id,
                message_thread_id,
            )
            return result == "UPDATE 1"

    async def get_config(
        self,
        chat_id: int,
        message_thread_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Получить настройку темы."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM duty_poll_configs
                WHERE telegram_chat_id = $1 AND message_thread_id = $2
                """,
                chat_id,
                message_thread_id,
            )
            return dict(row) if row else None

    async def get_active_configs(self) -> List[Dict[str, Any]]:
        """Получить все включённые темы дежурных."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM duty_poll_configs WHERE is_active = TRUE ORDER BY id"
            )
            return [dict(row) for row in rows]

    async def claim_dispatch(self, config_id: int, poll_date: date) -> bool:
        """Зарезервировать единственную отправку темы на дату."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO duty_poll_dispatches (config_id, poll_date)
                VALUES ($1, $2)
                ON CONFLICT (config_id, poll_date) DO NOTHING
                RETURNING id
                """,
                config_id,
                poll_date,
            )
            return row is not None

    async def mark_sent(
        self,
        config_id: int,
        poll_date: date,
        telegram_poll_id: str,
        telegram_message_id: int,
    ) -> None:
        """Сохранить идентификаторы опубликованного опроса."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE duty_poll_dispatches
                SET telegram_poll_id = $3,
                    telegram_message_id = $4,
                    status = 'active'
                WHERE config_id = $1 AND poll_date = $2
                """,
                config_id,
                poll_date,
                telegram_poll_id,
                telegram_message_id,
            )

    async def release_dispatch(self, config_id: int, poll_date: date) -> None:
        """Освободить резерв после неудачной отправки Telegram."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM duty_poll_dispatches
                WHERE config_id = $1 AND poll_date = $2 AND status = 'sending'
                """,
                config_id,
                poll_date,
            )

    async def get_expired_active(self, before_date: date) -> List[Dict[str, Any]]:
        """Получить опросы прошлых дней, которые ещё не закрыты."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT d.*, c.telegram_chat_id, c.message_thread_id
                FROM duty_poll_dispatches d
                JOIN duty_poll_configs c ON c.id = d.config_id
                WHERE d.status = 'active'
                  AND d.poll_date < $1
                  AND d.telegram_message_id IS NOT NULL
                ORDER BY d.poll_date, d.id
                """,
                before_date,
            )
            return [dict(row) for row in rows]

    async def mark_closed(self, dispatch_id: int, closed_at: datetime) -> None:
        """Отметить опрос закрытым."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE duty_poll_dispatches
                SET status = 'closed', closed_at = $2
                WHERE id = $1
                """,
                dispatch_id,
                closed_at,
            )
