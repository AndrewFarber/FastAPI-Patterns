---
title: "CORS settings"
category: auth-security
tags: [settings, cors, security]
status: draft
related: ["[[1a-settings-management]]", "[[1e-settings-lambda]]"]
---

# CORS settings

## Problem
Browsers block cross-origin requests unless the API allows the caller's origin. Too strict breaks the frontend; too loose (`*` with credentials) lets any site make authenticated requests.

## Use when
- Browsers call the API from a different origin (a separate frontend domain or port).

## Avoid when
- Only servers or mobile apps call the API. CORS is a browser mechanism; leave the list empty.

## Solution
```python
# app/config/cors.py
from typing import Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CorsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Exact origins, e.g. "https://app.example.com". Plain str, not HttpUrl:
    # HttpUrl adds a trailing slash, which never matches the browser's Origin header.
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
            # An Origin header is scheme://host[:port]; anything after it never matches
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
# main.py (fragment: the full app/main.py is in 1b-settings-access)
# CORS is set here only: a Function URL CORS config would replace these headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
    allow_credentials=settings.cors.allow_credentials,
)
```

```bash
CORS__ALLOW_ORIGINS='["https://app.example.com"]'
```

- The default (no origins) is the safe state: no cross-origin access.
- Each origin must be `scheme://host[:port]`, exactly what browsers send in the `Origin` header; a path or trailing slash fails at startup.
- The root `Settings` also rejects `*` in production; see [[1a-settings-management]].
- **One place only.** CORS lives in the app; the Function URL has no CORS config. A Function URL (or API Gateway) CORS config answers preflight requests itself and adds its own headers to the rest ([[1e-settings-lambda]]).

## Pitfalls
- **Wildcard with credentials.** The CORS spec forbids it; the validator rejects it at startup.
- **Trailing slashes.** `https://app.example.com/` never matches the `Origin` header `https://app.example.com`; the validator rejects it.
- **CORS on both the Function URL and the app.** The app's settings stop taking effect for preflights, and other responses get duplicate `Access-Control-Allow-Origin` headers, which browsers reject.
- **Expecting CORS to protect the API.** It only restricts browsers; other clients ignore it. Authentication still applies.

## Related
- [[1a-settings-management]]
- [[1e-settings-lambda]]
