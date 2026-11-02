from dataclasses import dataclass
from enum import StrEnum


class OrderStatus(StrEnum):
    OPEN = "open"
    CANCELLED = "cancelled"


@dataclass
class Order:
    user_id: int
    item: str
    status: OrderStatus = OrderStatus.OPEN
    id: int | None = None
    version: int = 0

    def cancel(self) -> None:
        self.status = OrderStatus.CANCELLED
