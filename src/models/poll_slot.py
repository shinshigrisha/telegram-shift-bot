from datetime import time

from sqlalchemy import (
    Column,
    Integer,
    Time,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID

from .database import Base


class PollSlot(Base):
    __tablename__ = "poll_slots"

    id = Column(Integer, primary_key=True)
    poll_id = Column(UUID(as_uuid=True), nullable=False)
    slot_number = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    max_users = Column(Integer, default=3)
    current_users = Column(Integer, default=0)
    user_ids = Column(JSON, default=[])


