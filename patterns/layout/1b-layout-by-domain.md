---
title: Layout by domain
category: project-structure
tags:
  - project-layout
  - modular-monolith
  - domain-driven-design
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1a-layout-by-layer]]"
  - "[[1b-layout-by-domain-core]]"
  - "[[1b-layout-by-domain-shared]]"
  - "[[1b-layout-by-domain-calls]]"
  - "[[1b-layout-by-domain-events]]"
---

# Layout by domain

One deployable app split into self-contained services, one per bounded context. Each service keeps its domain model free of framework code, and services talk through a public interface or domain events.

## Fits when
- Many domains, or several teams working in one codebase.
- Business rules are complex enough to deserve their own model.
- Services may later be extracted into separate deployments.

Not when:
- A small app with mostly CRUD: use [[1a-layout-by-layer]].

## Signals
- **Feature:** "add a new domain", "who owns this code", "when X happens, do Y in another domain".
- **Code:** business rules tangled with HTTP or ORM code; domains importing each other's models or queries.

## Pattern
```
app/
├── main.py
├── core/
├── shared/
└── services/
    ├── orders/
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
    └── users/
        └── ...
tests/
```

| Folder / file     | Holds                                                             |
| ----------------- | ----------------------------------------------------------------- |
| `main.py`         | App creation; mounts each service's router.                       |
| `core/`           | Runtime infrastructure; see [[1b-layout-by-domain-core]].            |
| `shared/`         | Stateless building blocks; see [[1b-layout-by-domain-shared]].       |
| `services/<name>` | One bounded context.                                              |
| `__init__.py`     | Re-exports the public interface; nothing else.                    |
| `public.py`       | What other services may call; see [[1b-layout-by-domain-calls]].     |
| `domain/`         | The service's business model, free of framework code.             |
| `entities.py`     | Entities and the value objects only this service uses.            |
| `events.py`       | Domain events: facts the service announces.                       |
| `errors.py`       | Domain errors, subclassing `shared/exceptions/`.                  |
| `protocols.py`    | What the domain needs from outside: repositories, other services. |
| `use_cases/`      | One application action per file; orchestrates the domain.         |
| `infrastructure/` | ORM models and repository implementations.                        |
| `api/`            | Routes, schemas, and `Depends()` wiring of implementations.       |

Split a file in `domain/` into a subpackage only when it outgrows one file. Add more folders (`event_handlers/`, `clients/`, ...) only when needed.

## Rules
- **Domain is pure:** everything in `domain/` is plain dataclasses, exceptions, and `Protocol`s, with no FastAPI, ORM, or I/O. It imports only `shared/value_objects/`, `shared/events/`, and `shared/exceptions/`.
- **Use cases depend on `Protocol`s:** they import `domain/`, never `infrastructure/`.
- **Infrastructure implements the domain:** it imports `domain/` to implement its `Protocol`s, never `use_cases/` or `api/`.
- **`api/` wires it together:** its `Depends()` providers build the repository implementations and pass them to the use cases. It is the only layer that imports both `use_cases/` and `infrastructure/`.
- **Between services:** call another service's public interface ([[1b-layout-by-domain-calls]]), or react to its domain events ([[1b-layout-by-domain-events]]); never import its internals.
- **Each service owns its data:** its tables live in its own database schema (`orders`, `users`), and no other service queries them.
- **Across packages:** services import `core/` and `shared/`; `core/` imports `shared/`; `shared/` imports neither. `core/` and `shared/` never import from `services/`.
- **Tests mirror the services;** domain and use cases test without a database.

## Anti-patterns
- **ORM models as domain entities.** The domain can no longer be tested without a database.
- **Importing another service's models or repositories.** The services can no longer change or be extracted separately.
- **Joins across services' tables.** A schema change in one service breaks another.
- **One service per table.** Services that are too small call each other for every action; split by business capability.

## Related
- [[0-layout-guide]]
- [[1a-layout-by-layer]]
- [[1b-layout-by-domain-core]]
- [[1b-layout-by-domain-shared]]
- [[1b-layout-by-domain-calls]]
- [[1b-layout-by-domain-events]]
