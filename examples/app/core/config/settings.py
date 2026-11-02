import os
from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from app.core.config.app import AppSettings
from app.core.config.cors import CorsSettings
from app.core.config.db import DbSettings, PasswordAuth
from app.core.config.events import EventsSettings
from app.core.config.features import FeatureSettings
from app.core.config.log import LogSettings
from app.core.config.switches import SwitchSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    db: DbSettings
    events: EventsSettings
    switches: SwitchSettings

    app: AppSettings = Field(default_factory=AppSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)

    @model_validator(mode="after")
    def check_prod_safety(self) -> Self:
        if self.app.is_prd:
            if self.app.debug:
                raise ValueError("debug must be off in prod")
            if "*" in self.cors.allow_origins:
                raise ValueError("wildcard CORS origin is not allowed in prod")
            if isinstance(self.db.auth, PasswordAuth):
                raise ValueError("password DB auth is for local use; prod uses iam")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources = [init_settings, env_settings]

        if secret_id := os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID"):
            sources.append(AWSSecretsManagerSettingsSource(settings_cls, secret_id))
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(AWSSystemsManagerSettingsSource(settings_cls, ssm_path))

        return tuple(sources)


@lru_cache
def get_settings() -> Settings:
    return Settings()
