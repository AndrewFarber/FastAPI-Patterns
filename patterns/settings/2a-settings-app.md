---
title: "App settings"
category: project-structure
tags: [settings]
status: draft
related: ["[[1a-settings-management]]"]
---

# App settings

App-wide values (name, production toggle, debug) get their own `AppSettings` sub-model like any other concern, instead of flat fields on the root class or hard-coded strings.

## Fits when
- Always: every app has an `AppSettings`.

## Signals
- **Feature:** "prod-only check", "debug mode", the app's name in logs or `pg_stat_activity`.
- **Code:** `ENV == "production"` string comparisons; `debug=True` passed to `FastAPI()` literally; fields like `app_name` or `environment` directly on the root `Settings`.

## Pattern
```python
# app/core/config/app.py
from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "shop-api"
    is_prd: bool = False
    debug: bool = False
```

## Rules
- **`is_prd` is a bool, not an environment name.** It switches on the production checks on the root `Settings` (no debug, no wildcard CORS, [[1a-settings-management]]); anything that differs per stage is its own setting.

## Anti-patterns
- **`debug=True` in production.** FastAPI returns tracebacks to clients; the root validator rejects it.
- **Deriving other values from `is_prd`.** `"prd" if is_prd else "dev"` points staging at dev's resources.

## Related
- [[1a-settings-management]]
