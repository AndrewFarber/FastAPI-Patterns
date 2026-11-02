---
title: "Layout: shared"
category: project-structure
tags:
  - project-layout
  - modular-monolith
  - domain-driven-design
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1a-layout]]"
  - "[[1b-layout-core]]"
---

# Layout: shared

The `shared/` package in [[1a-layout]]: stateless building blocks that services subclass or import as types. No state, no I/O, no business rules beyond shared value objects.

## Fits when
- Two or more services repeat the same base classes, helpers, or value objects.

Not when:
- It holds state, opens connections, or does I/O: put it in [[1b-layout-core]].
- Only one service uses it: keep it in that service.

## Signals
- **Feature:** "both services need `Money`", "where does the base event go", "where do pagination types go".
- **Code:** the same base class or helper copied across services; value objects duplicated with slightly different rules.

## Pattern
```
app/
├── main.py
├── core/
├── shared/
│   ├── value_objects/
│   ├── events/
│   ├── exceptions/
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
| `exceptions/`    | Base domain error types.                                  |
| `schemas/`       | Base Pydantic config; error envelopes.                    |
| `pagination/`    | Page and cursor types.                                    |
| `assemblers/`    | Helpers for mapping between domain objects and schemas.   |
| `clock/`         | Injectable current time for testable code.                |

Add a folder only when a second service needs it.

## Rules
- **The test:** holds state or does I/O → `core/`; otherwise → `shared/`.
- **Imports:** `shared/` imports neither `core/` nor `services/`.
- **The domain's only dependency:** `value_objects/`, `events/`, and `exceptions/` are plain Python with no Pydantic, ORM, or FastAPI; they are the only parts a service's `domain/` may import.
- **No domain concepts** outside `value_objects/`, and it holds only concepts every using service agrees on.
- **Tests mirror the folders.**

## Anti-patterns
- **One service's rules in a shared value object.** Every other service inherits them; keep it in that service.
- **I/O in a helper.** A pagination helper that runs its own count query belongs in `core/db/`.
- **Code only one service uses.** It hides who owns it; move it back into that service.

## Related
- [[0-layout-guide]]
- [[1a-layout]]
- [[1b-layout-core]]
