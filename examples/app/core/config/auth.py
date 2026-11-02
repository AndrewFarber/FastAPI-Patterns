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
