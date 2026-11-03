from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.domain.errors import OrderChangedError
from app.services.orders.infrastructure.models import DbOrder


def to_entity(row: DbOrder) -> Order:
    return Order(
        id=row.id,
        user_id=row.user_id,
        item=row.item,
        status=OrderStatus(row.status),
        version=row.version,
    )


class SqlOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: Order) -> Order:
        row = DbOrder(
            user_id=order.user_id, item=order.item, status=order.status
        )
        self._session.add(row)
        self._session.flush()
        order.id, order.version = row.id, row.version
        return order

    def list_for_user(
        self, user_id: int, status: OrderStatus | None = None
    ) -> list[Order]:
        query = select(DbOrder).where(DbOrder.user_id == user_id)
        if status is not None:
            query = query.where(DbOrder.status == status)
        rows = self._session.scalars(query)
        return [to_entity(row) for row in rows]

    def save(self, order: Order) -> None:
        result = self._session.execute(
            update(DbOrder)
            .where(DbOrder.id == order.id, DbOrder.version == order.version)
            .values(
                item=order.item, status=order.status, version=order.version + 1
            )
        )
        if result.rowcount != 1:
            raise OrderChangedError(order.id)
        order.version += 1
