from sqlalchemy.orm import Session

from app.core.db.unit_of_work import UnitOfWork
from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.event_handlers.user_deactivated import (
    on_user_deactivated,
)
from app.services.orders.infrastructure.models import OrderRow
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.users import UserDeactivated


def test_user_deactivated_cancels_open_orders(engine, relay):
    with UnitOfWork(engine, relay) as uow:
        order = SqlOrderRepository(uow.session).add(
            Order(user_id=1, item="book")
        )
    with UnitOfWork(engine, relay) as uow:
        on_user_deactivated(UserDeactivated(user_id=1), uow)
    with Session(engine) as session:
        assert (
            session.get_one(OrderRow, order.id).status == OrderStatus.CANCELLED
        )
