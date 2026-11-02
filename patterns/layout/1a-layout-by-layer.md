---
title: Layout by layer
category: project-structure
tags:
  - project-layout
  - layered-architecture
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1b-layout-by-domain]]"
  - "[[1a-settings-management]]"
  - "[[1b-settings-access]]"
---

# Layout by layer

One top-level folder per technical layer, with dependencies pointing one way. Each kind of code has a predictable home.

## Fits when
- A small to medium app with a few domains, owned by one team.

Not when:
- Many domains or several teams: use [[1b-layout-by-domain]].

## Signals
- **Feature:** "where should this go", "split up `main.py`".
- **Code:** HTTP handling, business rules, and data access mixed in the same file.

## Pattern
```
app/
├── main.py
├── config/
├── dependencies/
├── routers/
├── schemas/
├── services/
├── repositories/
└── models/
tests/
```

| Folder          | Holds                                                   |
| --------------- | ------------------------------------------------------- |
| `main.py`       | App creation and wiring.                                |
| `config/`       | Settings; see [[1a-settings-management]].               |
| `dependencies/` | `Depends()` providers: settings, session, services.     |
| `routers/`      | HTTP layer.                                             |
| `schemas/`      | Request and response models.                            |
| `services/`     | Business logic.                                         |
| `repositories/` | Data access.                                            |
| `models/`       | Persistence models.                                     |

Add further layers (`security/`, `clients/`, `tasks/`, `middleware/`, ...) only when needed.

## Rules
- **Imports go down, never up:** routers import services, services import repositories, repositories import models. Routers never call repositories directly.
- **Schemas stay near the edge:** routers import schemas; services may take request schemas as input but return models or plain values; repositories never import schemas.
- **`config/` imports nothing else from the app;** every other layer receives settings through `dependencies/` ([[1b-settings-access]]).
- **Only routers import `dependencies/`;** it builds what they inject and may import any layer below routers.
- **One file per domain inside each layer:** `routers/orders.py`, `services/orders.py`, ...
- **Tests mirror the layers.**

## Anti-patterns
- **Business rules in routers.** They can't be reused from tasks or tested without HTTP.
- **Routers querying the database.** Some paths then skip the service's rules.
- **One file per layer (`services.py`).** It grows without bound; split per domain.

## Related
- [[0-layout-guide]]
- [[1b-layout-by-domain]]
- [[1a-settings-management]]
- [[1b-settings-access]]
