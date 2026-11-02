from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.infrastructure.models import OrderRow


def to_entity(row: OrderRow) -> Order:
    return Order(id=row.id, user_id=row.user_id, item=row.item, status=OrderStatus(row.status))


class SqlOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: Order) -> Order:
        row = OrderRow(user_id=order.user_id, item=order.item, status=order.status)
        self._session.add(row)
        self._session.flush()
        order.id = row.id
        return order

    def open_for_user(self, user_id: int) -> list[Order]:
        rows = self._session.scalars(select(OrderRow).where(OrderRow.user_id == user_id, OrderRow.status == OrderStatus.OPEN))
        return [to_entity(row) for row in rows]

    def save(self, order: Order) -> None:
        row = self._session.get_one(OrderRow, order.id)
        row.item, row.status = order.item, order.status
