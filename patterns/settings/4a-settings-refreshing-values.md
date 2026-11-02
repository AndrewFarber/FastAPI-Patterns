---
title: "Refreshing settings values"
category: project-structure
tags: [settings, caching, secrets-rotation, feature-flags]
status: draft
related: ["[[0-settings-guide]]", "[[1d-settings-deployments]]", "[[4a-settings-refreshing-values-ttl]]", "[[4a-settings-refreshing-values-cache]]", "[[2b-settings-db-rotated-password]]", "[[2f-settings-feature-flags-appconfig]]"]
---

# Refreshing settings values

`Settings` stays frozen. A redeploy is the default way to change a value; only values that can't wait for one get a refresh mechanism, chosen by what must refresh.

## Fits when
- A secret rotates automatically, or a flag must change within minutes without a deploy.

Not when:
- A redeploy is acceptable. It validates every value together and rolls back a bad one ([[1d-settings-deployments]]).

## Signals
- **Feature:** "pick up the new value without a restart", "rotation", "kill switch".
- **Code:** mutating settings (`settings.x = ...`, `object.__setattr__`); a background thread rebuilding settings; values fetched from AWS on every request without a cache.

## Pattern
| Need | Note |
|---|---|
| Reload all config periodically, small app | [[4a-settings-refreshing-values-ttl]] |
| Refresh individual values from AWS | [[4a-settings-refreshing-values-cache]] |
| DB password rotated by Secrets Manager | [[2b-settings-db-rotated-password]] |
| Kill switches, gradual rollouts | [[2f-settings-feature-flags-appconfig]] |

| | Rebuild all settings | Refresh individual values |
|---|---|---|
| Code | One decorator | A small cache client per source |
| Startup objects (engine, CORS, routers) | Keep old values | Unaffected, by design |
| When a refresh fails | Requests fail until the sources recover | Last good value, retry after a backoff |

## Rules
- **Never mutate settings.** Refresh by replacing what `get_settings()` returns, or by reading the value from a cache client.
- **Caches live per process** (on Lambda, per instance); each new instance reads fresh values anyway.
- **Runtime changes reach every running version at once,** so roll them out with AppConfig, not the app's canary.

## Anti-patterns
- **Refreshing what a redeploy would handle.** One more thing that can change mid-request.
- **These clients in `async def` code.** They are synchronous with thread locks and would block the event loop.

## Related
- [[0-settings-guide]]
- [[1d-settings-deployments]]
- [[4a-settings-refreshing-values-ttl]]
- [[4a-settings-refreshing-values-cache]]
- [[2b-settings-db-rotated-password]]
- [[2f-settings-feature-flags-appconfig]]
