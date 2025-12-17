"""Репозиторий для работы с администраторами."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
import logging

logger = logging.getLogger(__name__)


class Administrator:
    """Простая модель администратора для работы с БД."""

    def __init__(self, user_id: int, username: Optional[str] = None, is_super_admin: bool = False):
        self.user_id = user_id
        self.username = username
        self.is_super_admin = is_super_admin


class AdminRepository:
    """Репозиторий для работы с администраторами."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update(
        self,
        user_id: int,
        username: Optional[str] = None,
        is_super_admin: bool = False,
    ) -> None:
        """Создать или обновить администратора."""
        try:
            # Проверяем существование
            result = await self.session.execute(
                select("administrators").where(
                    "administrators.user_id == :user_id"
                ).params(user_id=user_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Обновляем
                await self.session.execute(
                    """
                    UPDATE administrators
                    SET username = :username, is_super_admin = :is_super_admin
                    WHERE user_id = :user_id
                    """,
                    {
                        "username": username,
                        "is_super_admin": is_super_admin,
                        "user_id": user_id,
                    },
                )
            else:
                # Создаем
                await self.session.execute(
                    """
                    INSERT INTO administrators (user_id, username, is_super_admin)
                    VALUES (:user_id, :username, :is_super_admin)
                    """,
                    {
                        "user_id": user_id,
                        "username": username,
                        "is_super_admin": is_super_admin,
                    },
                )

            await self.session.commit()
            logger.info(f"Admin {user_id} created/updated")

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating/updating admin {user_id}: {e}")
            raise

