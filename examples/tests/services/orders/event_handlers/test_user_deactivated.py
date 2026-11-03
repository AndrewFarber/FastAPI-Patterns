from sqlalchemy.orm import Session

from app.core.db.unit_of_work import UnitOfWork
from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.event_handlers.user_deactivated import (
    handle_user_deactivated,
)
from app.services.orders.infrastructure.models import DbOrder
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.users import UserDeactivated


def test_user_deactivated_cancels_open_orders(engine, relay):
    with UnitOfWork(engine, relay) as unit_of_work:
        order = SqlOrderRepository(unit_of_work.session).add(
            Order(user_id=1, item="book")
        )
    with UnitOfWork(engine, relay) as unit_of_work:
        handle_user_deactivated(UserDeactivated(user_id=1), unit_of_work)
    with Session(engine) as session:
        assert (
            session.get_one(DbOrder, order.id).status == OrderStatus.CANCELLED
        )
