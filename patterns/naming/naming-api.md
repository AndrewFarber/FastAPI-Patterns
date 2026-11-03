---
title: "Naming: API"
category: conventions
related:
  - "[[naming-guide]]"
  - "[[naming]]"
  - "[[layout]]"
  - "[[services-calls]]"
---

# Naming: API

## Overview
Names at a service's entry points: `api/`, `event_handlers/`, and `public.py` ([[layout]]), building on [[naming]]. A URL shows whether it is CRUD or an action, and the route function, its schemas, and its dependencies follow from the URL.

## Rules
- **CRUD URLs are nouns:** a plural collection and its items, `/orders` and `/orders/{order_id}`, with the HTTP method as the operation: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. Filters are query parameters: `GET /orders?user_id=1&status=open`.
- **Action URLs end in a verb** and are always `POST`: `POST /users/{user_id}/deactivate`. A verb segment means an action, and a noun segment means CRUD.
- **Path parameters are `<resource>_id`:** `user_id`, never `id`.
- **Route functions are the method plus the resource,** singular when it handles one item and plural when it returns many: `post_order`, `get_order`, `get_orders`, `patch_order`. An action appends its verb: `post_user_deactivate`. Never the use case's name; the route calls `place_order`, it isn't it.
- **Request schemas name the intent:** `<Resource>Create` (`POST`), `<Resource>Replace` (`PUT`, every field required), `<Resource>Patch` (`PATCH`, every field optional). An action's input, when it has one, is `<UseCase>In` (`DeactivateUserIn`). The body parameter is always `body`.
- **Response schemas are `<Resource>Read`:** `OrderRead`, one per resource, the same CRUD word as the request schemas. It is what a client reads back from every method, `POST` and `PATCH` included.
- **Dependencies:** the provider is `get_<collaborator>` and its `Annotated` alias `<Collaborator>Dep`: `get_order_repository`, `OrderRepositoryDep`. The route's parameter takes the collaborator's name: `order_repository: OrderRepositoryDep`.
- **Each `api/` module has one `router`,** imported under the service's name where it's mounted: `router as orders_router`.
- **Event handlers:** the file is named after the event and the function is `handle_<event>`: `event_handlers/user_deactivated.py`, `handle_user_deactivated()`. Each package's `register()` wires its handlers.
- **The public interface is `<Service>Service`:** `UsersService` in `public.py` ([[services-calls]]). `Api` would suggest HTTP, which lives in `api/`.

## Code example

| Method + path | Route function | Body | Response |
| --- | --- | --- | --- |
| `GET /orders?user_id=&status=` | `get_orders` | | `list[OrderRead]` |
| `POST /orders` | `post_order` | `OrderCreate` | `OrderRead` |
| `GET /orders/{order_id}` | `get_order` | | `OrderRead` |
| `PUT /orders/{order_id}` | `put_order` | `OrderReplace` | `OrderRead` |
| `PATCH /orders/{order_id}` | `patch_order` | `OrderPatch` | `OrderRead` |
| `DELETE /orders/{order_id}` | `delete_order` | | 204 |
| `POST /users/{user_id}/deactivate` | `post_user_deactivate` | `DeactivateUserIn`, if any | 204 |

```python
# app/services/users/api/router.py
from fastapi import APIRouter

from app.core.dependencies.db import UnitOfWorkDep
from app.services.users.api.dependencies import UserRepositoryDep
from app.services.users.api.schemas import UserCreate, UserRead
from app.services.users.use_cases.deactivate_user import (
    DeactivateUserCommand,
    deactivate_user,
)
from app.services.users.use_cases.register_user import (
    RegisterUserCommand,
    register_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=201)
def post_user(body: UserCreate, user_repository: UserRepositoryDep) -> UserRead:
    user = register_user(RegisterUserCommand(name=body.name), user_repository)
    return UserRead(id=user.id, name=user.name, status=user.status)


@router.post("/{user_id}/deactivate", status_code=204)
def post_user_deactivate(
    user_id: int,
    user_repository: UserRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> None:
    deactivate_user(
        DeactivateUserCommand(user_id=user_id),
        user_repository,
        unit_of_work.event_publisher,
    )
```
