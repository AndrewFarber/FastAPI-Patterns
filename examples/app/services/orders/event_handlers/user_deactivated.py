from app.core.db.unit_of_work import UnitOfWork
from app.services import users
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.use_cases.cancel_open_orders import (
    CancelOpenOrdersCommand,
    cancel_open_orders,
)


def handle_user_deactivated(
    event: users.UserDeactivated, unit_of_work: UnitOfWork
) -> None:
    cancel_open_orders(
        CancelOpenOrdersCommand(user_id=event.user_id),
        SqlOrderRepository(unit_of_work.session),
    )
