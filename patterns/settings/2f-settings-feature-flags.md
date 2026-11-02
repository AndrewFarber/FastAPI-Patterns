---
title: "Feature flag settings"
category: project-structure
tags: [settings, feature-flags]
status: draft
related: ["[[1a-settings-management]]", "[[1b-settings-access]]", "[[4a-settings-refreshing-values]]"]
---

# Feature flag settings

Static flags are typed bools on `FeatureSettings`, default off, changed by redeploying. Whole features are gated by mounting their router; behavior inside a feature by passing `FeatureSettings` into the use case.

## Fits when
- A feature should be on in some environments and off in others.

Not when:
- It must change without a redeploy (kill switches, gradual rollouts): a flag service, not settings ([[4a-settings-refreshing-values]]).

## Signals
- **Feature:** "ship it turned off", "enable only in staging".
- **Code:** `if os.getenv("NEW_CHECKOUT")`; string lookups like `is_enabled("new_checkout")`; `get_settings()` inside a use case; flag checks inside every route of a feature instead of one `include_router`.

## Pattern
```python
# app/core/config/features.py
from pydantic import BaseModel, ConfigDict


class FeatureSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    new_checkout: bool = False
    bulk_export: bool = False
```

Whole endpoints: `create_app()` mounts the router only when the flag is on, so the routes don't exist when it's off (404, absent from OpenAPI):

```python
# app/main.py (fragment)
if settings.features.bulk_export:
    app.include_router(exports_router)
```

Behavior inside an endpoint: the route reads the flags from `SettingsDep` and passes them to the use case, which never reads settings itself:

```python
# app/services/orders/api/router.py (fragment)
@router.post("/checkout", status_code=201)
def post_checkout(body: CheckoutIn, orders: OrderRepositoryDep, settings: SettingsDep) -> OrderOut:
    order = checkout(Checkout(cart_id=body.cart_id), orders, settings.features)
    return OrderOut.from_order(order)
```

```python
# app/services/orders/use_cases/checkout.py (fragment)
def checkout(command: Checkout, orders: OrderRepository, features: FeatureSettings) -> Order:
    if features.new_checkout:
        return _checkout_v2(command, orders)
    return _checkout_v1(command, orders)
```

## Rules
- **One bool per feature, named for it, default off.** A missing env var never releases a feature.
- **Typed attributes, not string lookups.** The type checker catches `new_chekout`.
- **Pass `FeatureSettings` in.** Only entry points read `Settings` ([[1b-settings-access]]); the use case gets only flags, and its tests build `FeatureSettings(new_checkout=True)`.

## Anti-patterns
- **Flags that never die.** Once released, delete the field, the env var, and the old path together.
- **Operational toggles as static flags.** A kill switch that needs a redeploy is too slow when it's needed.

## Related
- [[1a-settings-management]]
- [[1b-settings-access]]
- [[4a-settings-refreshing-values]]
