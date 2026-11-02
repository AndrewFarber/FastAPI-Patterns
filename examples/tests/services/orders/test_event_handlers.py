from sqlalchemy.orm import Session

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.event_handlers.user_deactivated import on_user_deactivated
from app.services.orders.infrastructure.models import OrderRow
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.users import UserDeactivated


def test_user_deactivated_cancels_open_orders(engine):
    with Session(engine) as session, session.begin():
        order = SqlOrderRepository(session).add(Order(user_id=1, item="book"))
    with Session(engine) as session, session.begin():
        on_user_deactivated(UserDeactivated(user_id=1), session)
    with Session(engine) as session:
        assert session.get_one(OrderRow, order.id).status == OrderStatus.CANCELLED
