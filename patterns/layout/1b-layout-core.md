---
title: "Layout: core"
category: project-structure
tags:
  - project-layout
  - modular-monolith
  - domain-driven-design
status: draft
related:
  - "[[0-layout-guide]]"
  - "[[1a-layout]]"
  - "[[1c-layout-shared]]"
  - "[[1a-settings-management]]"
---

# Layout: core

The `core/` package in [[1a-layout]]: cross-cutting infrastructure every service relies on, with no business rules. One folder per technical concern.

## Fits when
- Two or more services need the same infrastructure (database, events, auth, storage).

Not when:
- Only one service uses it: keep it in that service.
- It has no state and does no I/O: put it in [[1c-layout-shared]].

## Signals
- **Feature:** "every service needs X", "where does the event bus / storage client go".
- **Code:** the same plumbing copied across services; services importing each other just to reach shared infrastructure.

## Pattern
```
app/
├── main.py
├── core/
│   ├── config/
│   ├── db/
│   ├── cache/
│   ├── events/
│   ├── outbox/
│   ├── messaging/
│   ├── tasks/
│   ├── scheduler/
│   ├── exceptions/
│   ├── dependencies/
│   ├── middleware/
│   ├── auth/
│   ├── identity/
│   ├── security/
│   ├── observability/
│   ├── http/
│   ├── blob/
│   └── notifications/
├── shared/
└── services/
```

| Folder           | Holds                                                                  |
| ---------------- | ---------------------------------------------------------------------- |
| `config/`        | Settings, one sub-model per concern; see [[1a-settings-management]].   |
| `db/`            | Engine, sessions, ORM base and mixins, base repository, unit of work.  |
| `cache/`         | Cache client and key/TTL helpers.                                      |
| `events/`        | The in-process event bus; see [[1b-services-events]].          |
| `outbox/`        | Stores events in the same transaction and relays them later.           |
| `messaging/`     | Message broker publishers and consumers.                               |
| `tasks/`         | Background jobs run on demand.                                         |
| `scheduler/`     | Registering and running periodic jobs.                                 |
| `exceptions/`    | Mapping domain errors to HTTP responses.                               |
| `dependencies/`  | Shared `Depends()` providers: session, unit of work, caller.           |
| `middleware/`    | Request IDs, CORS, timing, request logging.                            |
| `auth/`          | Authenticating callers and checking permissions.                       |
| `identity/`      | Who the caller is: principal, tenant, request context.                 |
| `security/`      | Hashing, encryption, signing.                                          |
| `observability/` | Logging, metrics, tracing.                                             |
| `http/`          | Outbound HTTP client: timeouts, retries, header propagation.           |
| `blob/`          | File and object storage.                                               |
| `notifications/` | Email, SMS, and push behind one interface.                             |

Add a folder only when a second service needs it.

## Rules
- **Folders only:** one folder per concern; no loose modules.
- **No business rules:** anything about one domain belongs in that service.
- **Imports:** `core/` imports `shared/`, never `services/`.
- **Stateless parts go to `shared/`:** base event and error types live in [[1c-layout-shared]]; `core/` holds what runs them (the bus, the HTTP error mapping).
- **Bases, not instances:** the base repository lives in `db/`; concrete repositories stay in each service's `infrastructure/`.
- **Domain code never imports `core/`:** a service's `domain/` imports only from `shared/`.
- **Tests mirror the folders.**

## Anti-patterns
- **Business rules in `core/`.** A discount rule in `notifications/` couples every service to one domain.
- **A `utils.py` or `common.py` grab bag.** Nothing says what belongs there, so everything ends up there.
- **Clients created at import time.** Tests can't replace them; build them at startup and provide them through `dependencies/`.

## Related
- [[0-layout-guide]]
- [[1a-layout]]
- [[1c-layout-shared]]
- [[1a-settings-management]]
