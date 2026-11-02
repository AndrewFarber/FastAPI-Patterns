---
title: "Settings guide"
category: project-structure
related:
  - "[[settings-management]]"
---

# Settings guide

| Note | Description |
| --- | --- |
| [[settings-management]] | The base: one `core/config/` package, a frozen sub-model per concern, a root `Settings` that only composes. |
| [[settings-access]] | A cached `get_settings()` built at startup, `SettingsDep` in routes, sub-models passed below entry points. |
| [[settings-testing]] | Fixtures that build settings from one dict and clear the developer's env vars. |
| [[settings-app]] | App name, production toggle, debug. |
| [[settings-db]] | Connection parts instead of a URL, password auth locally and IAM when deployed, verified TLS, pool. |
| [[settings-db-iam-auth]] | Builds on [[settings-db]]: a fresh IAM token per connection through `do_connect`. |
| [[settings-auth-cognito]] | Public values to verify Cognito access tokens (`client_id`, `token_use`), no secrets. |
| [[settings-cors]] | Exact origins validated at startup, set in the app only. |
| [[settings-feature-flags]] | Static typed flags, default off, passed into services. |
| [[settings-aws-sources]] | Secrets Manager and Parameter Store as pydantic-settings sources, added only when configured. |
| [[settings-refreshing-values]] | Settings stay frozen; individual live values come from a stampede-safe TTL cache. |
