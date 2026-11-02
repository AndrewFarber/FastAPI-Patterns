---
title: "Settings management"
category: project-structure
tags: [settings, configuration, pydantic-settings]
status: draft
related: ["[[0-settings-guide]]", "[[1b-settings-access]]", "[[1c-settings-testing]]", "[[1e-settings-lambda]]", "[[2a-settings-app]]", "[[2b-settings-db]]", "[[2c-settings-auth]]", "[[layout-by-layer]]"]
---

# Settings management

## Problem
Configuration scattered across `os.getenv()` calls is untyped, unvalidated, and invisible: a missing or malformed value only surfaces when the code path that reads it runs, often in production.

## Use when
- Always.

## Avoid when
- Never skip it. For values that must change while the app runs, add [[4a-settings-refreshing-values]] on top.

## Solution

### The settings package
Each concern gets its own file with one sub-model. `settings.py` composes them into the root `Settings` class.

```
config/
├── __init__.py
├── settings.py     Settings: composes the sub-models, nothing else
├── app.py          AppSettings        see [[2a-settings-app]]
├── db.py           DbSettings         see [[2b-settings-db]]
├── db_iam.py       IamAuth            see [[2b-settings-db-iam-auth]]
├── db_rotated.py   RotatedSecretAuth  see [[2b-settings-db-rotated-password]]
├── auth.py         AuthSettings       see [[2c-settings-auth]]
├── cors.py         CorsSettings       see [[2d-settings-cors]]
├── email.py        EmailSettings      see [[2e-settings-email]]
├── features.py     FeatureSettings    see [[2f-settings-feature-flags]]
└── log.py          LogSettings, configure_logging()
```

### A sub-model
Every sub-model looks like `LogSettings` below: a plain `BaseModel`, frozen, rejecting unknown fields, with pydantic types doing the validation. `log.py` also holds `configure_logging()`, the one place logging is set up; `create_app()` calls it at startup ([[1b-settings-access]]).

```python
# app/config/log.py
import json
import logging
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_format: bool = False


# Attributes every LogRecord has; anything else was added by a filter or extra={...}
_RECORD_FIELDS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so CloudWatch Logs Insights can query the fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{k: v for k, v in vars(record).items() if k not in _RECORD_FIELDS},
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(log: LogSettings, *filters: logging.Filter) -> None:
    """Send every logger's records to stdout (CloudWatch on Lambda) at the configured level."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if log.json_format else logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    for f in filters:
        handler.addFilter(f)          # on the root handler, so records from child loggers get it too
    logging.basicConfig(level=log.level, handlers=[handler], force=True)   # force: replace earlier handlers
```

### The root settings class
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
```

How the app creates and reads this object is in [[1b-settings-access]]; tests are in [[1c-settings-testing]].

### Environment variables
For local development: a shell, `docker run --env-file`, or docker-compose. Deployed environments set only non-secret values this way (see the rules below).

```bash
# Local development values.
# Comments go on their own lines: env files (docker --env-file, docker-compose) keep
# anything after "=" as the value, including a trailing "# comment".
# JSON lists are single-quoted so the shell keeps their double quotes.
APP__DEBUG=true

DB__HOST=localhost
DB__USER=app
DB__AUTH__METHOD=password
DB__AUTH__PASSWORD=app
DB__NAME=orders
# Local Postgres has no TLS; RDS uses verify-full (see the 2b-settings-db note)
DB__SSLMODE=disable

AUTH__ISSUER=https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz
AUTH__AUDIENCES='["1example23456789"]'
AUTH__AUDIENCE_CLAIM=client_id
AUTH__REQUIRED_CLAIMS='{"token_use": "access"}'

CORS__ALLOW_ORIGINS='["http://localhost:3000"]'

