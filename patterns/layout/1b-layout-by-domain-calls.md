---
title: "Layout by domain: calls"
category: project-structure
tags:
  - project-layout
  - modular-monolith
  - domain-driven-design
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1b-layout-by-domain]]"
  - "[[1b-layout-by-domain-events]]"
---

# Layout by domain: calls

One service calls another in-process and waits for the answer. The caller defines what it needs as a `Protocol` in its own domain, the owner exposes a small public interface, and the caller's `api/` connects them. Neither imports the other's internals, and the call can later become an HTTP call without touching the caller's domain.

## Fits when
- A use case can't continue without an answer from another service: "is the user active?", "reserve this stock".

Not when:
- The other service can act a moment later: publish a domain event instead ([[1b-layout-by-domain-events]]).

## Signals
- **Feature:** "only if the user is active", "check X in another domain before doing Y".
- **Code:** `from app.services.users.infrastructure` or `.domain` inside another service; another service's entities passed around; one service's tables read by another service's repository.

## Pattern
The caller states what it needs, in its own words, next to its repository `Protocol`s:

```python
# app/services/orders/domain/protocols.py (fragment)
class UserDirectory(Protocol):
    def is_active(self, user_id: int) -> bool: ...
```

The owner exposes a public interface and re-exports it from `__init__.py`. The rule itself stays in its domain:

```python
# app/services/users/public.py (fragment)
class UsersApi:
    def __init__(self, session: Session) -> None:
        self._users = SqlUserRepository(session)

    def is_active(self, user_id: int) -> bool:
        user = self._users.get(user_id)
        return user is not None and user.is_active()
```

```python
# app/services/users/__init__.py (fragment)
from app.services.users.public import UsersApi

__all__ = ["UsersApi"]
```

The caller's `api/` builds the implementation and passes it to the use case:

```python
# app/services/orders/api/dependencies.py (fragment)
from app.services import users


def get_user_directory(session: SessionDep) -> UserDirectory:
    return users.UsersApi(session)
```

```python
# app/services/orders/use_cases/place_order.py (fragment)
def place_order(command: PlaceOrder, orders: OrderRepository, users: UserDirectory) -> Order:
    if not users.is_active(command.user_id):
        raise UserNotActive(command.user_id)
    ...
```

`UsersApi` never imports orders; it satisfies `UserDirectory` by having a matching method. If users moves to its own deployment, an `HttpUserDirectory` with the same method replaces it in `get_user_directory`, and nothing else in orders changes.

## Rules
- **Import only the owner's `__init__.py`:** never its `domain/`, `infrastructure/`, or `use_cases/`.
- **The caller owns the `Protocol`:** it lists only the methods the caller uses, named in the caller's terms.
- **Plain values or small DTOs across the boundary:** `bool`, IDs, or a `UserSummary`; never the owner's entities.
- **The owner decides:** the public method applies the owner's rules; the caller never recomputes them from raw fields.
- **Batch for lists:** fetch the page, then make one call with all its IDs (`users.get_names(user_ids)`), never one call per row.
- **One direction:** if two services call each other, use events for one direction or move the boundary.
- **Calls share the request's session:** reads are fine; writes on both sides become one transaction, which is an exception to make deliberately, not by default.
- **Tests use a fake:** the caller's tests pass a fake `UserDirectory`; the owner tests its public interface itself.

## Anti-patterns
- **Importing the owner's repository or ORM model.** The caller depends on its tables and breaks when they change.
- **Returning the owner's entities.** The caller starts depending on the owner's model and its methods.
- **Re-checking the rule in the caller.** `user.status == "active"` in orders misses bans or verification added to users later.
- **Long call chains.** A → B → C on every request multiplies latency and failures; keep a local copy updated from events instead.

## Related
- [[0-layout-guide]]
- [[1b-layout-by-domain]]
- [[1b-layout-by-domain-events]]
