---
title: "Layout by domain: events"
category: project-structure
tags:
  - project-layout
  - modular-monolith
  - domain-driven-design
  - domain-events
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1b-layout-by-domain]]"
  - "[[1b-layout-by-domain-calls]]"
  - "[[1b-layout-by-domain-core]]"
  - "[[1b-layout-by-domain-shared]]"
---

# Layout by domain: events

One service announces a fact, and other services react to it later in their own transaction. The publisher owns the event and never knows who listens; each subscriber decides what the fact means for its own domain.

## Fits when
- Another service should react, but the publisher doesn't need its answer: "when a user is deactivated, cancel their open orders".
- Several services react to the same fact.
- A service keeps a local copy of another service's data (user names next to orders) instead of calling it on every request.

Not when:
- The caller can't continue without an answer: use [[1b-layout-by-domain-calls]].
- Both sides are in the same service: call the code directly.

## Signals
- **Feature:** "when X happens, do Y in another domain", "notify", "keep in sync with".
- **Code:** a use case that calls several other services after its own write; two services calling each other; the publisher importing a subscriber.

## Pattern
The base type and the publisher `Protocol` live in `shared/events/`, so a service's domain can use them:

```python
# app/shared/events/base.py (fragment)
@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)


class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
```

The publisher defines the event in its domain and re-exports it from `__init__.py`:

```python
# app/services/users/domain/events.py (fragment)
@dataclass(frozen=True, kw_only=True)
class UserDeactivated(DomainEvent):
    user_id: int
```

```python
# app/services/users/__init__.py (fragment)
from app.services.users.domain.events import UserDeactivated
from app.services.users.public import UsersApi

__all__ = ["UserDeactivated", "UsersApi"]
```

The use case publishes after changing state. `publish` only records the event; `core/events/` dispatches it after the transaction commits:

```python
# app/services/users/use_cases/deactivate_user.py (fragment)
def deactivate_user(command: DeactivateUser, users: UserRepository, events: EventPublisher) -> None:
    user = users.get(command.user_id)
    user.deactivate()
    users.save(user)
    events.publish(UserDeactivated(user_id=user.id))
```

The subscriber's `event_handlers/` is an entry point like `api/`: it builds the implementations and calls a use case. Each handler gets its own session:

```python
# app/services/orders/event_handlers/user_deactivated.py (fragment)
from app.services import users


def on_user_deactivated(event: users.UserDeactivated, session: Session) -> None:
    cancel_open_orders(CancelOpenOrders(user_id=event.user_id), SqlOrderRepository(session))
```

```python
# app/services/orders/event_handlers/__init__.py (fragment)
def register(bus: EventBus) -> None:
    bus.subscribe(users.UserDeactivated, on_user_deactivated)
```

`main.py` calls each service's `register(bus)` at startup. Users never imports orders; adding another subscriber changes nothing in users.

## Rules
- **The publisher owns the event:** it lives in the publisher's `domain/events.py`, and subscribers import it only from the publisher's `__init__.py`.
- **Facts, in the past tense:** `UserDeactivated`, named in the publisher's terms; never an instruction to a subscriber.
- **Plain values only:** frozen dataclasses with IDs and the fields subscribers need; never entities or ORM models.
- **Dispatch after commit:** a handler never sees an event whose transaction rolled back.
- **Handlers run in their own transaction:** a failing handler doesn't undo the publisher's work, and the publisher doesn't wait for it.
- **In-process bus by default, outbox when losing an event is costly:** `core/outbox/` stores the event in the publisher's transaction and relays it at least once.
- **Handlers are idempotent:** the outbox can deliver an event twice; check by `event_id` or make the change safe to repeat.
- **Handlers hold no rules:** they call a use case of their own service, like `api/` does.
- **Change events by adding fields with defaults;** a changed meaning is a new event.
- **Tests:** the publisher's tests pass a fake `EventPublisher` and assert the recorded events; the subscriber's tests call the handler with an event directly.

## Anti-patterns
- **Commands dressed as events.** `CancelUserOrders` published by users means users knows orders' rules; publish the fact and let orders decide.
- **Dispatching before commit.** Handlers send emails or cancel orders for a change that was rolled back.
- **Thin events that force a call back.** A handler that calls the publisher for every field it needs couples them again; put those fields in the event.
- **Event ping-pong.** A → B → A chains are hard to follow and can loop; move the boundary instead.

## Related
- [[0-layout-guide]]
- [[1b-layout-by-domain]]
- [[1b-layout-by-domain-calls]]
- [[1b-layout-by-domain-core]]
- [[1b-layout-by-domain-shared]]
