---
title: "Layout: shared"
category: project-structure
related:
  - "[[layout-guide]]"
  - "[[layout]]"
---

# Layout: shared

## Overview
The `shared/` package in [[layout]]: stateless building blocks that services subclass or import as types. No state, no I/O, no business rules beyond shared value objects.

## Rules
- **The test:** holds state or does I/O → `core/`; otherwise → `shared/`.
- **Imports:** `shared/` imports neither `core/` nor `services/`.
- **The domain's only dependency:** `value_objects/`, `events/`, and `errors/` are plain Python with no Pydantic, ORM, or FastAPI; they are the only parts a service's `domain/` may import.
- **No domain concepts** outside `value_objects/`, and it holds only concepts every using service agrees on.
- **Tests mirror the folders.**

## Code example
```
app/
├── main.py
├── core/
├── shared/
│   ├── value_objects/
│   ├── events/
│   ├── errors/
│   ├── schemas/
│   ├── pagination/
│   ├── assemblers/
│   └── clock/
└── services/
```

| Folder           | Holds                                                     |
| ---------------- | --------------------------------------------------------- |
| `value_objects/` | Value objects several domains agree on: `Money`, `Email`. |
| `events/`        | Base domain event type and the `EventPublisher` protocol. |
| `errors/`        | Base domain error types.                                  |
| `schemas/`       | Base Pydantic config; error envelopes.                    |
| `pagination/`    | Page and cursor types.                                    |
| `assemblers/`    | Helpers for mapping between domain objects and schemas.   |
| `clock/`         | Injectable current time for testable code.                |

Add a folder only when a second service needs it.
