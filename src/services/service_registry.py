"""
Реестр глобальных сервисов для доступа из handlers.

Избегает циклических импортов и проблем с bot.get().
"""
from typing import Optional

from src.services.scheduler_service import SchedulerService
from src.services.poll_service import PollService

# Глобальные переменные для сервисов
scheduler_service: Optional[SchedulerService] = None
poll_service: Optional[PollService] = None


def set_scheduler_service(service: SchedulerService) -> None:
    """Установить глобальный scheduler_service."""
    global scheduler_service
    scheduler_service = service


def set_poll_service(service: PollService) -> None:
    """Установить глобальный poll_service."""
    global poll_service
    poll_service = service


def get_scheduler_service() -> Optional[SchedulerService]:
    """Получить глобальный scheduler_service."""
    return scheduler_service


def get_poll_service() -> Optional[PollService]:
    """Получить глобальный poll_service."""
    return poll_service
