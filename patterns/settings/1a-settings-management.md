---
title: "Settings management"
category: project-structure
tags: [settings, configuration, pydantic-settings]
status: draft
related: ["[[0-settings-guide]]", "[[1b-settings-access]]", "[[1c-settings-testing]]", "[[2a-settings-app]]", "[[2b-settings-db]]", "[[2c-settings-auth-cognito]]", "[[3b-settings-aws-sources]]", "[[1a-layout-by-layer]]"]
---

# Settings management

All configuration goes through one typed, frozen `Settings` object, composed from one sub-model per concern and validated at startup. A missing or malformed value fails the app before it serves traffic, not when the code path that reads it first runs.

## Fits when
- Always: any app with configuration.

Not when:
- Never skip it. Values that must change while the app runs add [[4a-settings-refreshing-values]] on top.

## Signals
- **Feature:** a new env var, a new external service to configure, "make X configurable".
- **Code:** `os.getenv(` or `os.environ[` outside `config/`; a flat `Settings` with `db_host`, `db_password: str`; nested models extending `BaseSettings`; `smtp_enabled: bool` next to the fields it switches; per-environment subclasses (`ProdSettings`); `password: str` instead of `SecretStr`.

## Pattern
```
config/
├── settings.py     Settings: composes the sub-models, nothing else
├── app.py          AppSettings        [[2a-settings-app]]
├── db.py           DbSettings         [[2b-settings-db]]
├── db_iam.py       IamAuth            [[2b-settings-db-iam-auth]]
├── db_rotated.py   RotatedSecretAuth  [[2b-settings-db-rotated-password]]
├── auth.py         AuthSettings       [[2c-settings-auth-cognito]]
├── cors.py         CorsSettings       [[2d-settings-cors]]
├── features.py     FeatureSettings    [[2f-settings-feature-flags]]
└── log.py          LogSettings, configure_logging()
```

Every sub-model looks like `LogSettings`: a plain `BaseModel`, frozen, rejecting unknown fields, with pydantic types doing the validation. A concern's setup function (`configure_logging()`) lives next to its model.

```python
# app/config/log.py
import logging
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


def configure_logging(log: LogSettings) -> None:
    """Send every logger's records to stdout at the configured level."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=log.level, handlers=[handler], force=True)   # force: replace earlier handlers
```

```python
# app/config/settings.py
from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.app import AppSettings
from app.config.auth import AuthSettings
from app.config.cors import CorsSettings
from app.config.db import DbSettings
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
    """Built once per process. create_app() calls it at import."""
    return Settings()
```

Env vars map to nested fields with `__`:

```bash
DB__HOST=localhost
DB__AUTH__METHOD=password
# JSON lists single-quoted in a shell; unquoted in env files
CORS__ALLOW_ORIGINS='["http://localhost:3000"]'
```

## Rules
- **One concern per file**, its sub-model named `<Concern>Settings`. Variants of a concern get their own files (`db.py` imports `db_iam.py`, `db_rotated.py`).
- **Only the root is a `BaseSettings`.** Sub-models are plain `BaseModel`; only the root reads the environment.
- **`settings.py` only composes.** App-wide values live in `app.py` like any other concern.
- **Concerns don't import each other.** Cross-concern rules ("no debug in prod") are a `model_validator` on the root; rules within a concern go on its sub-model.
- **`frozen=True` and `extra="forbid"` on every model.** The root's `frozen` doesn't reach sub-models; `forbid` turns a typo (`DB__POOL_SZIE`) into a startup error.
- **Required concerns have no default; safe concerns use `Field(default_factory=...)`; optional subsystems are `X | None = None`.** Code checks `settings.smtp is None`, never a separate `smtp_enabled` flag.
- **Defaults only for safe values** (log level, empty CORS list), never for credentials or hosts.
- **Validate with types:** `SecretStr`, `Literal`, `Field(pattern=..., gt=...)`.
- **No secrets in plain env vars when deployed.** Env vars carry a secret's ARN or name; the app reads the value ([[3b-settings-aws-sources]], [[2b-settings-db-rotated-password]]). Env vars are readable by anyone who can read the deployment configuration.
- **One class for every environment.** Environments differ only by the values they set.

## Anti-patterns
- **`os.environ` outside `config/`.** Values read there skip validation and fail only when the code path runs.
- **Plain `str` for secrets.** Only `SecretStr` is masked in logs, reprs, and tracebacks.
- **A default for a required value.** A default host hides a missing env var until the app connects to the wrong place.
- **Trailing comments in env files.** Docker keeps `value  # comment` as the value.
- **Unrelated env vars named like a field.** A platform variable called `APP` or `DB__X` fails startup; keep the environment to the app's own variables, or add an `env_prefix`.

## Related
- [[0-settings-guide]]
- [[1b-settings-access]]
- [[1c-settings-testing]]
- [[2a-settings-app]]
- [[2b-settings-db]]
- [[2c-settings-auth-cognito]]
- [[3b-settings-aws-sources]]
- [[1a-layout-by-layer]]
