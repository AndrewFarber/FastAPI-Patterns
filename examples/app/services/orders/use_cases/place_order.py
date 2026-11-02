from dataclasses import dataclass

from app.services.orders.domain.entities import Order
from app.services.orders.domain.errors import UserNotActive
from app.services.orders.domain.protocols import OrderRepository, UserDirectory


@dataclass(frozen=True)
class PlaceOrder:
    user_id: int
    item: str


def place_order(command: PlaceOrder, orders: OrderRepository, users: UserDirectory) -> Order:
    if not users.is_active(command.user_id):
        raise UserNotActive(command.user_id)
    return orders.add(Order(user_id=command.user_id, item=command.item))
