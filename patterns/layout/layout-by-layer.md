---
title: "Layout by layer"
category: project-structure
tags: [project-layout, layered-architecture]
status: draft
related: ["[[1a-settings-management]]", "[[2c-settings-auth]]"]
---

# Layout by layer

One top-level folder per technical layer, with dependencies pointing one way: routers call services, services call repositories. Every kind of code gets a predictable home, so routes, queries, and business rules don't mix.

## Fits when
- A small to medium app with a handful of domains (`users`, `orders`), owned by one team.
- The app has outgrown a single file, or new code has no obvious home.

Not when:
- Many domains (roughly 10+) or several teams: group by feature instead (not written yet).
- Business logic must be independent of FastAPI and the database: hexagonal layout (not written yet).

## Signals
- **Feature:** "add an endpoint/domain", "where should this go", "split up `main.py`".
- **Code:** routes and SQL in the same file (`session.execute(` or `select(` under `routers/` or in `main.py`); `HTTPException` raised in services; ORM models returned from endpoints; `models.py`/`schemas.py` as single growing files.

## Pattern
```
project/
├── app/              application code (below)
├── tests/            mirrors the layers: tests/routers/, tests/services/, ...
├── migrations/       Alembic migration scripts
├── pyproject.toml
├── alembic.ini
└── Dockerfile
```

```
app/
├── main.py
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

| Folder          | Holds                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| `main.py`       | Creates the app, mounts routers, registers middleware and exception handlers. No business logic.              |
| `config/`       | Settings: one sub-model per concern, composed in `settings.py`. See [[1a-settings-management]].               |
| `db/`           | Engine, session factory, declarative base. Creates DB plumbing; doesn't hand it to requests.                  |
| `security/`     | Pure helpers for verifying tokens (JWKS fetch and cache, claim checks). No FastAPI imports. See [[2c-settings-auth]]. |
| `exceptions/`   | Domain exceptions (`OrderNotFound`) and the handlers that map them to HTTP responses.                         |
| `middleware/`   | Cross-cutting request logic: CORS, timing, logging.                                                           |
| `dependencies/` | `Depends()` functions: settings, DB session per request, current user, pagination.                           |
| `routers/`      | HTTP only: paths, status codes, parsing, calling services.                                                    |
| `schemas/`      | Pydantic request and response models (`UserCreate`, `UserRead`).                                             |
| `models/`       | ORM models. Never returned directly from endpoints.                                                           |
| `services/`     | Business rules and orchestration. Raise domain exceptions, never `HTTPException`. Add once logic outgrows CRUD. |
| `repositories/` | All queries for one model. Add for testability or when storage may change. Also called `crud/`.               |
| `clients/`      | Wrappers around external APIs and AWS services.                                                               |
| `tasks/`        | Background work: `BackgroundTasks`, Celery, ARQ.                                                              |

## Rules
- **Dependency direction:** `routers → services → repositories → models`. Lower layers never import higher ones; nothing imports `routers/`.
- **Plumbing vs wiring:** `db/` and `security/` create things; `dependencies/` hands them to requests (`dependencies/db.py` yields a session from `db/session.py`).
- **One file per domain inside each layer:** `routers/orders.py`, `services/orders.py`, `schemas/orders.py`.

## Anti-patterns
- **Queries in routers.** The route can't be tested without a database, and the query can't be reused.
- **`HTTPException` in services.** Ties business logic to HTTP; raise `OrderNotFound` and map it in `exceptions/`.
- **Returning ORM models.** Leaks columns (password hashes) and couples the API to the table; return a schema.

## Related
- [[1a-settings-management]]
- [[2c-settings-auth]]
