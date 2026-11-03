from app.services.orders.domain.entities import Order, OrderStatus


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[int, Order] = {}

    def add(self, order: Order) -> Order:
        order.id = len(self.orders) + 1
        self.orders[order.id] = order
        return order

    def list_for_user(
        self, user_id: int, status: OrderStatus | None = None
    ) -> list[Order]:
        return [
            order
            for order in self.orders.values()
            if order.user_id == user_id
            and (status is None or order.status is status)
        ]

    def save(self, order: Order) -> None:
        self.orders[order.id] = order


class FakeUserDirectory:
    def __init__(self, *active: int) -> None:
        self.active = set(active)

    def is_active(self, user_id: int) -> bool:
        return user_id in self.active


class FakeOrderSwitches:
    def __init__(self, paused: bool = False) -> None:
        self.paused = paused

    def is_ordering_paused(self) -> bool:
        return self.paused
