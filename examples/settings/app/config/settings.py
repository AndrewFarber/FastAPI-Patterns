from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.app import AppSettings
from app.config.auth import AuthSettings
from app.config.cors import CorsSettings
from app.config.db import DbSettings
from app.config.email import EmailSettings
from app.config.features import FeatureSettings
from app.config.log import LogSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",   # DB__HOST -> settings.db.host
        extra="forbid",              # typos like DB__POOL_SZIE fail at startup
        frozen=True,
    )

    # Required concerns (no default, so startup fails if missing)
    db: DbSettings
    auth: AuthSettings

    # Concerns with safe defaults
    app: AppSettings = Field(default_factory=AppSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)

    # Optional subsystem (None = disabled)
    email: EmailSettings | None = None

    # Cross-concern rules live on the root class
    @model_validator(mode="after")
    def check_prod_safety(self) -> Self:
        if self.app.is_prd:
            if self.app.debug:
                raise ValueError("debug must be off in prod")
            if "*" in self.cors.allow_origins:
                raise ValueError("wildcard CORS origin is not allowed in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    """Built once per process (on Lambda: per execution environment). create_app() calls it at import."""
    return Settings()
