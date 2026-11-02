---
title: "CORS settings"
category: auth-security
tags: [settings, cors, security]
status: draft
related: ["[[1a-settings-management]]", "[[1b-settings-access]]"]
---

# CORS settings

Allowed origins are a validated list in settings, empty by default, applied by the app's middleware and nowhere else. A malformed origin or wildcard-with-credentials fails at startup.

## Fits when
- Browsers call the API from another origin (a separate frontend domain or port).

Not when:
- Only servers or mobile apps call it: leave the list empty.

## Signals
- **Feature:** "the frontend gets a CORS error", adding a frontend domain.
- **Code:** `allow_origins=["*"]` with `allow_credentials=True`; origins hard-coded in `main.py`; origins with a trailing slash or path; CORS configured in a gateway or Function URL *and* the app.

## Pattern
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
# app/main.py (fragment: the full file is in 1b-settings-access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
    allow_credentials=settings.cors.allow_credentials,
)
```

## Rules
- **Origins are plain `str`, validated as `scheme://host[:port]`:** exactly what browsers send in `Origin`. `HttpUrl` would add a trailing slash.
- **Empty by default:** no cross-origin access until configured.
- **No wildcard with credentials** (validator), and no wildcard in production (root validator, [[1a-settings-management]]).
- **One place only.** A gateway or Lambda Function URL CORS config answers preflights itself and duplicates headers, which browsers reject.

## Anti-patterns
- **Trailing slashes.** `https://app.example.com/` never matches.
- **Expecting CORS to protect the API.** It only restricts browsers; authentication still applies.

## Related
- [[1a-settings-management]]
- [[1b-settings-access]]
