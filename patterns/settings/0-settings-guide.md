---
title: "Settings guide"
category: project-structure
tags: [settings, guide]
status: draft
related: ["[[1a-settings-management]]"]
---

# Settings guide

General notes come first; indented notes build on the note above them. [[1a-settings-management]] is the base for all of them.

The examples run on AWS Lambda as a container image behind the Lambda Web Adapter. Each note states the few rules that change on Lambda; the patterns apply to any server.

## 1. Core
- [[1a-settings-management]]: one `config/` package, a frozen sub-model per concern, a root `Settings` that only composes.
- [[1b-settings-access]]: creating and reading settings: singleton, cached function + `Depends` (default), or app factory; built at startup.
- [[1c-settings-testing]]: fixtures that build settings from one dict and clear the developer's env vars.
- [[1d-settings-deployments]]: two versions running at once: tag logs with an immutable version, change shared config by expand-then-contract.

## 2. Sub-models
- [[2a-settings-app]]: app name, production toggle, debug.
    - [[2a-settings-app-build-metadata]]: version, git SHA, build time baked in at build.
- [[2b-settings-db]]: connection parts instead of a URL, auth as a discriminated union, verified TLS, pool.
    - [[2b-settings-db-iam-auth]]: a fresh IAM token per connection through `do_connect`.
    - [[2b-settings-db-rotated-password]]: the current rotated password per connection, retried once.
- [[2c-settings-auth]]: provider-agnostic JWT verification values, no secrets.
    - [[2c-settings-auth-cognito]]: Cognito access tokens (`client_id`, `token_use`).
- [[2d-settings-cors]]: exact origins validated at startup, set in the app only.
- [[2e-settings-email]]: an optional subsystem with cross-field validation.
- [[2f-settings-feature-flags]]: static typed flags, default off, passed into services.
    - [[2f-settings-feature-flags-appconfig]]: runtime flags from AppConfig Agent, failing safe.

## 3. Sources
- [[3a-settings-secret-files]]: secrets as files for local docker-compose, added only when configured.
- [[3b-settings-aws-sources]]: Secrets Manager and Parameter Store as pydantic-settings sources, added only when configured.

## 4. Values that change at runtime
- [[4a-settings-refreshing-values]]: refresh instead of redeploy, and which option to use.
    - [[4a-settings-refreshing-values-ttl]]: rebuild all settings on a TTL.
    - [[4a-settings-refreshing-values-cache]]: a stampede-safe TTL cache for individual live values.

## Related
- [[1a-settings-management]]
