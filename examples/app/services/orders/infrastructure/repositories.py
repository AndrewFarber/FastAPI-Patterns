from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.domain.errors import OrderChanged
from app.services.orders.infrastructure.models import OrderRow


def to_entity(row: OrderRow) -> Order:
    return Order(id=row.id, user_id=row.user_id, item=row.item, status=OrderStatus(row.status), version=row.version)


class SqlOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: Order) -> Order:
        row = OrderRow(user_id=order.user_id, item=order.item, status=order.status)
        self._session.add(row)
        self._session.flush()
        order.id, order.version = row.id, row.version
        return order

    def open_for_user(self, user_id: int) -> list[Order]:
        rows = self._session.scalars(select(OrderRow).where(OrderRow.user_id == user_id, OrderRow.status == OrderStatus.OPEN))
        return [to_entity(row) for row in rows]

    def save(self, order: Order) -> None:
        result = self._session.execute(
            update(OrderRow)
            .where(OrderRow.id == order.id, OrderRow.version == order.version)
            .values(item=order.item, status=order.status, version=order.version + 1)
        )
        if result.rowcount != 1:
            raise OrderChanged(order.id)
        order.version += 1
