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
