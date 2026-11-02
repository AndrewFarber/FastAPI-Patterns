---
title: "Rebuilding settings on a TTL"
category: project-structure
tags: [settings, caching]
status: draft
related: ["[[4a-settings-refreshing-values]]", "[[1b-settings-access]]", "[[1e-settings-lambda]]", "[[3b-settings-aws-sources-pydantic]]"]
---

# Rebuilding settings on a TTL

## Problem
Configuration in AWS changes occasionally, and the app should pick it up within minutes without a redeploy, with the least possible code.

## Use when
- A small app reads its settings per request through `SettingsDep` (approach 2 in [[1b-settings-access]]) and can tolerate requests failing while a refresh fails.

## Avoid when
- The value is used by objects built at startup (the DB engine, middleware, mounted routers): they never see the new value.
- Settings are reached through `app.state.settings` or a module singleton (approaches 1 and 3): the TTL only replaces what `get_settings()` returns.
- Only one or two values change. Refresh them individually with [[4a-settings-refreshing-values-cache]].

## Solution
Replace `lru_cache` on `get_settings()` (approach 2 in [[1b-settings-access]]) with a TTL cache:

```python
# config/settings.py (fragment)
from cachetools.func import ttl_cache


@ttl_cache(maxsize=1, ttl=300)       # was @lru_cache: rebuilt every 5 minutes
def get_settings() -> Settings:
    return Settings()
```

- Every rebuild re-reads all sources, including the AWS sources from [[3b-settings-aws-sources-pydantic]].
- Only code that calls `get_settings()` (or `SettingsDep`) per request sees new values.
- Tests still call `get_settings.cache_clear()`.
- On Lambda the cache lives per execution environment and the TTL counts from that environment's init ([[1e-settings-lambda]]). An environment younger than the TTL never rebuilds.

## Pitfalls
- **Expecting startup objects to update.** The engine, CORS middleware, and routers mounted by flags were built once; rebuilding `Settings` doesn't touch them.
- **Failing requests on refresh errors.** A rebuild runs inside the request that hits the expired cache, and `ttl_cache` doesn't cache exceptions. If AWS is down or a value is invalid, every request fails and retries the full rebuild, AWS calls included, until the sources recover. If that's not acceptable, refresh the values individually ([[4a-settings-refreshing-values-cache]]).
- **Short TTLs with AWS sources.** Each rebuild makes AWS API calls, with cost and throttling limits, and every warm execution environment rebuilds on its own.

## Related
- [[4a-settings-refreshing-values]]
- [[1b-settings-access]]
- [[1e-settings-lambda]]
- [[3b-settings-aws-sources-pydantic]]
