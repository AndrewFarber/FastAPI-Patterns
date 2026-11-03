from dataclasses import dataclass

from app.services.orders.domain.entities import Order
from app.services.orders.domain.errors import (
    OrderingPausedError,
    UserNotActiveError,
)
from app.services.orders.domain.protocols import (
    OrderRepository,
    OrderSwitches,
    UserDirectory,
)


@dataclass(frozen=True)
class PlaceOrderCommand:
    user_id: int
    item: str


def place_order(
    command: PlaceOrderCommand,
    order_repository: OrderRepository,
    user_directory: UserDirectory,
    order_switches: OrderSwitches,
) -> Order:
    if order_switches.is_ordering_paused():
        raise OrderingPausedError()
    if not user_directory.is_active(command.user_id):
        raise UserNotActiveError(command.user_id)
    return order_repository.add(
        Order(user_id=command.user_id, item=command.item)
    )
