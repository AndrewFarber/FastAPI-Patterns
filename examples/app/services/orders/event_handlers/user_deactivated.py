from sqlalchemy.orm import Session

from app.services import users
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.use_cases.cancel_open_orders import CancelOpenOrders, cancel_open_orders


def on_user_deactivated(event: users.UserDeactivated, session: Session) -> None:
    cancel_open_orders(CancelOpenOrders(user_id=event.user_id), SqlOrderRepository(session))
