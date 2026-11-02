---
title: "Layout by layer"
category: project-structure
tags: [project-layout, layered-architecture]
status: draft
related: ["[[1a-settings-management]]"]
---

# Layout by layer

One top-level folder per technical layer, with dependencies pointing one way. Each kind of code has a predictable home.

## Fits when
- A small to medium app with a few domains, owned by one team.

Not when:
- Many domains or several teams: group by feature instead.

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

| Folder          | Holds                                     |
| --------------- | ----------------------------------------- |
| `main.py`       | App creation and wiring.                  |
| `config/`       | Settings.                                 |
| `dependencies/` | `Depends()` providers.                    |
| `routers/`      | HTTP layer.                               |
| `schemas/`      | Request and response models.              |
| `services/`     | Business logic.                           |
| `repositories/` | Data access.                              |
| `models/`       | Persistence models.                       |

Add further layers (`clients/`, `tasks/`, `middleware/`, ...) only when needed.

## Rules
- **Dependency direction:** `routers → services → repositories → models`. Lower layers never import higher ones.
- **One file per domain inside each layer:** `routers/orders.py`, `services/orders.py`, ...
- **Tests mirror the layers.**

## Related
- [[1a-settings-management]]
