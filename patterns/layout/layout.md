---
title: "Layout"
category: project-structure
related:
  - "[[layout-guide]]"
  - "[[services-guide]]"
  - "[[layout-core]]"
  - "[[layout-shared]]"
  - "[[services-calls]]"
  - "[[services-events]]"
---

# Layout

## Overview
One deployable app split into self-contained services, one per bounded context. Each service keeps its domain model free of framework code, and services talk through a public interface or domain events.

## Rules
- **Domain is pure:** everything in `domain/` is plain dataclasses, exceptions, and `Protocol`s, with no FastAPI, ORM, or I/O. It imports only `shared/value_objects/`, `shared/events/`, and `shared/errors/`.
- **Use cases depend on `Protocol`s:** they import `domain/`, never `infrastructure/`.
- **Infrastructure implements the domain:** it imports `domain/` to implement its `Protocol`s, never `use_cases/` or `api/`.
- **Entry points wire it together:** `api/` (its `Depends()` providers) and `event_handlers/` build the repository implementations and pass them to the use cases. They are the only layers that import both `use_cases/` and `infrastructure/`.
- **Between services:** call its public interface or react to its domain events ([[services-guide]]); never import its internals.
- **Each service owns its data:** its tables live in its own database schema (`orders`, `users`), and no other service queries them.
- **Across packages:** services import `core/` and `shared/`; `core/` imports `shared/`; `shared/` imports neither. `core/` and `shared/` never import from `services/`.
- **Tests mirror the services;** domain and use cases test without a database.

## Code example
```
app/
├── main.py
├── workers.py
├── core/
├── shared/
└── services/
    ├── users/
    │   ├── __init__.py
    │   ├── public.py
    │   ├── domain/
    │   │   ├── entities.py
    │   │   ├── events.py
    │   │   ├── errors.py
    │   │   └── protocols.py
    │   ├── use_cases/
    │   ├── infrastructure/
    │   │   ├── models.py
    │   │   └── repositories.py
    │   └── api/
    │       ├── router.py
    │       ├── schemas.py
    │       └── dependencies.py
    └── orders/
        ├── ...              same layers, without public.py and events.py
        └── event_handlers/
tests/
```

A service has only the parts it uses: `users` is called by others and publishes an event, so it has `public.py` and `events.py`; `orders` calls users and reacts to its event, so it has `event_handlers/`.

| Folder / file     | Holds                                                             |
| ----------------- | ----------------------------------------------------------------- |
| `main.py`         | App creation; mounts each service's router.                       |
| `workers.py`      | Lambda entry points: event consumers, outbox sweeper.             |
| `core/`           | Runtime infrastructure; see [[layout-core]].            |
| `shared/`         | Stateless building blocks; see [[layout-shared]].       |
| `services/<name>` | One bounded context.                                              |
| `__init__.py`     | Re-exports the public interface; nothing else.                    |
| `public.py`       | What other services may call; see [[services-calls]].     |
| `domain/`         | The service's business model, free of framework code.             |
| `entities.py`     | Entities and the value objects only this service uses.            |
| `events.py`       | Domain events: facts the service announces.                       |
| `errors.py`       | Domain errors, subclassing `shared/errors/`.                  |
| `protocols.py`    | What the domain needs from outside: repositories, other services. |
| `use_cases/`      | One application action per file; orchestrates the domain.         |
| `infrastructure/` | ORM models and repository implementations.                        |
| `api/`            | Routes, schemas, and `Depends()` wiring of implementations.       |
| `event_handlers/` | Reactions to other services' events; see [[services-events]].     |

Split a file in `domain/` into a subpackage only when it outgrows one file. Add more folders (`clients/`, ...) only when needed.
