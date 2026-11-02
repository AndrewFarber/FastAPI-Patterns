---
title: "Auth settings for AWS Cognito"
category: auth-security
tags: [settings, authentication, cognito, jwt]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1b-layout-core]]"]
---

# Auth settings for AWS Cognito

Users sign in through a Cognito user pool; the API keeps only the *public* values needed to verify Cognito's access tokens: issuer, JWKS URL, the app clients allowed to call it, required claims, algorithms. No secrets, so plain env vars are fine.

## Fits when
- Users sign in through a Cognito user pool and the API verifies Cognito access tokens itself.

Not when:
- The app issues its own tokens: that needs a signing key and is a different pattern.
- API Gateway with a Cognito or JWT authorizer already verifies them and forwards trusted claims.

## Signals
- **Feature:** "Cognito", "user pool", "add login", "protect the endpoints", "verify JWTs".
- **Code:** `jwt_secret` or `SECRET_KEY` next to Cognito; `algorithms=["HS256"]`; `verify_aud=False` / `options={"verify_aud": False}` for Cognito tokens; no `token_use` check; the JWKS fetched per request; issuer typed as `HttpUrl`.

## Pattern
```python
# app/config/auth.py
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthSettings(BaseModel):
    """Values needed to verify JWTs from an external identity provider. No secrets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Exact "iss" claim. Plain str, not HttpUrl: the match is exact, and HttpUrl
    # would add or keep a trailing slash that the provider may not use.
    issuer: str
    # Where the provider publishes its public signing keys. Defaults to the
    # common {issuer}/.well-known/jwks.json; some providers use another path.
    jwks_url: str | None = None

    # Who the token must be issued for: API identifiers or app client IDs
    audiences: list[str] = Field(min_length=1)
    # The claim that holds the audience. "aud" for most providers.
    audience_claim: str = "aud"
    # Extra claims that must match exactly, e.g. {"token_use": "access"}
    required_claims: dict[str, str] = {}

    # Asymmetric algorithms only: never "none" or HS256 for provider-issued tokens
    algorithms: list[Literal["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]] = ["RS256"]
    leeway_seconds: int = Field(default=30, ge=0, le=300)   # clock skew allowed on exp/nbf
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

Verification itself lives in `security/` (pure helpers) and is handed to routes by `dependencies/` ([[1b-layout-core]]).

## Rules
- **No secrets.** Cognito signs with its private keys; every field is public.
- **Exact issuer as `str`.** `iss` must match character for character; `HttpUrl` adds or keeps a trailing slash. The issuer is `https://cognito-idp.<region>.amazonaws.com/<user pool ID>`.
- **`audience_claim=client_id`:** Cognito access tokens have no `aud` by default. `audiences` lists only the app clients allowed to call this API (`min_length=1`).
- **`token_use: access`** rejects ID tokens from the same client.
- **With resource indicators** (clients send `resource`), Cognito sets `aud`: drop `AUTH__AUDIENCE_CLAIM` and list the API's identifier. Switch only once every client sends it.
- **Asymmetric algorithms only,** enforced by the `Literal`; Cognito uses `RS256`, the default.
- **HTTPS only,** enforced by the validator.
- **Cache the JWKS** (the default `{issuer}/.well-known/jwks.json`) for `jwks_cache_ttl_seconds`; refetch early only for an unknown `kid`. Fetch lazily on the first request, not at startup, so a slow provider can't fail startup.
- **Every route but `/healthz` depends on verification** when nothing in front of the app checks tokens.

## Anti-patterns
- **A signing secret "just in case".** Dead configuration someone will use.
- **Checking `aud` without resource indicators.** Every token fails, so someone disables the check.
- **Skipping the audience check.** Tokens issued for other app clients pass.
- **Listing every app client in the pool.** Only API callers belong in `audiences`.
- **Accepting ID tokens.** APIs accept access tokens.
- **`HS256` or `none`.** The public key becomes an HMAC secret, or tokens go unsigned.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1b-layout-core]]
