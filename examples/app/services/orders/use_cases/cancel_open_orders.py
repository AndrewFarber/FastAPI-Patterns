from dataclasses import dataclass

from app.services.orders.domain.entities import OrderStatus
from app.services.orders.domain.protocols import OrderRepository


@dataclass(frozen=True)
class CancelOpenOrdersCommand:
    user_id: int


def cancel_open_orders(
    command: CancelOpenOrdersCommand, order_repository: OrderRepository
) -> None:
    for order in order_repository.list_for_user(
        command.user_id, OrderStatus.OPEN
    ):
        order.cancel()
        order_repository.save(order)
