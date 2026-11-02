---
title: "Refreshing settings values"
category: project-structure
tags: [settings, caching, secrets-rotation, feature-flags]
status: draft
related: ["[[0-settings-guide]]", "[[1e-settings-lambda]]", "[[4a-settings-refreshing-values-ttl]]", "[[4a-settings-refreshing-values-cache]]", "[[2b-settings-db-rotated-password]]", "[[2f-settings-feature-flags-appconfig]]"]
---

# Refreshing settings values

## Problem
`Settings` is read once and frozen. Some values change while the app runs: Secrets Manager rotates the DB password, an operator flips a kill switch, a feature rolls out gradually. Without a refresh mechanism these changes need new execution environments (a new deploy), and a rotated password breaks new DB connections until then.

## Use when
- A secret the app reads is rotated automatically by Secrets Manager.
- A flag must change within minutes without a deploy: kill switches, gradual rollouts.

## Avoid when
- A redeploy is acceptable. **Publishing a new version and shifting the `live` alias to it is the default way to reload settings** ([[1d-settings-deployments]]): simple, every value is validated together at init, and a bad value is rolled back. Use these notes only for values that can't wait.

## Solution

| Need | Note | How |
|---|---|---|
| Reload all config periodically, small app | [[4a-settings-refreshing-values-ttl]] | `get_settings()` with a TTL cache instead of `lru_cache` |
| Refresh individual values from AWS | [[4a-settings-refreshing-values-cache]] | A thread-safe TTL cache client in `clients/` |
| DB password rotated by Secrets Manager | [[2b-settings-db-rotated-password]] | Current password per new connection, built on the value cache |
| Kill switches, gradual rollouts | [[2f-settings-feature-flags-appconfig]] | Typed flags from AWS AppConfig Agent |

Rebuilding all settings vs. refreshing individual values:

| | Rebuild all settings | Refresh individual values |
|---|---|---|
| What refreshes | The whole `Settings` object | Only the values that need it |
| Code | One decorator | A small cache client per source |
| Startup objects (engine, CORS, mounted routers) | Keep old values | Unaffected, by design |
| When a refresh fails | Every request fails, each retrying the full rebuild, until the sources recover | Serves the last good value and retries after a backoff |
| Best for | Small apps, rarely changing config | Rotated secrets, runtime flags |

On Lambda both caches live per execution environment, and each new environment reads fresh values at init anyway ([[1e-settings-lambda]]). A refresh only matters for environments that stay warm longer than the value may stay stale.

## Pitfalls
- **Refreshing what a redeploy would handle.** Every refreshed value is one more thing that can change mid-request. Default to a new version.
- **Assuming the CodeDeploy canary covers runtime changes.** It shifts traffic between Lambda versions; refreshed values and runtime flags reach every version at once. Roll them out gradually with AppConfig ([[1d-settings-deployments-appconfig-rollouts]]).
- **Async code with these clients.** They are synchronous and use thread locks, matching plain `def` endpoints. In `async def` code they would block the event loop.

## Related
- [[0-settings-guide]]
- [[1e-settings-lambda]]
- [[4a-settings-refreshing-values-ttl]]
- [[4a-settings-refreshing-values-cache]]
- [[2b-settings-db-rotated-password]]
- [[2f-settings-feature-flags-appconfig]]
