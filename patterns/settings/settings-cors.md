---
title: "CORS settings"
category: auth-security
related:
  - "[[settings-guide]]"
  - "[[settings-management]]"
---

# CORS settings

## Overview
Allowed origins are a validated list in settings, empty by default, applied by the app's middleware and nowhere else. A malformed origin or wildcard-with-credentials fails at startup.

## Rules
- **Origins are plain `str`, validated as `scheme://host[:port]`:** exactly what browsers send in `Origin`. `HttpUrl` would add a trailing slash.
- **Empty by default:** no cross-origin access until configured.
- **No wildcard with credentials** (validator), and no wildcard in production (root validator, [[settings-management]]).
- **One place only.** A gateway's CORS config answers preflights itself and overrides the app's headers, so the app's list silently stops applying.

## Code example
```python
# app/core/config/cors.py
from typing import Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CorsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_origins: list[str] = []
    allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    allow_headers: list[str] = ["Authorization", "Content-Type"]
    allow_credentials: bool = False

    @field_validator("allow_origins")
    @classmethod
    def check_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            if origin == "*":
                continue
            parts = urlsplit(origin)
            if parts.scheme not in ("http", "https") or not parts.netloc or origin != f"{parts.scheme}://{parts.netloc}":
                raise ValueError(f"{origin!r} is not an origin like 'https://app.example.com' (no path or trailing slash)")
        return origins

    @model_validator(mode="after")
    def check_credentials(self) -> Self:
        if self.allow_credentials and "*" in self.allow_origins:
            raise ValueError("allow_credentials can't be combined with a wildcard origin")
        return self
```

```python
# app/main.py (fragment: the full file is in settings-access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
    allow_credentials=settings.cors.allow_credentials,
)
```
