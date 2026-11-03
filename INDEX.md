# FastAPI Patterns Index

One line per topic. Open the topic's guide to find its notes.

- [[settings-guide]] (`patterns/settings/`): configuration with pydantic-settings: one frozen sub-model per concern, access and testing, DB settings, feature flags, AWS sources, values that change at runtime.
- [[layout-guide]] (`patterns/layout/`): project layout by domain: one service per bounded context with a pure domain model, plus `core/` and `shared/` packages.
- [[services-guide]] (`patterns/services/`): how services talk: in-process calls through a caller-owned `Protocol`, and domain events through an outbox, SNS, and an SQS queue per service.
- [[naming-guide]] (`patterns/naming/`): naming conventions: modules, factory verbs, variables, tests, and per layer the domain (entities, events, errors, commands), infrastructure (ORM classes, tables, constraints), and API (URLs, routes, schemas, dependencies).
