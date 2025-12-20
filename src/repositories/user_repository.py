from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User


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
    
    async def get_by_ids(self, user_ids: List[int]) -> List[User]:
        """Получить пользователей по списку ID (оптимизация для батчей)."""
        if not user_ids:
            return []
        result = await self.session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        return list(result.scalars().all())

