from typing import Optional

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

