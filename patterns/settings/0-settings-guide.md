---
title: "Settings guide"
category: project-structure
tags: [settings, guide]
status: draft
related: ["[[1a-settings-management]]"]
---

# Settings guide

General notes come first; indented notes build on the note above them. [[1a-settings-management]] is the base for all of them.

## 1. Core
- [[1a-settings-management]]: one `core/config/` package, a frozen sub-model per concern, a root `Settings` that only composes.
- [[1b-settings-access]]: creating and reading settings: singleton, cached function + `Depends` (default), or app factory; built at startup.
- [[1c-settings-testing]]: fixtures that build settings from one dict and clear the developer's env vars.

## 2. Sub-models
- [[2a-settings-app]]: app name, production toggle, debug.
- [[2b-settings-db]]: connection parts instead of a URL, auth as a discriminated union, verified TLS, pool.
    - [[2b-settings-db-iam-auth]]: a fresh IAM token per connection through `do_connect`.
    - [[2b-settings-db-rotated-password]]: the current rotated password per connection, retried once.
- [[2c-settings-auth-cognito]]: public values to verify Cognito access tokens (`client_id`, `token_use`), no secrets.
- [[2d-settings-cors]]: exact origins validated at startup, set in the app only.
- [[2f-settings-feature-flags]]: static typed flags, default off, passed into services.

## 3. Sources
- [[3b-settings-aws-sources]]: Secrets Manager and Parameter Store as pydantic-settings sources, added only when configured.

## 4. Values that change at runtime
- [[4a-settings-refreshing-values]]: refresh instead of redeploy, and which option to use.
    - [[4a-settings-refreshing-values-ttl]]: rebuild all settings on a TTL.
    - [[4a-settings-refreshing-values-cache]]: a stampede-safe TTL cache for individual live values.

## Related
- [[1a-settings-management]]
