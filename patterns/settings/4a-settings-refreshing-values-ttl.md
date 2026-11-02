---
title: "Rebuilding settings on a TTL"
category: project-structure
tags: [settings, caching]
status: draft
related: ["[[4a-settings-refreshing-values]]", "[[1b-settings-access]]", "[[3b-settings-aws-sources]]"]
---

# Rebuilding settings on a TTL

Swap `lru_cache` on `get_settings()` for a TTL cache: the whole `Settings` is rebuilt every few minutes, with one line of code.

## Fits when
- A small app reads settings per request through `SettingsDep` (approach 2 in [[1b-settings-access]]) and can tolerate requests failing while a rebuild fails.

Not when:
- The value is used by startup objects (engine, middleware, mounted routers): they never see it.
- Settings come from `app.state` or a module singleton.
- Only one or two values change: [[4a-settings-refreshing-values-cache]].

## Signals
- **Feature:** "reload config every few minutes".
- **Code:** `@lru_cache` on `get_settings()` plus a request to pick up Parameter Store changes; a custom thread that rebuilds settings.

## Pattern
```python
# app/config/settings.py (fragment)
from cachetools.func import ttl_cache


@ttl_cache(maxsize=1, ttl=300)       # was @lru_cache: rebuilt every 5 minutes
def get_settings() -> Settings:
    return Settings()
```

## Rules
- **Only per-request readers see new values.**
- **Every rebuild re-reads every source,** AWS ones included ([[3b-settings-aws-sources]]); keep the TTL in minutes.
- **Tests still call `get_settings.cache_clear()`.**

## Anti-patterns
- **Expecting startup objects to update.**
- **Assuming a failed rebuild is cached.** `ttl_cache` doesn't cache exceptions: while AWS is down, every request fails and retries the whole rebuild.

## Related
- [[4a-settings-refreshing-values]]
- [[1b-settings-access]]
- [[3b-settings-aws-sources]]
