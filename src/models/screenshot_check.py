from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func

from .database import Base


class ScreenshotCheck(Base):
    """Модель для отслеживания времени последнего скриншота в теме 'приход/уход'."""
    __tablename__ = "screenshot_checks"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, unique=True)
    last_screenshot_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

