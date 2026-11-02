---
title: "Settings management"
category: project-structure
related:
  - "[[settings-guide]]"
  - "[[settings-aws-sources]]"
  - "[[settings-db-iam-auth]]"
  - "[[settings-app]]"
  - "[[settings-db]]"
  - "[[settings-cors]]"
  - "[[services-events]]"
  - "[[settings-feature-flags]]"
  - "[[layout-core]]"
---

# Settings management

## Overview
All configuration goes through one typed, frozen `Settings` object, composed from one sub-model per concern and validated at startup. A missing or malformed value fails the app before it serves traffic, not when the code path that reads it first runs.

## Rules
- **One concern per file**, its sub-model named `<Concern>Settings`. Variants of a concern get their own files (`db.py` imports `db_iam.py`).
- **Only the root is a `BaseSettings`.** Sub-models are plain `BaseModel`; only the root reads the environment.
- **`settings.py` only composes:** the sub-models, the cross-concern rules, and the sources. App-wide values live in `app.py` like any other concern.
- **Concerns don't import each other.** Cross-concern rules ("no debug in prod", "no password DB auth in prod") are a `model_validator` on the root; rules within a concern go on its sub-model.
- **`frozen=True` and `extra="forbid"` on every model.** The root's `frozen` doesn't reach sub-models; `forbid` turns a typo (`DB__POOL_SZIE`) into a startup error.
- **Required concerns have no default; safe concerns use `Field(default_factory=...)`; optional subsystems are `X | None = None`.** Code checks `settings.smtp is None`, never a separate `smtp_enabled` flag.
- **Defaults only for safe values** (log level, empty CORS list), never for credentials or hosts.
- **Validate with types:** `SecretStr`, `Literal`, `Field(pattern=..., gt=...)`.
- **No secrets in plain env vars when deployed.** Env vars carry a secret's ARN or name and the app reads the value ([[settings-aws-sources]]); the database uses IAM and has no password ([[settings-db-iam-auth]]). Env vars are readable by anyone who can read the deployment configuration.
- **One class for every environment.** Environments differ only by the values they set.

## Code example
```
config/
├── settings.py     Settings: composes the sub-models and sources
├── app.py          AppSettings        [[settings-app]]
├── db.py           DbSettings         [[settings-db]]
├── db_iam.py       IamAuth            [[settings-db-iam-auth]]
├── cors.py         CorsSettings       [[settings-cors]]
├── events.py       EventsSettings     [[services-events]]
├── features.py     FeatureSettings    [[settings-feature-flags]]
└── log.py          LogSettings
```

Every sub-model looks like `LogSettings`: a plain `BaseModel`, frozen, rejecting unknown fields, with pydantic types doing the validation. `config/` holds only models and their validation; code that acts on a concern lives in its own `core/` package, like `configure_logging()` in `core/observability/` ([[layout-core]]).

```python
# app/core/config/log.py
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
```

The root composes the sub-models, holds the cross-concern rules, and adds the AWS sources when their env vars are set ([[settings-aws-sources]]):

```python
# app/core/config/settings.py
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
                raise ValueError(
                    "password DB auth is for local use; prod uses iam"
                )
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
            sources.append(
                AWSSecretsManagerSettingsSource(settings_cls, secret_id)
            )
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(
                AWSSystemsManagerSettingsSource(settings_cls, ssm_path)
            )

        return tuple(sources)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Env vars map to nested fields with `__`:

```bash
DB__HOST=localhost
DB__AUTH__METHOD=password
# JSON lists single-quoted in a shell; unquoted in env files
CORS__ALLOW_ORIGINS='["http://localhost:3000"]'
SWITCHES__REGION=us-east-1
SWITCHES__ORDERS_PAUSED=/shop/switches/orders-paused
```
