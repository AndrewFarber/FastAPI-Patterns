from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class OrderRow(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "orders"}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    item: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
