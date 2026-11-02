---
title: "Auth settings"
category: auth-security
tags: [settings, authentication, oidc, jwt]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1e-settings-lambda]]", "[[2c-settings-auth-cognito]]", "[[layout-by-layer]]"]
---

# Auth settings

## Problem
Apps that sign their own tokens must store and rotate a signing secret, and a leaked secret lets anyone mint valid tokens. Delegating sign-in to an identity provider (IdP) removes the secret, but the API still needs the right values to verify the provider's tokens: who issued them, where the signing keys are, who they were issued for, and which algorithms to trust.

## Use when
- Users sign in through an OpenID Connect / OAuth 2.0 identity provider (AWS Cognito, Auth0, Okta, Microsoft Entra ID, Keycloak) and the API verifies the JWTs it issues.

## Avoid when
- The app issues its own tokens. That needs a signing key in settings (`SecretStr`) and is a different pattern.
- The API sits behind a gateway that already verifies tokens and forwards trusted claims (e.g. API Gateway with a JWT authorizer). Configure the gateway instead. A Lambda Function URL is not such a gateway: it offers only `NONE` or IAM (SigV4) auth, so the app verifies user tokens itself.

## Solution

### The settings model
The same fields describe any provider; only their values differ.

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

- **No secrets here.** The provider signs tokens with its private keys; the API only needs public values to fetch the signing keys and check the claims. Token verification itself lives in `security/` (a separate note, not written yet).
- **Settings, not code, per provider.** Switching providers or environments changes env vars only.
- **Plain env vars are fine here.** Every value is public, so the deployed function sets them directly (`AUTH__ISSUER`, `AUTH__AUDIENCES`); keep `audiences` short, all env vars share 4 KB on Lambda ([[1e-settings-lambda]]).

### On Lambda
- **The app is the only check.** The Function URL uses auth type `NONE`, so every route except the readiness path (`/healthz`) must depend on token verification.
- **The JWKS cache lives per execution environment.** Each new environment fetches the keys again on its first token, so a burst of cold starts is a burst of JWKS requests to the provider. Fetch with a short timeout, and lazily on the first request, not at init: a slow provider would otherwise fail init ([[1e-settings-lambda]]).

### Provider values

| Provider | `issuer` | `jwks_url` | `audience_claim` |
|---|---|---|---|
| AWS Cognito (access tokens) | `https://cognito-idp.<region>.amazonaws.com/<pool-id>` | default | `client_id`, plus `token_use: access` |
| Auth0 | `https://<tenant>.auth0.com/` (trailing slash) | default | `aud` (the API identifier) |
| Okta (custom authorization server) | `https://<org>.okta.com/oauth2/<server-id>` | `<issuer>/v1/keys` | `aud` |
| Microsoft Entra ID (v2 tokens) | `https://login.microsoftonline.com/<tenant-id>/v2.0` | `https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys` | `aud` |

Every OIDC provider lists its exact `issuer` and `jwks_uri` at `<issuer>/.well-known/openid-configuration`. Copy them from there rather than guessing.

Provider-specific setup: AWS Cognito in [[2c-settings-auth-cognito]].

## Pitfalls
- **Keeping a signing secret "just in case".** With an external provider the app never signs tokens; a `jwt_secret` field is dead configuration that someone will eventually use.
- **Issuer typos and trailing slashes.** `iss` must match exactly. `https://example.auth0.com` and `https://example.auth0.com/` are different issuers.
- **Skipping the audience check.** Without it, any token from the same provider (issued for another app) is accepted.
- **Accepting ID tokens at the API.** ID tokens describe the user to the client app; APIs should accept access tokens.
- **Allowing symmetric or `none` algorithms.** An attacker could sign tokens with the public key as an HMAC secret, or not sign them at all. The `Literal` allows asymmetric algorithms only.
- **Turning on Function URL IAM auth for user tokens.** `AWS_IAM` expects SigV4-signed requests from AWS principals; browser clients with a JWT are rejected before the app sees them.
- **Fetching the JWKS on every request.** Cache the keys for `jwks_cache_ttl_seconds`, and refetch early only when a token's `kid` isn't in the cache (the provider rotated its keys).

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1e-settings-lambda]]
- [[2c-settings-auth-cognito]]
- [[layout-by-layer]]
