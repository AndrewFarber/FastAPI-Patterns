---
title: "Auth settings"
category: auth-security
tags: [settings, authentication, oidc, jwt]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[2c-settings-auth-cognito]]", "[[layout-by-layer]]"]
---

# Auth settings

Delegate sign-in to an identity provider and keep only the *public* values needed to verify its JWTs: issuer, JWKS URL, audiences, required claims, asymmetric algorithms. The same model fits every OIDC provider; switching providers changes env vars only.

## Fits when
- Users sign in through an OIDC / OAuth 2.0 provider (Cognito, Auth0, Okta, Entra ID, Keycloak) and the API verifies its access tokens.

Not when:
- The app issues its own tokens: that needs a signing key and is a different pattern.
- A gateway already verifies tokens and forwards trusted claims (API Gateway with a JWT authorizer). A Lambda Function URL is not such a gateway.

## Signals
- **Feature:** "add login", "protect the endpoints", "verify JWTs", switching identity providers.
- **Code:** `jwt_secret` or `SECRET_KEY` with an external provider; `algorithms=["HS256"]` or `verify_aud=False` / `options={"verify_aud": False}`; the JWKS fetched per request; issuer typed as `HttpUrl`.

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

Verification itself lives in `security/` (pure helpers) and is handed to routes by `dependencies/` ([[layout-by-layer]]).

## Rules
- **No secrets.** The provider signs with its private keys; every field is public, so plain env vars are fine.
- **Exact issuer as `str`.** `iss` must match character for character; `HttpUrl` adds or keeps a trailing slash. Copy `issuer` and `jwks_uri` from `<issuer>/.well-known/openid-configuration`.
- **Audience is required** (`min_length=1`); `audience_claim` covers providers that use another claim ([[2c-settings-auth-cognito]]).
- **Asymmetric algorithms only,** enforced by the `Literal`.
- **HTTPS only,** enforced by the validator.
- **Cache the JWKS** for `jwks_cache_ttl_seconds`; refetch early only for an unknown `kid`. Fetch lazily on the first request, not at startup, so a slow provider can't fail startup.
- **Every route but `/healthz` depends on verification** when nothing in front of the app checks tokens.

## Anti-patterns
- **A signing secret "just in case".** Dead configuration someone will use.
- **Skipping the audience check.** Tokens issued for other apps pass.
- **Accepting ID tokens.** APIs accept access tokens.
- **`HS256` or `none`.** The public key becomes an HMAC secret, or tokens go unsigned.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[2c-settings-auth-cognito]]
- [[layout-by-layer]]
