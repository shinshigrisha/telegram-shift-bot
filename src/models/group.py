from datetime import datetime, time

from sqlalchemy import Boolean, BigInteger, Column, Integer, String, Time, JSON, DateTime
from sqlalchemy.sql import func

from .database import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=False)
    telegram_topic_id = Column(Integer, nullable=True)  # ID темы для форум-групп
    is_night = Column(Boolean, default=False)
    poll_close_time = Column(
        Time,
        default=datetime.strptime("19:00", "%H:%M").time(),  # type: ignore[arg-type]
    )
    settings = Column(
        JSON,
        nullable=False,
        default={"slots": [], "max_users_per_slot": 3},
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def get_slots_config(self) -> list:
        """Вернуть конфигурацию слотов из JSON-настроек."""
        return (self.settings or {}).get("slots", [])

    def update_slots(self, slots: list) -> None:
        """Обновить конфигурацию слотов в JSON-настройках."""
        data = dict(self.settings or {})
        data["slots"] = slots
        self.settings = data


