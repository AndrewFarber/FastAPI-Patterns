---
title: "Services guide"
category: project-structure
related:
  - "[[services-calls]]"
  - "[[services-events]]"
  - "[[layout]]"
---

# Services guide

| Note | Description |
| --- | --- |
| [[services-calls]] | In-process calls through a `Protocol` the caller owns and a public interface the owner exposes. Use when the caller needs an answer now. |
| [[services-events]] | Domain events through a transactional outbox, an SNS topic, and one SQS queue per subscribing service; subscribers react in their own transaction, once per event. Use when the other side can react later. |

Both build on the services in [[layout]].
