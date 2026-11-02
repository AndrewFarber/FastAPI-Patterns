---
title: "Layout guide"
category: project-structure
related:
  - "[[layout]]"
  - "[[services-guide]]"
---

# Layout guide

| Note | Description |
| --- | --- |
| [[layout]] | The base: one self-contained service per bounded context with a pure domain model, plus `core/` and `shared/`. |
| [[layout-core]] | Cross-cutting infrastructure with state or I/O: database, events, auth, storage. |
| [[layout-shared]] | Stateless building blocks: value objects, base event and error types, pagination. |

How services talk to each other is in [[services-guide]].
