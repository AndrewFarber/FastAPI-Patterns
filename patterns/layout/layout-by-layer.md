---
title: "Layout by layer"
category: project-structure
tags: [project-layout, layered-architecture]
status: draft
related: ["[[1a-settings-management]]"]
---

# Layout by layer

## Problem
Once an app outgrows a single file, code needs a predictable home. Without one, routes, queries, and business rules end up mixed together and nobody knows where new code should go.

## Use when
- Small to medium apps with a handful of domains (e.g. `users`, `orders`).
- One team, or one developer, owns the whole codebase.
- You want the structure most FastAPI tutorials and newcomers already recognize.

## Avoid when
- The app has many domains (roughly 10+) or keeps adding them: group code by feature instead (a separate note, not written yet).
- Multiple teams own different features.
- Business logic is complex and should be independent of FastAPI and the database: use a hexagonal layout (a separate note, not written yet).

## Solution

### Project root
```
project/
├── app/              application code (below)
├── tests/            mirrors the layers: tests/routers/, tests/services/, ...
├── migrations/       Alembic migration scripts
├── pyproject.toml
├── alembic.ini
└── Dockerfile
```

### Application
```
app/
├── main.py           the app; app-wide modules (observability.py) sit next to it
├── config/
├── db/
├── security/
├── exceptions/
├── middleware/
├── dependencies/
├── routers/
├── schemas/
├── models/
├── services/
├── repositories/
├── clients/
└── tasks/
```

### What each folder does

| Folder          | Responsibility                                                                                                                                            |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`       | Creates the app, mounts routers, registers middleware and exception handlers. No business logic. Small app-wide modules (`observability.py`) sit next to it. |
| `config/`       | Settings (`pydantic-settings`): one sub-model per concern, composed in `settings.py`, read from env vars. See [[1a-settings-management]].                 |
| `db/`           | Engine, session factory, ORM declarative base. Creates DB plumbing; does not hand it to requests.                                                         |
| `security/`     | Pure helpers: verifying identity-provider tokens (JWKS fetch and cache, claim checks). No FastAPI imports. See [[2c-settings-auth]].                      |
| `exceptions/`   | Domain exceptions (`OrderNotFound`) and the handlers that map them to HTTP responses.                                                                     |
| `middleware/`   | Cross-cutting request logic: CORS, timing, logging.                                                                                                       |
| `dependencies/` | `Depends()` functions that wire the layers into requests: settings, DB session per request, current user, pagination params.                              |
| `routers/`      | HTTP only: paths, status codes, request parsing, calling services. No queries, no business rules.                                                         |
| `schemas/`      | Pydantic models for request and response bodies (`UserCreate`, `UserRead`).                                                                               |
| `models/`       | ORM models (SQLAlchemy tables). Not returned directly from endpoints.                                                                                     |
| `services/`     | Business logic: rules, orchestration across models and clients. Raises domain exceptions, never `HTTPException`. Add once logic outgrows simple CRUD.     |
| `repositories/` | All DB queries for one model. Services call repositories instead of writing queries. Add for testability or when storage may change. Also called `crud/`. |
| `clients/`      | Wrappers around external APIs (payments, email, other services).                                                                                          |
| `tasks/`        | Background work: FastAPI `BackgroundTasks`, Celery, ARQ.                                                                                                  |

### Rules
- **Dependency direction:** `routers → services → repositories → models`. Lower layers never import higher ones; nothing imports `routers/`.
- **Plumbing vs wiring:** `db/` and `security/` create things; `dependencies/` hands them to requests (`dependencies/db.py` yields a session from `db/session.py`, `dependencies/auth.py` uses `security/tokens.py`).

## Related
- [[1a-settings-management]]
