# FastAPI Patterns Index

One line per topic. Open the topic's guide to find its notes.

- [[0-settings-guide]] (`patterns/settings/`): configuration with pydantic-settings: one frozen sub-model per concern, access and testing, DB and auth settings, feature flags, AWS sources, values that change at runtime.
- [[0-layout-guide]] (`patterns/layout/`): project layout by domain: one service per bounded context with a pure domain model, plus `core/` and `shared/` packages.
- [[0-services-guide]] (`patterns/services/`): how services talk: in-process calls through a caller-owned `Protocol`, and domain events through an outbox, SNS, and an SQS queue per service.
