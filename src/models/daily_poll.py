from datetime import datetime, date, time
from uuid import uuid4

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Integer,
    String,
    BigInteger,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID

from .database import Base


class DailyPoll(Base):
    __tablename__ = "daily_polls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    group_id = Column(Integer, nullable=False)
    poll_date = Column(Date, nullable=False)
    telegram_poll_id = Column(String(100))
    telegram_message_id = Column(BigInteger)
    telegram_topic_id = Column(Integer)
    status = Column(String(20), default="active")
    screenshot_path = Column(String)
    results = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)


