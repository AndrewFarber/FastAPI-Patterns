# FastAPI Patterns Index

One line per topic. Open the topic's guide to find its notes.

- [[0-settings-guide]] (`patterns/settings/`): configuration with pydantic-settings: one frozen sub-model per concern, access and testing, DB and auth settings, feature flags, AWS sources, values that change at runtime.
- [[0-layout-guide]] (`patterns/layout/`): project layout: by technical layer for small apps, or by domain for many domains or teams: services with a pure domain model, `core/` and `shared/` packages, in-process calls and domain events between services.
