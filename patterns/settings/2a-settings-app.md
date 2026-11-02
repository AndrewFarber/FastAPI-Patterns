---
title: "App settings"
category: project-structure
tags: [settings]
status: draft
related: ["[[1a-settings-management]]", "[[2a-settings-app-build-metadata]]"]
---

# App settings

## Problem
Every app has app-wide values: its name, whether it runs in production, debug mode. Without a home, these end up as flat fields on the root class or as hard-coded strings.

## Use when
- Always: every app has an `AppSettings` sub-model.

## Avoid when
- Never.

## Solution
```python
# app/config/app.py (fragment: the full file is in 2a-settings-app-build-metadata)
from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "orders-api"
    is_prd: bool = False
    debug: bool = False
```

- `is_prd` turns on the production checks on the root `Settings` class (no debug, no wildcard CORS); see [[1a-settings-management]].
- **Which build is running** (version, git SHA, build time): [[2a-settings-app-build-metadata]], which shows the full `app/config/app.py`.

## Pitfalls
- **`debug=True` in production.** FastAPI then returns tracebacks to clients. The root validator rejects it when `is_prd` is set.

## Related
- [[1a-settings-management]]
- [[2a-settings-app-build-metadata]]
