---
title: "Services: calls"
category: project-structure
related:
  - "[[services-guide]]"
  - "[[settings-refreshing-values]]"
---

# Services: calls

## Overview
One service calls another in-process and waits for the answer. The caller defines what it needs as a `Protocol` in its own domain, the owner exposes a small public interface, and the caller's `api/` connects them. Neither imports the other's internals, and the call can later become an HTTP call without touching the caller's domain.

## Rules
- **Import only the owner's `__init__.py`:** never its `domain/`, `infrastructure/`, or `use_cases/`.
- **The caller owns the `Protocol`:** it lists only the methods the caller uses, named in the caller's terms.
- **Plain values or small DTOs across the boundary:** `bool`, IDs, or a `UserSummary`; never the owner's entities.
- **The owner decides:** the public method applies the owner's rules; the caller never recomputes them from raw fields.
- **Batch for lists:** fetch the page, then make one call with all its IDs (`users.get_names(user_ids)`), never one call per row.
- **One direction:** if two services call each other, use events for one direction or move the boundary.
- **Calls share the request's unit of work:** reads are fine; writes on both sides become one transaction, which is an exception to make deliberately, not by default.
- **A check the caller acts on holds until the caller commits:** `is_active` reads the user `FOR SHARE`, so a deactivation waits for the order to commit, and its `UserDeactivated` handler then sees and cancels it. Without the lock, a deactivation committed between the check and the insert leaves an open order for a deactivated user. A share lock blocks only writers to that row, never other readers.
- **Tests use a fake:** the caller's tests pass a fake `UserDirectory`; the owner tests its public interface itself.

## Code example
The caller states what it needs, in its own words, next to its repository `Protocol`s:

```python
# app/services/orders/domain/protocols.py
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
```

The owner exposes a public interface and re-exports it from `__init__.py`. The rule itself stays in its domain, and the read locks the row the answer depends on:

```python
# app/services/users/public.py
from sqlalchemy.orm import Session

from app.services.users.infrastructure.repositories import SqlUserRepository


class UsersService:
    def __init__(self, session: Session) -> None:
        self._user_repository = SqlUserRepository(session)

    def is_active(self, user_id: int) -> bool:
        # The share lock keeps the answer true until the caller commits:
        # a deactivation waits for the caller's transaction, so its
        # UserDeactivated handler sees what the caller wrote
        user = self._user_repository.get_for_share(user_id)
        return user is not None and user.is_active()
```

```python
# app/services/users/__init__.py
from app.services.users.domain.events import UserDeactivated
from app.services.users.public import UsersService

__all__ = ["UserDeactivated", "UsersService"]
```

The caller's `api/` builds the implementations from the request's unit of work, or from app state for the runtime switches ([[settings-refreshing-values]]), and passes them to the use case:

```python
# app/services/orders/api/dependencies.py
from typing import Annotated

from fastapi import Depends, Request

from app.core.dependencies.db import UnitOfWorkDep
from app.core.dependencies.settings import SettingsDep
from app.services import users
from app.services.orders.domain.protocols import (
    OrderRepository,
    OrderSwitches,
    UserDirectory,
)
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.infrastructure.switches import SsmOrderSwitches


def get_order_repository(unit_of_work: UnitOfWorkDep) -> OrderRepository:
    return SqlOrderRepository(unit_of_work.session)


def get_user_directory(unit_of_work: UnitOfWorkDep) -> UserDirectory:
    return users.UsersService(unit_of_work.session)


def get_order_switches(
    request: Request, settings: SettingsDep
) -> OrderSwitches:
    return SsmOrderSwitches(
        request.app.state.parameters, settings.switches.orders_paused
    )


OrderRepositoryDep = Annotated[OrderRepository, Depends(get_order_repository)]
UserDirectoryDep = Annotated[UserDirectory, Depends(get_user_directory)]
OrderSwitchesDep = Annotated[OrderSwitches, Depends(get_order_switches)]
```

```python
# app/services/orders/use_cases/place_order.py
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
```

`UsersService` never imports orders; it satisfies `UserDirectory` by having a matching method. If users moves to its own deployment, an `HttpUserDirectory` with the same method replaces it in `get_user_directory`, and nothing else in orders changes.
