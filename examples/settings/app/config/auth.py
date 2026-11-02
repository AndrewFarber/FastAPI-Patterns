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
