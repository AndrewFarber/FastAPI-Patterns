import pytest
from services.orders.fakes import (
    FakeOrderRepository,
    FakeOrderSwitches,
    FakeUserDirectory,
)

from app.services.orders.domain.entities import OrderStatus
from app.services.orders.domain.errors import (
    OrderingPausedError,
    UserNotActiveError,
)
from app.services.orders.use_cases.place_order import (
    PlaceOrderCommand,
    place_order,
)


def test_place_order_for_active_user():
    order = place_order(
        PlaceOrderCommand(user_id=1, item="book"),
        FakeOrderRepository(),
        FakeUserDirectory(1),
        FakeOrderSwitches(),
    )
    assert order.id == 1 and order.status is OrderStatus.OPEN


def test_place_order_asks_users_not_its_own_copy():
    with pytest.raises(UserNotActiveError):
        place_order(
            PlaceOrderCommand(user_id=2, item="book"),
            FakeOrderRepository(),
            FakeUserDirectory(1),
            FakeOrderSwitches(),
        )


def test_place_order_while_paused_is_refused():
    with pytest.raises(OrderingPausedError):
        place_order(
            PlaceOrderCommand(user_id=1, item="book"),
            FakeOrderRepository(),
            FakeUserDirectory(1),
            FakeOrderSwitches(paused=True),
        )
