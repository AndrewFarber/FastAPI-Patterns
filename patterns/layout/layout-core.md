---
title: "Layout: core"
category: project-structure
related:
  - "[[layout-guide]]"
  - "[[layout]]"
  - "[[layout-shared]]"
  - "[[settings-management]]"
  - "[[services-events]]"
---

# Layout: core

## Overview
The `core/` package in [[layout]]: cross-cutting infrastructure every service relies on, with no business rules. One folder per technical concern.

## Rules
- **Folders only:** one folder per concern; no loose modules.
- **No business rules:** anything about one domain belongs in that service.
- **Imports:** `core/` imports `shared/`, never `services/`.
- **Stateless parts go to `shared/`:** base event and error types live in [[layout-shared]]; `core/` holds what runs them (the outbox, the consumer, the HTTP error mapping).
- **Bases, not instances:** the base repository lives in `db/`; concrete repositories stay in each service's `infrastructure/`.
- **Domain code never imports `core/`:** a service's `domain/` imports only from `shared/`.
- **Tests mirror the folders.**

## Code example
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
│   ├── aws/
│   ├── blob/
│   └── notifications/
├── shared/
└── services/
```

| Folder           | Holds                                                                  |
| ---------------- | ---------------------------------------------------------------------- |
| `config/`        | Settings, one sub-model per concern; see [[settings-management]].   |
| `db/`            | Engine, sessions, ORM base and mixins, base repository, unit of work.  |
| `cache/`         | Cache client and key/TTL helpers.                                      |
| `events/`        | Event wire format and consumers; see [[services-events]].           |
| `outbox/`        | Stores events in the publisher's transaction; relay and sweeper.       |
| `messaging/`     | Message broker clients: the SNS sender.                                |
| `tasks/`         | Background jobs run on demand.                                         |
| `scheduler/`     | Registering and running periodic jobs.                                 |
| `exceptions/`    | Mapping domain errors to HTTP responses.                               |
| `dependencies/`  | Shared `Depends()` providers: session, unit of work, caller.           |
| `middleware/`    | Request IDs, timing, request logging.                                  |
| `auth/`          | Authenticating callers and checking permissions.                       |
| `identity/`      | Who the caller is: principal, tenant, request context.                 |
| `security/`      | Hashing, encryption, signing.                                          |
| `observability/` | Logging, metrics, tracing.                                             |
| `http/`          | Outbound HTTP client: timeouts, retries, header propagation.           |
| `aws/`           | AWS client config with short timeouts, and caches for live values.    |
| `blob/`          | File and object storage.                                               |
| `notifications/` | Email, SMS, and push behind one interface.                             |

Add a folder only when a second service needs it.