LOG__LEVEL=DEBUG
```

In env files (no shell involved), write JSON lists without the outer single quotes: `CORS__ALLOW_ORIGINS=["http://localhost:3000"]`.

Other ways values reach `Settings`: AWS Secrets Manager or Parameter Store, read by the app ([[3b-settings-aws-sources]]), and secret files for local docker-compose development ([[3a-settings-secret-files]]).

### Rules
- **One concern per file**, with its sub-model named `<Concern>Settings`. A concern with variants splits them into files of their own (`db.py` imports `db_iam.py` and `db_rotated.py`). Only `settings.py` defines a `BaseSettings` class.
- **Concerns don't import each other.** Rules that span concerns (e.g. "no debug in prod") go in a `model_validator` on the root class; rules within one concern (e.g. CORS credentials) go on that sub-model.
- **`settings.py` only composes.** No fields of its own: app-wide values live in `app.py` like any other concern.
- **Defaults:** safe values (log level, empty CORS list) get defaults; credentials and connection details never do.
- **Optional subsystems** use `X | None = None`. Code checks `if settings.email is None` instead of reading a separate `email_enabled` flag.
- **Sub-model defaults** use `Field(default_factory=...)`, not a shared instance.
- **Validate formats with pydantic types and constraints** (`EmailStr`, `Literal`, `Field(pattern=..., gt=...)`) so bad values fail at startup, not at first use.
- **`extra="forbid"` on every model.** A misspelled env var (`DB__POOL_SZIE`) or a stale field fails at startup instead of being silently ignored.
- **No secrets in plain env vars in deployed environments.** On Lambda, env vars are readable by anyone with `lambda:GetFunctionConfiguration` and limited to 4 KB in total. Passwords and keys stay in Secrets Manager or Parameter Store, and the app reads them at startup ([[3b-settings-aws-sources-pydantic]]) or per connection ([[2b-settings-db-rotated-password]]); env vars carry only the secret's ARN or name. See [[1e-settings-lambda]].
- Env var names are case-insensitive; nested fields use the `__` delimiter. Source priority, highest first: init kwargs → environment variables → dotenv file → secret files → defaults. The dotenv and secret-file sources read nothing until `env_file` or `secrets_dir` is set ([[3a-settings-secret-files]]); this `Settings` sets neither.

## Pitfalls
- **Reading `os.environ` directly** anywhere outside `config/`. All configuration goes through `Settings`. The exception is runtime metadata the platform sets, not configuration: `AWS_LAMBDA_FUNCTION_VERSION` in `app/observability.py` ([[1d-settings-deployments]]).
- **Defaults for required values.** A default database host hides a missing env var until the app connects to the wrong place. No default means startup fails fast.
- **Plain `str` for secrets.** Use `SecretStr` so values show as `**********` in logs, reprs, and tracebacks; call `.get_secret_value()` only where the raw value is needed.
- **Unquoted JSON in shell commands.** `X=["a"]` reaches Python as `[a]`; quote it: `X='["a"]'`.
- **Trailing comments in env files.** Docker and docker-compose env files keep `value  # comment` as the value. Put comments on their own lines.
- **Unrelated env vars named like a field.** Every env var whose name matches a field is read: a variable called `APP`, `LOG`, or `DB__ANYTHING`, set by the platform or an extension, stops the app at startup. Keep the function's environment to the app's own variables, or add an `env_prefix` to `SettingsConfigDict`.
- **Per-environment subclasses.** Use one class; environments differ only by the env vars they set.
- **Mutating settings at runtime.** `frozen=True` on the root class doesn't freeze nested sub-models; each sub-model needs its own `frozen=True`. For values that legitimately change, see [[4a-settings-refreshing-values]].
- **Nested sub-models extending `BaseSettings`.** They should be plain `BaseModel`; only the root class reads the environment.

## Related
- [[0-settings-guide]]
- [[1b-settings-access]]
- [[1c-settings-testing]]
- [[1e-settings-lambda]]
- [[2a-settings-app]]
- [[2b-settings-db]]
- [[2c-settings-auth]]
- [[layout-by-layer]]
