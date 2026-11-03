---
title: "Naming: domain"
category: conventions
related:
  - "[[naming-guide]]"
  - "[[naming]]"
  - "[[layout]]"
  - "[[services-events]]"
---

# Naming: domain

## Overview
Names inside a service's `domain/` and `use_cases/` ([[layout]]), building on [[naming]]. The domain's names are the business's words, and the name's form tells an entity, a command, an event, and an error apart: `Order`, `PlaceOrderCommand`, `UserDeactivated`, `OrderChangedError`.

## Rules
- **Entities and value objects are singular nouns** in the business's words: `Order`, `User`, `Money`. Their status enums are `<Entity>Status`.
- **Events are facts in the past tense,** `<Subject><PastVerb>`: `UserDeactivated`. No `Event` suffix; the class name is the wire name ([[services-events]]).
- **Errors end in `Error`** and name the condition: `UserNotFoundError`, `OrderingPausedError`, `OrderChangedError`. Each subclasses a base from `shared/errors/` (`NotFoundError`, `RuleViolationError`, `ConflictError`), which picks the HTTP status. The class name is the `error` field of the response, so a rename changes the API.
- **Protocols name a role in the caller's words:** `OrderRepository`, `UserDirectory`, `OrderSwitches`, `EventPublisher`. No `I` prefix, no `Protocol` suffix.
- **Protocol methods are verbs:** `get`, `add`, `save`, `list_for_user`; a lock or variant is a qualifier, `get_for_share`.
- **Implementations put their technology first,** in a short word: `SqlOrderRepository`, `SsmOrderSwitches`, `SnsMessageSender`, `OutboxEventPublisher`.
- **Use cases:** the file and function are `<verb>_<noun>` (`place_order.py`, `place_order()`), and their input is a frozen `<Verb><Noun>Command` (`PlaceOrderCommand`). An imperative command and a past-tense event never collide: `DeactivateUserCommand` asks, `UserDeactivated` reports.

## Code example
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

```python
# app/shared/errors/base.py
class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class RuleViolationError(DomainError):
    pass


class ConflictError(DomainError):
    pass
```
