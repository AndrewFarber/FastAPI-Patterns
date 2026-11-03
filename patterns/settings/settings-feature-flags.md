---
title: "Feature flag settings"
category: project-structure
related:
  - "[[settings-guide]]"
  - "[[settings-access]]"
---

# Feature flag settings

## Overview
Static flags are typed bools on `FeaturesSettings`, default off, changed by redeploying. Whole features are gated by mounting their router; behavior inside a feature by passing `FeaturesSettings` into the use case.

## Rules
- **One bool per feature, named for it, default off.** A missing env var never releases a feature.
- **Typed attributes, not string lookups.** The type checker catches `new_chekout`.
- **Pass `FeaturesSettings` in.** Only entry points read `Settings` ([[settings-access]]); the use case gets only flags, and its tests build `FeaturesSettings(new_checkout=True)`.

## Code example
```python
# app/core/config/features.py
from pydantic import BaseModel, ConfigDict


class FeaturesSettings(BaseModel):
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
def post_order_checkout(
    body: CheckoutIn, order_repository: OrderRepositoryDep, settings: SettingsDep
) -> OrderRead:
    order = checkout(
        CheckoutCommand(cart_id=body.cart_id), order_repository, settings.features
    )
    return OrderRead(id=order.id, user_id=order.user_id, item=order.item, status=order.status)
```

```python
# app/services/orders/use_cases/checkout.py (fragment)
def checkout(
    command: CheckoutCommand,
    order_repository: OrderRepository,
    features: FeaturesSettings,
) -> Order:
    if features.new_checkout:
        return _checkout_v2(command, order_repository)
    return _checkout_v1(command, order_repository)
```
