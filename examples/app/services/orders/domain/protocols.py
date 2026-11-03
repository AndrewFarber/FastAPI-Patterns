from typing import Protocol

from app.services.orders.domain.entities import Order, OrderStatus


class OrderRepository(Protocol):
    def add(self, order: Order) -> Order: ...
    def list_for_user(
        self, user_id: int, status: OrderStatus | None = None
    ) -> list[Order]: ...
    def save(self, order: Order) -> None: ...


class UserDirectory(Protocol):
    def is_active(self, user_id: int) -> bool: ...


class OrderSwitches(Protocol):
    def is_ordering_paused(self) -> bool: ...
