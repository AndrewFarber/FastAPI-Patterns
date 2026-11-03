from services.orders.fakes import FakeOrderRepository

from app.services.orders.domain.entities import Order, OrderStatus
from app.services.orders.use_cases.cancel_open_orders import (
    CancelOpenOrdersCommand,
    cancel_open_orders,
)


def test_cancel_open_orders_is_safe_to_repeat():
    order_repository = FakeOrderRepository()
    order_repository.add(Order(user_id=1, item="a"))
    order_repository.add(Order(user_id=2, item="b"))
    for _ in range(2):
        cancel_open_orders(CancelOpenOrdersCommand(user_id=1), order_repository)
    assert [o.status for o in order_repository.orders.values()] == [
        OrderStatus.CANCELLED,
        OrderStatus.OPEN,
    ]
