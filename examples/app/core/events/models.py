from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class ProcessedEventRow(Base):
    __tablename__ = "processed"
    __table_args__ = {"schema": "events"}

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    consumer: Mapped[str] = mapped_column(String(100), primary_key=True)
