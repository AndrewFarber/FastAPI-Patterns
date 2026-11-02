---
title: "Layout by domain"
category: project-structure
tags: [project-layout, modular-monolith, domain-driven-design]
status: draft
related: ["[[layout-by-layer]]", "[[layout-by-domain-core]]", "[[1a-settings-management]]"]
---

# Layout by domain

One deployable app split into self-contained services, one per bounded context. Each service keeps its domain model free of framework code, and services talk through a public interface or domain events.

## Fits when
- Many domains, or several teams working in one codebase.
- Business rules are complex enough to deserve their own model.
- Services may later be extracted into separate deployments.

Not when:
- A small app with mostly CRUD: use [[layout-by-layer]].

## Signals
- **Feature:** "add a new domain", "who owns this code", "when X happens, do Y in another domain".
- **Code:** business rules tangled with HTTP or ORM code; domains importing each other's models or queries.

## Pattern
```
app/
├── main.py
├── core/
└── services/
    ├── orders/
    │   ├── __init__.py
    │   ├── domain.py
    │   ├── events.py
    │   ├── use_cases/
    │   ├── infrastructure/
    │   │   ├── models.py
    │   │   └── repositories.py
    │   └── api/
    │       ├── router.py
    │       └── schemas.py
    └── users/
        └── ...
tests/
```

| Folder / file     | Holds                                                      |
| ----------------- | ---------------------------------------------------------- |
| `main.py`         | App creation; mounts each service's router.                |
| `core/`           | Cross-cutting infrastructure; see [[layout-by-domain-core]]. |
| `services/<name>` | One bounded context.                                       |
| `__init__.py`     | The service's public interface.                            |
| `domain.py`       | Entities and value objects as dataclasses.                 |
| `events.py`       | Domain events as dataclasses.                              |
| `use_cases/`      | One application action per file; orchestrates the domain.  |
| `infrastructure/` | ORM models and repository implementations.                 |
| `api/`            | HTTP layer: routes and request/response schemas.           |

Split `domain.py` into a package only when it outgrows one file. Add more folders (`event_handlers/`, `clients/`, ...) only when needed.

## Rules
- **Dependency direction:** `api → use_cases → domain ← infrastructure`. `domain.py` and `events.py` import nothing from the other layers.
- **Domain is pure:** plain dataclasses; no FastAPI, ORM, or I/O.
- **Use cases depend on `Protocol`s:** repository implementations are injected.
- **Between services:** call another service's public interface, or react to its domain events; never import its internals.
- **Each service owns its data:** no queries against another service's tables.
- **`core/` never imports from `services/`.**
- **Tests mirror the services;** domain and use cases test without a database.

## Related
- [[layout-by-layer]]
- [[layout-by-domain-core]]
- [[1a-settings-management]]
