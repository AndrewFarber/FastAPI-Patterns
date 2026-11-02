---
title: "Layout guide"
category: project-structure
tags:
  - project-layout
  - guide
status: draft
related:
  - "[[1a-layout]]"
  - "[[0-services-guide]]"
---

# Layout guide

[[1a-layout]] is the base; the other notes describe its top-level packages. How services talk to each other is in [[0-services-guide]].

## 1. Layout
- [[1a-layout]]: one self-contained service per bounded context with a pure domain model, plus `core/` and `shared/`.
- [[1b-layout-core]]: cross-cutting infrastructure with state or I/O: database, events, auth, storage.
- [[1c-layout-shared]]: stateless building blocks: value objects, base event and error types, pagination.

## Related
- [[1a-layout]]
- [[0-services-guide]]
