from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def get_or_create_user(
        self,
        user_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> User:
        """Получить пользователя или создать нового."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            user = await self.user_repo.create(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
            )
            await self.session.commit()
        return user

    async def verify_user(self, user_id: int, first_name: str, last_name: str) -> Optional[User]:
        """Верифицировать пользователя."""
        user = await self.user_repo.verify_user(user_id, first_name, last_name)
        if user:
            await self.session.commit()
        return user

    async def is_verified(self, user_id: int) -> bool:
        """Проверить, верифицирован ли пользователь."""
        user = await self.user_repo.get_by_id(user_id)
        return user.is_verified if user else False

