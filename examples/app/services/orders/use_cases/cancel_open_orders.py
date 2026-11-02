from dataclasses import dataclass

from app.services.orders.domain.protocols import OrderRepository


@dataclass(frozen=True)
class CancelOpenOrders:
    user_id: int


def cancel_open_orders(
    command: CancelOpenOrders, orders: OrderRepository
) -> None:
    for order in orders.open_for_user(command.user_id):
        order.cancel()
        orders.save(order)
