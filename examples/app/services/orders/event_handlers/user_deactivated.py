from app.core.db.unit_of_work import UnitOfWork
from app.services import users
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.use_cases.cancel_open_orders import (
    CancelOpenOrders,
    cancel_open_orders,
)


def on_user_deactivated(event: users.UserDeactivated, uow: UnitOfWork) -> None:
    cancel_open_orders(
        CancelOpenOrders(user_id=event.user_id), SqlOrderRepository(uow.session)
    )
