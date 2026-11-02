from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "users"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(default=1)
