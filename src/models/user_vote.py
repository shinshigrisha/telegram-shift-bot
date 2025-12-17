from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    BigInteger,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID

from .database import Base


class UserVote(Base):
    __tablename__ = "user_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    poll_id = Column("poll_id", nullable=False)
    user_id = Column(BigInteger, nullable=False)
    user_name = Column(String(100))
    slot_id = Column(Integer)
    voted_option = Column(String(50))
    voted_at = Column(DateTime, default=datetime.utcnow)


