"""
Утилиты для работы с базой данных.
Предоставляют удобные функции для получения репозиториев и сервисов из контекста middleware.
"""
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.group_repository import GroupRepository
from src.repositories.poll_repository import PollRepository
from src.repositories.user_repository import UserRepository
from src.services.group_service import GroupService
from src.services.user_service import UserService
from src.services.poll_service import PollService


def get_db_session(data: Dict[str, Any]) -> Optional[AsyncSession]:
    """
    Получить сессию БД из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        AsyncSession если доступна, None иначе
    """
    return data.get("db_session")


def get_group_repo(data: Dict[str, Any]) -> Optional[GroupRepository]:
    """
    Получить GroupRepository из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        GroupRepository если доступен, None иначе
    """
    return data.get("group_repo")


def get_poll_repo(data: Dict[str, Any]) -> Optional[PollRepository]:
    """
    Получить PollRepository из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        PollRepository если доступен, None иначе
    """
    return data.get("poll_repo")


def get_user_repo(data: Dict[str, Any]) -> Optional[UserRepository]:
    """
    Получить UserRepository из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        UserRepository если доступен, None иначе
    """
    return data.get("user_repo")


def get_group_service(data: Dict[str, Any]) -> Optional[GroupService]:
    """
    Получить GroupService из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        GroupService если доступен, None иначе
    """
    return data.get("group_service")


def get_user_service(data: Dict[str, Any]) -> Optional[UserService]:
    """
    Получить UserService из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        UserService если доступен, None иначе
    """
    return data.get("user_service")


def get_poll_service(data: Dict[str, Any]) -> Optional[PollService]:
    """
    Получить PollService из контекста middleware.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        PollService если доступен, None иначе
    """
    return data.get("poll_service")


def require_db_session(data: Dict[str, Any]) -> AsyncSession:
    """
    Получить сессию БД из контекста или создать новую при необходимости.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        AsyncSession
        
    Raises:
        RuntimeError: Если сессия недоступна и не может быть создана
    """
    session = get_db_session(data)
    if session:
        return session
    
    # Если сессия не доступна через middleware, создаем новую
    # Это может быть нужно для некоторых edge cases
    from src.models.database import AsyncSessionLocal
    return AsyncSessionLocal()


def require_repositories(data: Dict[str, Any]) -> tuple[GroupRepository, PollRepository, UserRepository]:
    """
    Получить все репозитории из контекста или создать новые при необходимости.
    
    Args:
        data: Словарь данных из middleware
        
    Returns:
        Кортеж (GroupRepository, PollRepository, UserRepository)
    """
    group_repo = get_group_repo(data)
    poll_repo = get_poll_repo(data)
    user_repo = get_user_repo(data)
    
    if group_repo and poll_repo and user_repo:
        return group_repo, poll_repo, user_repo
    
    # Если репозитории не доступны через middleware, создаем новые
    session = require_db_session(data)
    return (
        GroupRepository(session),
        PollRepository(session),
        UserRepository(session),
    )


