---
title: "Layout guide"
category: project-structure
tags:
  - project-layout
  - guide
status: draft
related:
  - "[[1a-layout-by-layer]]"
  - "[[1b-layout-by-domain]]"
---

# Layout guide

Pick one layout per app; indented notes describe parts of the note above them.

## 1. Layouts
- [[1a-layout-by-layer]]: one folder per technical layer, one file per domain inside each; for small to medium apps owned by one team.
- [[1b-layout-by-domain]]: one self-contained service per bounded context with a pure domain model; for many domains or several teams.
    - [[1b-layout-by-domain-core]]: cross-cutting infrastructure with state or I/O: database, events, auth, storage.
    - [[1b-layout-by-domain-shared]]: stateless building blocks: value objects, base event and error types, pagination.
    - [[1b-layout-by-domain-calls]]: in-process calls between services through a `Protocol` the caller owns and a public interface the owner exposes.
    - [[1b-layout-by-domain-events]]: domain events between services: the publisher owns the fact, subscribers react after commit in their own transaction.

## Related
- [[1a-layout-by-layer]]
- [[1b-layout-by-domain]]
