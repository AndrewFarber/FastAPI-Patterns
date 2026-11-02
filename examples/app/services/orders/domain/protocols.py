from typing import Protocol

from app.services.orders.domain.entities import Order


class OrderRepository(Protocol):
    def add(self, order: Order) -> Order: ...
    def open_for_user(self, user_id: int) -> list[Order]: ...
    def save(self, order: Order) -> None: ...


class UserDirectory(Protocol):
    def is_active(self, user_id: int) -> bool: ...


class OrderSwitches(Protocol):
    def ordering_paused(self) -> bool: ...
