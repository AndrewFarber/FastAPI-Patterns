---
title: "Layout by domain: core"
category: project-structure
tags: [project-layout, modular-monolith, domain-driven-design]
status: draft
related: ["[[layout-by-domain]]", "[[1a-settings-management]]"]
---

# Layout by domain: core

The `core/` package in [[layout-by-domain]]: cross-cutting infrastructure every service relies on, with no business rules. One folder per technical concern.

## Fits when
- Two or more services need the same infrastructure (database, events, auth, storage).

Not when:
- Only one service uses it: keep it in that service.

## Signals
- **Feature:** "every service needs X", "where does the event bus / storage client go".
- **Code:** the same plumbing copied across services; services importing each other just to reach shared infrastructure; a growing `utils.py`.

## Pattern
```
app/
├── main.py
├── core/
│   ├── config/
│   ├── db/
│   ├── events/
│   ├── outbox/
│   ├── exceptions/
│   ├── dependencies/
│   ├── auth/
│   ├── identity/
│   ├── security/
│   ├── observability/
│   ├── blob/
│   └── scheduler/
└── services/
```

| Folder           | Holds                                                         |
| ---------------- | ------------------------------------------------------------- |
| `config/`        | Settings, one sub-model per concern.                          |
| `db/`            | Engine, session factory, ORM base, unit of work.              |
| `events/`        | Base event type and the in-process event bus.                 |
| `outbox/`        | Stores events in the same transaction and relays them later.  |
| `exceptions/`    | Base domain errors and their mapping to HTTP responses.       |
| `dependencies/`  | Shared `Depends()` providers: session, unit of work, caller.  |
| `auth/`          | Authenticating callers and checking permissions.              |
| `identity/`      | Who the caller is: principal, tenant, request context.        |
| `security/`      | Hashing, encryption, signing.                                 |
| `observability/` | Logging, metrics, tracing.                                    |
| `blob/`          | File and object storage.                                      |
| `scheduler/`     | Registering and running periodic jobs.                        |

Add a folder only when a second service needs it.

## Rules
- **Folders only:** one folder per concern; no loose modules and no `utils/`.
- **No business rules:** anything about one domain belongs in that service.
- **Dependency direction:** `services → core`. `core/` never imports from `services/`.
- **Services stay pure:** `domain.py` and `events.py` in a service never import from `core/` folders that touch FastAPI or I/O.
- **Tests mirror the folders.**

## Related
- [[layout-by-domain]]
- [[1a-settings-management]]
