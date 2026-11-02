---
title: "Settings from AWS sources"
category: project-structure
related:
  - "[[settings-guide]]"
  - "[[settings-refreshing-values]]"
  - "[[settings-db-iam-auth]]"
  - "[[settings-testing]]"
---

# Settings from AWS sources

## Overview
Read Secrets Manager and Parameter Store as pydantic-settings sources, added only when their env var is set. Values pass through the same validation as env vars, at startup, and local runs and tests need no AWS access.

**Where each value comes from:**

| Value | Source |
|---|---|
| Non-secret, few | Env var, set at deploy |
| Secret, or many values | These sources, at startup |
| Changes while running | A cache client: [[settings-refreshing-values]] |
| DB credentials | None: IAM ([[settings-db-iam-auth]]) |

## Rules
- **Opt-in by env var,** so the fixtures in [[settings-testing]] work unchanged; test the wiring with `moto`.
- **Env vars first,** so a deploy can override one value.
- **One source per field.** A sub-model may span both: its plain fields under the path, its secret fields in the secret.
- **Names match field names, case-sensitively.** `extra="forbid"` catches wrong names inside a sub-model; a wrong first segment (`/shop/prd/Db/host`) is silently ignored.
- **Lists are JSON strings.**
- **Few calls per startup:** one secret, one small path (a `GetParametersByPath` call per 10 parameters). Every new instance repeats them, and Parameter Store allows 40 TPS per account by default.
- **Timeouts through `AWS_DEFAULTS_MODE`.** The sources build their own boto3 clients and accept no `Config`, so the env var is the only way to shorten their timeouts. Clients the app builds itself pass an explicit `Config` ([[settings-refreshing-values]]).
- **Least privilege:** `GetSecretValue` on the app's secret ARN (`-??????` suffix, not `-*`), `GetParametersByPath` on its path.

## Code example
```bash
uv add "pydantic-settings[aws-secrets-manager,aws-systems-manager]"
```

```python
# app/core/config/settings.py (fragment: the full file is in settings-management)
import os

from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
    BaseSettings,
    PydanticBaseSettingsSource,
)


class Settings(BaseSettings):
    ...

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
```

```bash
# Deployed env vars; unset locally
AWS_SECRETS_MANAGER_SECRET_ID=shop/prd/app
AWS_SSM_PATH=/shop/prd
# The sources build their own boto3 clients: short connect timeout, standard retries
AWS_DEFAULTS_MODE=in-region
```

| | Secrets Manager | Parameter Store |
|---|---|---|
| Holds | Secrets | Plain configuration |
| Shape | One secret, a JSON object | One parameter per field under a path |
| Nested field | Key `<concern>--<field>` | `/shop/prd/db/host` |
