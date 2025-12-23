import logging
from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.user_vote import UserVote

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, first_name: Optional[str] = None, 
                     last_name: Optional[str] = None, username: Optional[str] = None) -> User:
        """Создать нового пользователя."""
        user = User(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            is_verified=False,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить данные пользователя."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        await self.session.flush()
        return user

    async def verify_user(self, user_id: int, first_name: str, last_name: str) -> Optional[User]:
        """Верифицировать пользователя."""
        return await self.update(
            user_id,
            first_name=first_name,
            last_name=last_name,
            is_verified=True,
        )

    async def get_verified_users(self) -> List[User]:
        """Получить всех верифицированных пользователей."""
        from sqlalchemy import select
        result = await self.session.execute(
            select(User).where(User.is_verified == True)  # noqa: E712
        )
        return list(result.scalars().all())
    
    async def get_unverified_users(self) -> List[User]:
        """Получить всех неверифицированных пользователей."""
        result = await self.session.execute(
            select(User).where(User.is_verified == False).order_by(User.id)  # noqa: E712
        )
        return list(result.scalars().all())
    
    async def get_by_ids(self, user_ids: List[int]) -> List[User]:
        """Получить пользователей по списку ID (оптимизация для батчей)."""
        if not user_ids:
            return []
        result = await self.session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        return list(result.scalars().all())
    
    async def verify_users_batch(self, user_ids: List[int]) -> int:
        """Массовая верификация пользователей."""
        if not user_ids:
            return 0
        
        result = await self.session.execute(
            select(User).where(
                User.id.in_(user_ids),
                User.is_verified == False  # noqa: E712
            )
        )
        users = result.scalars().all()
        
        verified_count = 0
        for user in users:
            # Если у пользователя нет имени или фамилии, используем доступные данные
            if not user.first_name and not user.last_name:
                # Используем username или ID как имя
                display_name = user.username or f"User {user.id}"
                user.first_name = display_name
                user.last_name = ""
            elif not user.first_name:
                user.first_name = user.last_name or (user.username or f"User {user.id}")
            elif not user.last_name:
                user.last_name = user.first_name
            
            user.is_verified = True
            verified_count += 1
        
        await self.session.flush()
        return verified_count

    async def delete(self, user_id: int) -> bool:
        """Удалить пользователя и все его голоса."""
        try:
            # Проверяем, существует ли пользователь
            user = await self.get_by_id(user_id)
            if not user:
                logger.warning("Attempted to delete non-existent user %s", user_id)
                return False
            
            # Сначала удаляем все голоса пользователя
            votes_deleted = await self.session.execute(
                delete(UserVote).where(UserVote.user_id == user_id)
            )
            votes_count = votes_deleted.rowcount
            logger.info("Deleted %d votes for user %s", votes_count, user_id)
            
            # Затем удаляем самого пользователя
            await self.session.delete(user)
            await self.session.flush()
            
            logger.info("Successfully deleted user %s (%s)", user_id, user.get_full_name())
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Error deleting user %s: %s", user_id, e, exc_info=True)
            return False

