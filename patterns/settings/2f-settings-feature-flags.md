---
title: "Feature flag settings"
category: project-structure
tags: [settings, feature-flags]
status: draft
related: ["[[1a-settings-management]]", "[[4a-settings-refreshing-values]]"]
---

# Feature flag settings

Static flags are typed bools on `FeatureSettings`, default off, changed by redeploying. Whole features are gated by mounting their router; behavior inside a feature by passing `FeatureSettings` into the service.

## Fits when
- A feature should be on in some environments and off in others.

Not when:
- It must change without a redeploy (kill switches, gradual rollouts): a flag service, not settings ([[4a-settings-refreshing-values]]).

## Signals
- **Feature:** "ship it turned off", "enable only in staging".
- **Code:** `if os.getenv("NEW_CHECKOUT")`; string lookups like `is_enabled("new_checkout")`; flags read from global settings inside a service; flag checks inside every route of a feature instead of one `include_router`.

## Pattern
```python
# app/config/features.py
from pydantic import BaseModel, ConfigDict


class FeatureSettings(BaseModel):
    """Static feature flags: fixed for the life of the process, changed by redeploying."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # One bool per feature, named for the feature, default off
    new_checkout: bool = False       # services: switch to the new checkout flow
    bulk_export: bool = False        # main.py: mount the /exports router
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

    def checkout(self, cart: Cart) -> Order:
        if self.features.new_checkout:
            return self._checkout_v2(cart)
        return self._checkout_v1(cart)
```

## Rules
- **One bool per feature, named for it, default off.** A missing env var never releases a feature.
- **Typed attributes, not string lookups.** The type checker catches `new_chekout`.
- **Pass `FeatureSettings` in.** The service gets only flags, and tests build `FeatureSettings(new_checkout=True)`.

## Anti-patterns
- **Flags that never die.** Once released, delete the field, the env var, and the old path together.
- **Operational toggles as static flags.** A kill switch that needs a redeploy is too slow when it's needed.

## Related
- [[1a-settings-management]]
- [[4a-settings-refreshing-values]]
