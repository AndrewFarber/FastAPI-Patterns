import pytest

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.domain.errors import UserNotActive
from app.services.orders.use_cases.cancel_open_orders import CancelOpenOrders, cancel_open_orders
from app.services.orders.use_cases.place_order import PlaceOrder, place_order


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[int, Order] = {}

    def add(self, order: Order) -> Order:
        order.id = len(self.orders) + 1
        self.orders[order.id] = order
        return order

    def open_for_user(self, user_id: int) -> list[Order]:
        return [o for o in self.orders.values() if o.user_id == user_id and o.status is OrderStatus.OPEN]

    def save(self, order: Order) -> None:
        self.orders[order.id] = order


class FakeUserDirectory:
    def __init__(self, *active: int) -> None:
        self.active = set(active)

    def is_active(self, user_id: int) -> bool:
        return user_id in self.active


def test_place_order_for_active_user():
    order = place_order(PlaceOrder(user_id=1, item="book"), FakeOrderRepository(), FakeUserDirectory(1))
    assert order.id == 1 and order.status is OrderStatus.OPEN


def test_place_order_asks_users_not_its_own_copy():
    with pytest.raises(UserNotActive):
        place_order(PlaceOrder(user_id=2, item="book"), FakeOrderRepository(), FakeUserDirectory(1))


def test_cancel_open_orders_is_safe_to_repeat():
    orders = FakeOrderRepository()
    orders.add(Order(user_id=1, item="a"))
    orders.add(Order(user_id=2, item="b"))
    for _ in range(2):
        cancel_open_orders(CancelOpenOrders(user_id=1), orders)
    assert [o.status for o in orders.orders.values()] == [OrderStatus.CANCELLED, OrderStatus.OPEN]
