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
        """Получить пользователя или создать нового. Обновляет данные, если пользователь уже существует."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            user = await self.user_repo.create(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
            )
            # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        else:
            # Для верифицированных пользователей не обновляем имена автоматически
            # (они были установлены вручную и не должны перезаписываться данными из Telegram)
            if not user.is_verified:
                # Обновляем данные пользователя, если они изменились (только для неверифицированных)
                updated = False
                if first_name is not None and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if last_name is not None and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                if username is not None and user.username != username:
                    user.username = username
                    updated = True
            else:
                # Для верифицированных пользователей обновляем только username (если изменился)
                # Имена (first_name, last_name) не обновляем, так как они были установлены вручную
                if username is not None and user.username != username:
                    user.username = username
            # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        return user

    async def verify_user(self, user_id: int, first_name: str, last_name: str) -> Optional[User]:
        """Верифицировать пользователя."""
        user = await self.user_repo.verify_user(user_id, first_name, last_name)
        # DatabaseMiddleware автоматически сделает commit после успешного выполнения handler
        return user

    async def is_verified(self, user_id: int) -> bool:
        """Проверить, верифицирован ли пользователь."""
        user = await self.user_repo.get_by_id(user_id)
        return user.is_verified if user else False

