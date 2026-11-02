---
title: "Services guide"
category: project-structure
tags:
  - modular-monolith
  - domain-driven-design
  - guide
status: draft
related:
  - "[[1a-layout]]"
  - "[[1a-services-calls]]"
  - "[[1b-services-events]]"
---

# Services guide

How the services in [[1a-layout]] talk to each other without importing each other's internals. Use a call when the caller needs an answer now, an event when the other side can react later.

## 1. Between services
- [[1a-services-calls]]: in-process calls through a `Protocol` the caller owns and a public interface the owner exposes.
- [[1b-services-events]]: domain events through a transactional outbox, an SNS topic, and one SQS queue per subscribing service; subscribers react in their own transaction, once per event.

## Related
- [[1a-layout]]
- [[1a-services-calls]]
- [[1b-services-events]]
