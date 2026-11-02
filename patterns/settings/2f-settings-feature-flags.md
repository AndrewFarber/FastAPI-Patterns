---
title: "Feature flag settings"
category: project-structure
tags: [settings, feature-flags]
status: draft
related: ["[[1a-settings-management]]", "[[1e-settings-lambda]]", "[[2f-settings-feature-flags-appconfig]]"]
---

# Feature flag settings

## Problem
Unfinished or risky features need to ship turned off and be turned on per environment. Ad hoc `if os.getenv("NEW_CHECKOUT")` checks are untyped, scattered, and never cleaned up.

## Use when
- A feature should be on in some environments and off in others, changed by redeploying.

## Avoid when
- The flag must change without a redeploy (kill switches, gradual rollouts). Use runtime flags from AWS AppConfig; see [[2f-settings-feature-flags-appconfig]].

## Solution
```python
# app/config/features.py
from pydantic import BaseModel, ConfigDict


class RuntimeFlagsSource(BaseModel):
    """Where AppConfig Agent finds the runtime flags (2f-settings-feature-flags-appconfig)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    application: str
    environment: str                 # the AppConfig environment ("dev", "staging", "prd"): set per stage, not derived
    profile: str = "runtime-flags"


class FeatureSettings(BaseModel):
    """Static feature flags: fixed for the life of the process, changed by redeploying."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # One bool per feature, named for the feature, default off
    new_checkout: bool = False       # services: switch to the new checkout flow
    bulk_export: bool = False        # main.py: mount the /exports router
    # A handful of user IDs that see beta features early. Env vars share 4 KB on Lambda:
    # longer lists belong in AppConfig or Parameter Store.
    beta_users: frozenset[str] = frozenset()

    # Runtime flags from AppConfig; None (local dev, no agent) = runtime flags keep their defaults
    runtime_flags: RuntimeFlagsSource | None = None
```

```bash
FEATURES__NEW_CHECKOUT=true
FEATURES__BETA_USERS='["user-123","user-456"]'
```

Two ways to use a flag:

```python
# main.py (fragment): whole endpoints. When the flag is off, the routes don't exist (404, absent from OpenAPI docs)
if settings.features.bulk_export:
    app.include_router(exports.router)
```

```python
# services/checkout.py (fragment): behavior inside an endpoint
class CheckoutService:
    def __init__(self, features: FeatureSettings) -> None:
        self.features = features

    def checkout(self, user_id: str, cart: Cart) -> Order:
        if self.features.new_checkout or user_id in self.features.beta_users:
            return self._checkout_v2(cart)
        return self._checkout_v1(cart)
```

- **Pass `FeatureSettings` in, don't import settings.** The service gets only the flags it needs, and tests construct it with `FeatureSettings(new_checkout=True)`.
- **Typed attributes, not string lookups.** `features.new_checkout` is checked by the type checker and autocompleted; `is_enabled("new_chekout")` fails silently.
- **`beta_users` is a `frozenset`:** membership checks are constant time, and the frozen model stays immutable. The env var is still a JSON list.
- **Changed by redeploying,** which on Lambda means publishing a new version: the env vars are frozen into it ([[1e-settings-lambda]]).
- `runtime_flags` says where AppConfig Agent finds the runtime flags; see [[2f-settings-feature-flags-appconfig]].

## Pitfalls
- **Flags that never die.** Once a feature is fully released, delete the field, the env var, and the old code path together.
- **Defaults that turn features on.** Every flag defaults to off, so a missing env var never releases a feature.
- **Long ID lists in env vars.** All of a Lambda function's env vars share 4 KB. Keep `beta_users` to a handful of IDs; larger cohorts belong in AppConfig or a user attribute.

## Related
- [[1a-settings-management]]
- [[1e-settings-lambda]]
- [[2f-settings-feature-flags-appconfig]]
