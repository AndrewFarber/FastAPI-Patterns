---
title: "App settings"
category: project-structure
related:
  - "[[settings-guide]]"
  - "[[settings-management]]"
---

# App settings

## Overview
App-wide values (name, production toggle, debug) get their own `AppSettings` sub-model like any other concern, instead of flat fields on the root class or hard-coded strings.

## Rules
- **`is_prd` is a bool, not an environment name.** It switches on the production checks on the root `Settings` (no debug, no wildcard CORS, no password DB auth; [[settings-management]]); anything that differs per stage is its own setting.

## Code example
```python
# app/core/config/app.py
from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "shop-api"
    is_prd: bool = False
    debug: bool = False
```
