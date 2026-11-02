---
title: "Feature flag settings"
category: project-structure
tags: [settings, feature-flags]
status: draft
related: ["[[1a-settings-management]]", "[[2f-settings-feature-flags-appconfig]]"]
---

# Feature flag settings

Static flags are typed bools on `FeatureSettings`, default off, changed by redeploying. Whole features are gated by mounting their router; behavior inside a feature by passing `FeatureSettings` into the service.

## Fits when
- A feature should be on in some environments and off in others.

Not when:
- It must change without a redeploy (kill switches, gradual rollouts): [[2f-settings-feature-flags-appconfig]].

## Signals
- **Feature:** "ship it turned off", "enable only in staging", "beta users".
- **Code:** `if os.getenv("NEW_CHECKOUT")`; string lookups like `is_enabled("new_checkout")`; flags read from global settings inside a service; flag checks inside every route of a feature instead of one `include_router`.

## Pattern
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

```python
# main.py (fragment): whole endpoints. When off, the routes don't exist (404, absent from OpenAPI)
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

## Rules
- **One bool per feature, named for it, default off.** A missing env var never releases a feature.
- **Typed attributes, not string lookups.** The type checker catches `new_chekout`.
- **Pass `FeatureSettings` in.** The service gets only flags, and tests build `FeatureSettings(new_checkout=True)`.
- **Small ID sets as `frozenset`:** constant-time membership, immutable. Keep them to a handful; larger cohorts belong in AppConfig or a user attribute.

## Anti-patterns
- **Flags that never die.** Once released, delete the field, the env var, and the old path together.
- **Mixing static and runtime flags.** Release toggles here; operational toggles in AppConfig.

## Related
- [[1a-settings-management]]
- [[2f-settings-feature-flags-appconfig]]
