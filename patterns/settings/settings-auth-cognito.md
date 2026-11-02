---
title: "Auth settings for AWS Cognito"
category: auth-security
related:
  - "[[settings-guide]]"
  - "[[layout-core]]"
---

# Auth settings for AWS Cognito

## Overview
Users sign in through a Cognito user pool; the API keeps only the *public* values needed to verify Cognito's access tokens: issuer, JWKS URL, the app clients allowed to call it, required claims, algorithms. No secrets, so plain env vars are fine.

## Rules
- **No secrets.** Cognito signs with its private keys; every field is public.
- **Exact issuer as `str`.** `iss` must match character for character; `HttpUrl` adds or keeps a trailing slash. The issuer is `https://cognito-idp.<region>.amazonaws.com/<user pool ID>`.
- **`audience_claim=client_id`:** Cognito access tokens have no `aud` by default. `audiences` lists only the app clients allowed to call this API (`min_length=1`).
- **`token_use: access`** rejects ID tokens from the same client.
- **With resource indicators** (clients send `resource`), Cognito sets `aud`: drop `AUTH__AUDIENCE_CLAIM` and list the API's identifier. Switch only once every client sends it.
- **Asymmetric algorithms only,** enforced by the `Literal`; Cognito uses `RS256`, the default.
- **HTTPS only,** enforced by the validator.
- **Cache the JWKS** (the default `{issuer}/.well-known/jwks.json`) for `jwks_cache_ttl_seconds`; refetch early only for an unknown `kid`. Fetch lazily on the first request, not at startup, so a slow provider can't fail startup.
- **Every route but `/healthz` depends on verification** when nothing in front of the app checks tokens. The `shop-api` example leaves verification out to stay small, so its routes are unauthenticated.

## Code example
```python
# app/core/config/auth.py
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer: str
    jwks_url: str | None = None

    audiences: list[str] = Field(min_length=1)
    audience_claim: str = "aud"
    required_claims: dict[str, str] = {}

    algorithms: list[Literal["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]] = ["RS256"]
    leeway_seconds: int = Field(default=30, ge=0, le=300)
    jwks_cache_ttl_seconds: int = Field(default=3600, gt=0)

    @model_validator(mode="after")
    def check_https(self) -> Self:
        for name, url in (("issuer", self.issuer), ("jwks_url", self.jwks_url)):
            if url is not None and not url.startswith("https://"):
                raise ValueError(f"{name} must use https")
        return self

    @property
    def resolved_jwks_url(self) -> str:
        return self.jwks_url or f"{self.issuer.rstrip('/')}/.well-known/jwks.json"
```

```bash
AUTH__ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz
AUTH__AUDIENCES='["1example23456789"]'
AUTH__AUDIENCE_CLAIM=client_id
AUTH__REQUIRED_CLAIMS='{"token_use": "access"}'
```

Verification itself lives in `core/auth/` and is handed to routes by `core/dependencies/` ([[layout-core]]).
